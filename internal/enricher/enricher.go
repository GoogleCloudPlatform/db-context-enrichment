/*
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package enricher

import (
	"bytes"
	"context"
	"fmt"
	"log"
	"os"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
	"github.com/google/generative-ai-go/genai"
	"google.golang.org/api/option"
	"google.golang.org/grpc/status"
)

// MetadataCollector collects metadata and applies comments.
type MetadataCollector struct {
	db                *database.DB        // Database connection
	retryOpts         *RetryOptions       // Retry configuration
	DryRun            bool                // Dry run mode flag
	Metadata          []*ColumnMetadata   // Collected metadata
	TableMetadata     []*TableMetadata    // Collected table metadata
	mu                sync.Mutex          // Mutex to protect Metadata slice
	TableFilters      map[string][]string // Table and column filters
	Enrichments       map[string]bool     // Enrichment types to include
	GeminiAPIKey      string              // Gemini API Key
	Model             string              // Gemini model name
	AdditionalContext string              // Additional context from files
	schemaContext     string              // Database schema context (generated once)
}

// NewMetadataCollector creates a new MetadataCollector instance.
func NewMetadataCollector(db *database.DB, retryOpts *RetryOptions, dryRun bool, geminiAPIKey string, additionalContext string, model string) *MetadataCollector {
	return &MetadataCollector{
		db:                db,
		retryOpts:         retryOpts,
		DryRun:            dryRun,
		Metadata:          []*ColumnMetadata{},
		TableMetadata:     []*TableMetadata{},
		TableFilters:      make(map[string][]string),
		Enrichments:       make(map[string]bool),
		GeminiAPIKey:      geminiAPIKey,
		AdditionalContext: additionalContext,
		schemaContext:     "",
		Model:             model,
	}
}

// IsGeminiAPIKeyValid checks if the Gemini API key is valid by attempting to list models.
func (mc *MetadataCollector) IsGeminiAPIKeyValid(ctx context.Context) error {
	if mc.GeminiAPIKey == "" {
		return fmt.Errorf("gemini api key is not configured")
	}

	client, err := genai.NewClient(ctx, option.WithAPIKey(mc.GeminiAPIKey))
	if err != nil {
		return fmt.Errorf("failed to create Gemini client: %w", err)
	}
	defer client.Close()

	modelIterator := client.ListModels(ctx)

	// Iterate to trigger the API call and check for errors during iteration.
	_, err = modelIterator.Next()
	if err != nil {
		// Check if the error is related to authentication (invalid API key)
		if st, ok := status.FromError(err); ok {
			if st.Code() == 16 || // Unauthenticated
				st.Code() == 7 { // PermissionDenied (sometimes used for invalid keys)
				return fmt.Errorf("invalid Gemini API key: %w", err)
			}
		}
		return fmt.Errorf("failed to list Gemini models, potentially due to API key issue or other error: %w", err)
	}
	return nil
}

// Helper function to check if a specific enrichment is requested
func (mc *MetadataCollector) isEnrichmentRequested(enrichment string) bool {
	if len(mc.Enrichments) == 0 {
		return true // If no enrichments are specified, include all
	}
	return mc.Enrichments[enrichment]
}

// CollectColumnMetadata gathers comprehensive metadata for a specific database column.
func (mc *MetadataCollector) CollectColumnMetadata(ctx context.Context, tableName string, colInfo database.ColumnInfo, schemaContext string) (*ColumnMetadata, error) {
	if tableName == "" || colInfo.Name == "" {
		return nil, &ErrInvalidInput{
			Msg: "table name and column name cannot be empty",
		}
	}

	var (
		exampleValues []string
		distinctCount int64
		nullCount     int64
		err           error
	)
	dbMetadata := make(map[string]interface{})

	if mc.isEnrichmentRequested("examples") || mc.isEnrichmentRequested("distinct_values") || mc.isEnrichmentRequested("null_count") {
		dbMetadata, err = mc.db.GetColumnMetadata(tableName, colInfo.Name)
		if err != nil {
			return nil, &ErrQueryExecution{
				Msg: "failed to get column metadata",
				Err: err,
			}
		}
	}

	if mc.isEnrichmentRequested("examples") {
		retrivedExampleValues, ok := dbMetadata["ExampleValues"].([]string)
		if !ok {
			log.Println("WARN: unexpected type for ExampleValues")
		}
		exampleValues = retrivedExampleValues

		if mc.GeminiAPIKey != "" {
			processedExampleValues, err := mc.generateExampleValuesWithGemini(ctx, colInfo, tableName, exampleValues)
			if err != nil {
				log.Printf("WARN: Failed to generate/process example values with Gemini for column %s.%s: %v, using original examples.", tableName, colInfo.Name, err)
			} else {
				exampleValues = processedExampleValues
			}
		}
	}

	if mc.isEnrichmentRequested("distinct_values") {
		distinctCountFloat, ok := dbMetadata["DistinctCount"].(int)
		if !ok {
			log.Println("WARN: unexpected type for DistinctCount")
		}
		distinctCount = int64(distinctCountFloat)
	}

	if mc.isEnrichmentRequested("null_count") {
		nullCountFloat, ok := dbMetadata["NullCount"].(int)
		if !ok {
			log.Println("WARN: unexpected type for NullCount")
		}
		nullCount = int64(nullCountFloat)
	}

	metadata := &ColumnMetadata{
		Table:         tableName,
		Column:        colInfo.Name,
		DataType:      colInfo.DataType,
		ExampleValues: exampleValues,
		DistinctCount: distinctCount,
		NullCount:     nullCount,
	}

	// Generate description using Gemini if API key is available and "description" enrichment is requested
	if mc.GeminiAPIKey != "" && mc.isEnrichmentRequested("description") {
		description, err := mc.generateDescriptionWithGemini(ctx, metadata, schemaContext)
		if err != nil {
			log.Printf("WARN: Failed to generate description with Gemini for %s.%s: %v", tableName, colInfo.Name, err)
		} else {
			metadata.Description = description
		}
	}

	return metadata, nil
}

// CollectTableMetadata collects metadata for a table
func (mc *MetadataCollector) CollectTableMetadata(ctx context.Context, tableName string, schemaContext string) (*TableMetadata, error) {
	if tableName == "" {
		return nil, &ErrInvalidInput{Msg: "table name cannot be empty"}
	}

	metadata := &TableMetadata{
		Table: tableName,
	}

	// Generate description using Gemini if API key is available.s
	if mc.GeminiAPIKey != "" && mc.isEnrichmentRequested("description") {
		description, err := mc.generateTableDescriptionWithGemini(ctx, metadata, schemaContext)
		if err != nil {
			log.Printf("WARN: Failed to generate table description with Gemini for %s: %v", tableName, err)
		} else {
			metadata.Description = description
		}
	}

	return metadata, nil
}

// GenerateCommentSQLs collects metadata and generates SQL statements, no application.
func (mc *MetadataCollector) GenerateCommentSQLs(ctx context.Context) ([]string, error) {
	startTime := time.Now()
	log.Println("INFO: Starting metadata collection and SQL comment generation...")

	tables, err := mc.db.ListTables()
	if err != nil {
		return nil, fmt.Errorf("failed to list tables: %w", err)
	}

	// Apply table filtering
	filteredTables := []string{}
	if len(mc.TableFilters) > 0 {
		for table := range mc.TableFilters {
			filteredTables = append(filteredTables, table)
		}
	} else {
		filteredTables = tables
	}
	tables = filteredTables

	// Generate schema context once
	schemaContext, err := mc.generateSchemaContext()
	if err != nil {
		log.Printf("WARN: Failed to generate schema context: %v", err)
		schemaContext = ""
	}
	mc.schemaContext = schemaContext

	var orderedSQLs []OrderedSQL
	var wg sync.WaitGroup
	errorChannel := make(chan error, len(tables))
	var mu sync.Mutex

	for _, table := range tables {
		wg.Add(1)
		go func(table string) {
			defer wg.Done()

			// Collect TABLE metadata and generate SQL
			tableMetadata, err := withRetry[*TableMetadata](ctx, DefaultRetryOptions, func(ctx context.Context) (*TableMetadata, error) {
				return mc.CollectTableMetadata(ctx, table, mc.schemaContext)
			})
			if err != nil {
				log.Println("ERROR: Failed to collect metadata for table:", table, "error:", err)
				errorChannel <- err
				return
			}

			tableCommentData := &database.TableCommentData{
				TableName:   tableMetadata.Table,
				Description: tableMetadata.Description,
			}
			tableSQL, genTableErr := mc.db.GenerateTableCommentSQL(tableCommentData, mc.Enrichments)
			if genTableErr != nil {
				log.Printf("WARN: Failed to generate table comment SQL for %s: %v", table, genTableErr)
				errorChannel <- genTableErr
				return
			}

			if tableSQL != "" {
				mu.Lock()
				orderedSQLs = append(orderedSQLs, OrderedSQL{SQL: tableSQL, Table: table, IsTableComment: true})
				mu.Unlock()
			}

			columnInfos, err := mc.db.ListColumns(table)
			if err != nil {
				log.Println("ERROR: Failed to list columns for table:", table, "error:", err)
				errorChannel <- err
				return
			}
			// Apply column filtering
			filteredColumnInfos := []database.ColumnInfo{}

			if columnFilters, ok := mc.TableFilters[table]; ok && columnFilters != nil {
				for _, colInfo := range columnInfos {
					for _, filteredCol := range columnFilters {
						if colInfo.Name == filteredCol {
							filteredColumnInfos = append(filteredColumnInfos, colInfo)
							break
						}
					}
				}
			} else {
				filteredColumnInfos = columnInfos
			}
			columnInfos = filteredColumnInfos

			for _, colInfo := range columnInfos {
				wg.Add(1)
				go func(colInfo database.ColumnInfo) {
					defer wg.Done()

					metadata, err := withRetry[*ColumnMetadata](ctx, DefaultRetryOptions, func(ctx context.Context) (*ColumnMetadata, error) {
						return mc.CollectColumnMetadata(ctx, table, colInfo, mc.schemaContext)
					})
					if err != nil {
						log.Println("ERROR: Failed to collect metadata for column:", colInfo.Name, "in table:", table, "error:", err)
						errorChannel <- err
						return
					}

					commentData := &database.CommentData{
						TableName:      metadata.Table,
						ColumnName:     metadata.Column,
						ColumnDataType: metadata.DataType,
						ExampleValues:  metadata.ExampleValues,
						DistinctCount:  metadata.DistinctCount,
						NullCount:      metadata.NullCount,
						Description:    metadata.Description,
					}
					// Pass mc.Enrichments to GenerateCommentSQL
					sql, genErr := mc.db.GenerateCommentSQL(commentData, mc.Enrichments)
					if genErr != nil {
						log.Printf("WARN: Failed to generate comment SQL for %s.%s: %v", metadata.Table, metadata.Column, genErr)
						errorChannel <- genErr
						return
					}

					if sql != "" {
						mu.Lock()
						sql = "\t" + sql                                                                                                   // Lock before modifying orderedSQLs
						orderedSQLs = append(orderedSQLs, OrderedSQL{SQL: sql, Table: table, Column: colInfo.Name, IsTableComment: false}) // Mark as column comment
						mu.Unlock()                                                                                                        // Unlock after modifying orderedSQLs
					}
				}(colInfo)
			}
		}(table)
	}

	wg.Wait()
	close(errorChannel)

	// Sort orderedSQLs to maintain order
	sort.Slice(orderedSQLs, func(i, j int) bool {
		if orderedSQLs[i].Table != orderedSQLs[j].Table {
			return orderedSQLs[i].Table < orderedSQLs[j].Table
		}
		if orderedSQLs[i].IsTableComment != orderedSQLs[j].IsTableComment {
			return orderedSQLs[i].IsTableComment
		}
		return orderedSQLs[i].Column < orderedSQLs[j].Column
	})

	allSQLs := make([]string, 0, len(orderedSQLs))
	for _, osql := range orderedSQLs {
		allSQLs = append(allSQLs, osql.SQL)
	}

	log.Println("INFO: Metadata collection and SQL comment generation completed in:", time.Since(startTime))
	return allSQLs, nil
}

// GenerateDeleteCommentSQLs collects metadata and generates SQL for deletion.
func (mc *MetadataCollector) GenerateDeleteCommentSQLs(ctx context.Context) ([]string, error) {
	startTime := time.Now()
	log.Println("INFO: Starting metadata collection and SQL comment deletion generation...")

	tables, err := mc.db.ListTables()
	if err != nil {
		return nil, fmt.Errorf("failed to list tables: %w", err)
	}

	// Apply table filtering
	filteredTables := []string{}
	if len(mc.TableFilters) > 0 {
		for table := range mc.TableFilters {
			filteredTables = append(filteredTables, table)
		}
	} else {
		filteredTables = tables
	}
	tables = filteredTables

	var allSQLs []string
	var wg sync.WaitGroup
	errorChannel := make(chan error, len(tables))

	for _, table := range tables {
		wg.Add(1)
		go func(table string) {
			defer wg.Done()
			// Generate SQL for deleting TABLE comments
			tableSQL, genTableErr := withRetry[string](ctx, DefaultRetryOptions, func(ctx context.Context) (string, error) {
				return mc.db.GenerateDeleteTableCommentSQL(ctx, table)
			})
			if genTableErr != nil {
				log.Printf("WARN: Failed to generate delete table comment SQL for %s: %v", table, genTableErr)
				errorChannel <- genTableErr
				return
			}
			if tableSQL != "" {
				mc.mu.Lock()
				allSQLs = append(allSQLs, tableSQL)
				mc.mu.Unlock()
			} else {
				log.Printf("INFO: No SQL generated for deleting table comment in %s, possibly no gemini tag.", table)
			}

			columnInfos, err := mc.db.ListColumns(table)
			if err != nil {
				log.Println("ERROR: Failed to list columns for table:", table, "error:", err)
				errorChannel <- err
				return
			}

			// Apply column filtering
			filteredColumnInfos := []database.ColumnInfo{}
			if columnFilters, ok := mc.TableFilters[table]; ok && columnFilters != nil {
				for _, colInfo := range columnInfos {
					for _, filteredCol := range columnFilters {
						if colInfo.Name == filteredCol {
							filteredColumnInfos = append(filteredColumnInfos, colInfo)
							break
						}
					}
				}
			} else {
				filteredColumnInfos = columnInfos
			}
			columnInfos = filteredColumnInfos

			for _, colInfo := range columnInfos {
				wg.Add(1)
				go func(colInfo database.ColumnInfo) {
					defer wg.Done()

					sql, genErr := withRetry[string](ctx, DefaultRetryOptions, func(ctx context.Context) (string, error) {
						return mc.db.GenerateDeleteCommentSQL(ctx, table, colInfo.Name)
					})
					if genErr != nil {
						log.Printf("WARN: Failed to generate delete comment SQL for %s.%s: %v", table, colInfo.Name, genErr)
						errorChannel <- genErr
						return
					}
					if sql != "" {
						mc.mu.Lock()
						allSQLs = append(allSQLs, sql)
						mc.mu.Unlock()
					} else {
						log.Printf("INFO: No SQL generated for deleting comment in %s.%s, possibly no gemini tag.", table, colInfo.Name)
					}
				}(colInfo)
			}
		}(table)
	}

	wg.Wait()
	close(errorChannel)

	// Check for and combine errors
	var combinedErr error
	for err := range errorChannel {
		if err != nil {
			if combinedErr == nil {
				combinedErr = err
			} else {
				combinedErr = fmt.Errorf("%w; %v", combinedErr, err)
			}
		}
	}
	if combinedErr != nil {
		return nil, combinedErr
	}

	if len(allSQLs) == 0 {
		log.Println("INFO: No SQL statements generated for deleting comments. Possibly no gemini tags found.")
	}

	log.Println("INFO: SQL comment deletion generation completed in:", time.Since(startTime))
	return allSQLs, nil
}

// ColumnComment represents a comment for a specific column.
type ColumnComment struct {
	Table   string `json:"table"`
	Column  string `json:"column"`
	Comment string `json:"comment"`
}

// GetComments retrieves all column and table comments.
func (mc *MetadataCollector) GetComments(ctx context.Context) ([]*ColumnComment, error) {
	tables, err := mc.db.ListTables()
	if err != nil {
		return nil, fmt.Errorf("failed to list tables: %w", err)
	}

	var allComments []*ColumnComment
	var wg sync.WaitGroup
	errorChannel := make(chan error, len(tables))

	for _, table := range tables {
		wg.Add(1)
		go func(table string) {
			defer wg.Done()

			tableComment, err := withRetry[string](ctx, DefaultRetryOptions, func(ctx context.Context) (string, error) {
				return mc.db.GetTableComment(ctx, table)
			})
			if err != nil {
				log.Printf("WARN: Failed to get table comment for table: %s, error: %v", table, err)
				errorChannel <- err
				return
			}
			if tableComment != "" {
				mc.mu.Lock()
				allComments = append(allComments, &ColumnComment{
					Table:   table,
					Column:  "", // Leave Column empty for table comments
					Comment: tableComment,
				})
				mc.mu.Unlock()
			}

			columnInfos, err := mc.db.ListColumns(table)
			if err != nil {
				log.Printf("ERROR: Failed to list columns for table: %s, error: %v", table, err)
				errorChannel <- err
				return
			}

			for _, colInfo := range columnInfos {
				wg.Add(1)
				go func(colInfo database.ColumnInfo) {
					defer wg.Done()

					comment, err := withRetry[string](ctx, DefaultRetryOptions, func(ctx context.Context) (string, error) {
						return mc.db.GetColumnComment(ctx, table, colInfo.Name)
					})
					if err != nil {
						log.Printf("WARN: Failed to get comment for column: %s in table: %s, error: %v", colInfo.Name, table, err)
						errorChannel <- err
						return
					}

					if comment != "" {
						mc.mu.Lock()
						allComments = append(allComments, &ColumnComment{
							Table:   table,
							Column:  colInfo.Name,
							Comment: comment,
						})
						mc.mu.Unlock()
					}
				}(colInfo)
			}
		}(table)
	}

	wg.Wait()
	close(errorChannel)
	var combinedErr error
	for err := range errorChannel {
		if err != nil {
			if combinedErr == nil {
				combinedErr = err
			} else {
				combinedErr = fmt.Errorf("%w; %v", combinedErr, err)
			}
		}
	}
	if combinedErr != nil {
		return nil, combinedErr
	}
	return allComments, nil
}

// FormatCommentsAsText formats the comments as plain text.
func FormatCommentsAsText(comments []*ColumnComment) string {
	var buffer bytes.Buffer
	// Sort comments by table and column
	sort.Slice(comments, func(i, j int) bool {
		if comments[i].Table != comments[j].Table {
			return comments[i].Table < comments[j].Table
		}
		return comments[i].Column < comments[j].Column
	})

	// Print comments in order
	for _, comment := range comments {
		if comment.Column == "" {
			buffer.WriteString(fmt.Sprintf("Table: %s\n", comment.Table))
		} else {
			buffer.WriteString(fmt.Sprintf("Table: %s, Column: %s\n", comment.Table, comment.Column))
		}
		buffer.WriteString(fmt.Sprintf("Comment: %s\n", comment.Comment))
		buffer.WriteString("\n") // Add an empty line
	}
	return buffer.String()
}

// WriteCommentsToFile writes the comments to a file.
func WriteCommentsToFile(comments string, filePath string) error {
	log.Printf("INFO: Writing comments to file: %s", filePath)
	file, err := os.Create(filePath)
	if err != nil {
		return fmt.Errorf("failed to create file: %w", err)
	}
	defer file.Close()

	_, err = file.WriteString(comments)
	return err
}

// generateDescriptionWithGemini calls the Gemini API to generate a column description.
func (mc *MetadataCollector) generateDescriptionWithGemini(ctx context.Context, metadata *ColumnMetadata, schemaContext string) (string, error) {
	if mc.GeminiAPIKey == "" {
		return "", nil
	}

	if mc.AdditionalContext == "" {
		return "", nil
	}

	prompt := fmt.Sprintf(`
Your task is to generate a brief and concise description for a database column based on the provided context.
The context might be irrelevant, so you need to firstly read through the context and decide if there is any relevant information for the target table.column.

********** Knowledge Context **********
%s

********** End Knowledge Context **********

**Instructions:**
- Response starting with your analysis. Then output the description in between <result></result> tags.
- Focus on the column's purpose and meaning within the database.
- Be concise and informative, no more than 50 words.
- Important: Only provide a description for the column if there is information related to this column in additional context. Otherwise in all other cases, return empty <result></result> tags.

The target table and column is:
Column Name: %s in Table: %s

Now start your response. Remember, only give description when the knowledge context provides useful information about the column.
	`, mc.AdditionalContext, metadata.Column, metadata.Table)

	client, err := genai.NewClient(ctx, option.WithAPIKey(mc.GeminiAPIKey))
	if err != nil {
		return "", fmt.Errorf("failed to create Gemini client: %w", err)
	}
	defer client.Close()

	model_name := mc.Model
	if model_name == "" {
		model_name = "gemini-1.5-pro-002"
	}
	model := client.GenerativeModel(model_name)
	model.SetTemperature(0.4)
	model.SetMaxOutputTokens(500)
	model.SetTopP(0.8)
	model.SetTopK(40)

	resp, err := model.GenerateContent(ctx, genai.Text(prompt))
	if err != nil {
		return "", fmt.Errorf("Gemini API call failed: %w", err)
	}

	description, err := extractTextFromResponse(resp)
	if err != nil {
		return "", err
	}

	return description, nil
}

// generateTableDescriptionWithGemini generates a description for a table.
func (mc *MetadataCollector) generateTableDescriptionWithGemini(ctx context.Context, metadata *TableMetadata, schemaContext string) (string, error) {
	if mc.GeminiAPIKey == "" {
		return "", nil
	}
	if mc.AdditionalContext == "" {
		return "", nil
	}
	prompt := fmt.Sprintf(`
Your task is to generate a brief and concise description for a database table based on the provided context.
The context might be irrelevant, so you need to firstly read through the context and decide if there is any relevant information for the target table.

********** Knowledge Context **********
%s

********** End Knowledge Context **********

**Instructions:**
- Response starting with your analysis. Then output the description in between <result></result> tags.
- Be concise and informative, no more than 50 words.
- Important: Only provide a description for the table if there is information related to this table in additional context. Otherwise in all other cases, return empty <result></result> tags.

The target table is:
Table: %s

Now start your response. Remember, only give description when the knowledge context provides useful information about the table.
	`, mc.AdditionalContext, metadata.Table)

	client, err := genai.NewClient(ctx, option.WithAPIKey(mc.GeminiAPIKey))
	if err != nil {
		return "", fmt.Errorf("failed to create Gemini client: %w", err)
	}
	defer client.Close()

	model_name := mc.Model
	if model_name == "" {
		model_name = "gemini-1.5-pro-002"
	}
	model := client.GenerativeModel(model_name)
	model.SetTemperature(0.4)
	model.SetMaxOutputTokens(500)
	model.SetTopP(0.8)
	model.SetTopK(40)

	resp, err := model.GenerateContent(ctx, genai.Text(prompt))
	if err != nil {
		return "", fmt.Errorf("Gemini API call failed: %w", err)
	}

	description, err := extractTextFromResponse(resp)
	if err != nil {
		return "", err
	}
	return description, nil
}

func (mc *MetadataCollector) generateExampleValuesWithGemini(ctx context.Context, colInfo database.ColumnInfo, tableName string, originalExampleValues []string) ([]string, error) {
	if mc.GeminiAPIKey == "" {
		return nil, nil
	}
	if len(originalExampleValues) == 0 {
		return []string{}, nil
	}

	dataTypeDescription := colInfo.DataType
	exampleValuesStr := strings.Join(originalExampleValues, ", ")

	prompt := fmt.Sprintf(`
	You are an expert in data privacy and database metadata. Your task is to analyze a database column and determine if it likely contains Personally Identifiable Information (PII).
	Based on your analysis, you will either return synthetic, representative example values or the original example values.

	**Column Information:**
	- Column Name: %s
	- Table Name: %s
	- Data Type: %s
	- Original Example Values: [%s]

	**Instructions:**
	1. **Analyze for PII:**  Based on the column name, data type, and example values, determine if this column is likely to contain PII. 
		Consider common patterns and keywords that indicate personal information (names, emails, phone numbers, addresses, IDs, etc.).
	2. **Decision:**
	- **If likely PII:** Generate equal number of synthetic example values that are representative of the data in the "%s" column but are completely fabricated and do not resemble real personal data.
		The synthetic values should be consistent with the "%s" data type.
	- **If NOT likely PII:** Return the original example values provided.
	3. **Output Format:**
	- If you generated synthetic values, output them as a comma-separated list enclosed in <synthetic_examples>...</synthetic_examples> tags.
	- If you are returning the original values, output them as a comma-separated list enclosed in <original_examples>...</original_examples> tags.

	Example Output for Synthetic Values:
	<synthetic_examples>Fake Name 1, Fake Name 2, Fake Name 3</synthetic_examples>

	Example Output for Original Values:
	<original_examples>Value 1, Value 2, Value 3</original_examples>

	Now, analyze the column and provide the appropriate output.
`, colInfo.Name, tableName, dataTypeDescription, exampleValuesStr, colInfo.Name, dataTypeDescription)

	client, err := genai.NewClient(ctx, option.WithAPIKey(mc.GeminiAPIKey))
	if err != nil {
		return nil, fmt.Errorf("failed to create Gemini client: %w", err)
	}
	defer client.Close()

	model_name := mc.Model
	if model_name == "" {
		model_name = "gemini-1.5-pro-002"
	}
	model := client.GenerativeModel(model_name)
	model.SetTemperature(0.4)
	model.SetMaxOutputTokens(500)
	model.SetTopP(0.8)
	model.SetTopK(40)

	resp, err := model.GenerateContent(ctx, genai.Text(prompt))
	if err != nil {
		return nil, fmt.Errorf("Gemini API call failed for example value generation: %w", err)
	}

	responseString, err := extractTextFromResponseForExampleValues(resp)
	if err != nil {
		return nil, err
	}

	var exampleValues []string
	if strings.Contains(responseString, "<synthetic_examples>") {
		startTag := "<synthetic_examples>"
		endTag := "</synthetic_examples>"
		startIndex := strings.Index(responseString, startTag)
		endIndex := strings.Index(responseString, endTag)
		if startIndex != -1 && endIndex != -1 && startIndex < endIndex {
			syntheticValueString := responseString[startIndex+len(startTag) : endIndex]
			exampleValues = strings.Split(syntheticValueString, ",")
			for i := range exampleValues {
				exampleValues[i] = strings.TrimSpace(exampleValues[i])
			}
			log.Printf("INFO: Gemini determined column '%s' table '%s' is PII and generated synthetic examples.", colInfo.Name, tableName)
		} else {
			return nil, fmt.Errorf("invalid response format for synthetic examples from Gemini: tags not found")
		}
	} else if strings.Contains(responseString, "<original_examples>") {
		startTag := "<original_examples>"
		endTag := "</original_examples>"
		startIndex := strings.Index(responseString, startTag)
		endIndex := strings.Index(responseString, endTag)
		if startIndex != -1 && endIndex != -1 && startIndex < endIndex {
			originalValueString := responseString[startIndex+len(startTag) : endIndex]
			exampleValues = strings.Split(originalValueString, ",")
			for i := range exampleValues {
				exampleValues[i] = strings.TrimSpace(exampleValues[i])
			}
		} else {
			return nil, fmt.Errorf("invalid response format for original examples from Gemini: tags not found")
		}
	} else {
		return nil, fmt.Errorf("unexpected response format from Gemini for example values: %s", responseString)
	}
	return exampleValues, nil
}

// Helper function to extract text
func extractTextFromResponse(resp *genai.GenerateContentResponse) (string, error) {
	if len(resp.Candidates) == 0 || len(resp.Candidates[0].Content.Parts) == 0 {
		return "", fmt.Errorf("empty response from Gemini API")
	}

	// Safely access and return the text
	if textPart, ok := resp.Candidates[0].Content.Parts[0].(genai.Text); ok {

		// Extract the text between <result> tags
		resp := strings.TrimSpace(string(textPart))
		if idx1 := strings.LastIndex(resp, "<result>"); idx1 != -1 {
			if idx2 := strings.Index(resp[idx1+len("<result>"):], "</result>"); idx2 != -1 {
				resp = resp[idx1+len("<result>") : idx1+len("<result>")+idx2]
			} else {
				return "", nil
			}
		} else {
			return "", nil
		}

		return resp, nil
	}

	return "", fmt.Errorf("unexpected response format from Gemini API: %+v", resp)
}

func extractTextFromResponseForExampleValues(resp *genai.GenerateContentResponse) (string, error) {
	if len(resp.Candidates) == 0 {
		return "", fmt.Errorf("no candidates in response")
	}
	part := resp.Candidates[0].Content.Parts[0]
	text, ok := part.(genai.Text)
	if !ok {
		return "", fmt.Errorf("unexpected response type: %T", part)
	}
	return string(text), nil
}

// generateSchemaContext generates a string representation of the database schema.
func (mc *MetadataCollector) generateSchemaContext() (string, error) {
	tables, err := mc.db.ListTables()
	if err != nil {
		return "", fmt.Errorf("failed to list tables for schema context: %w", err)
	}

	var schemaContext strings.Builder
	schemaContext.WriteString("Tables:\n")
	for _, table := range tables {
		columns, err := mc.db.ListColumns(table)
		if err != nil {
			log.Printf("WARN: Failed to list columns for table %s in schema context: %v", table, err)
			continue
		}
		schemaContext.WriteString(fmt.Sprintf("- %s: [", table))
		columnNames := []string{}
		for _, col := range columns {
			columnNames = append(columnNames, col.Name)
		}
		schemaContext.WriteString(strings.Join(columnNames, ", "))
		schemaContext.WriteString("]\n")
	}
	return schemaContext.String(), nil
}

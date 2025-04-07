// File: internal/enricher/enricher.go
package enricher

import (
	"bytes"
	"context"
	"fmt"
	"log"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/genai"
)

type Service struct {
	dbAdapter database.DBAdapter
	llmClient genai.LLMClient
}

type Config struct {
}

func NewService(db database.DBAdapter, llm genai.LLMClient, cfg Config) *Service {
	return &Service{
		dbAdapter: db,
		llmClient: llm,
	}
}

type GenerateSQLParams struct {
	TableFilters      map[string][]string
	Enrichments       map[string]bool
	AdditionalContext string
}

func (s *Service) GenerateCommentSQLs(ctx context.Context, params GenerateSQLParams) ([]string, error) {
	startTime := time.Now()
	log.Println("INFO: Starting metadata collection and SQL comment generation...")

	tables, err := s.dbAdapter.ListTables()
	if err != nil {
		return nil, fmt.Errorf("failed to list tables: %w", err)
	}

	filteredTables := filterTables(tables, params.TableFilters)
	if len(filteredTables) == 0 {
		log.Println("INFO: No tables match the provided filters (--tables).")
		return []string{}, nil
	}

	var orderedSQLs []OrderedSQL
	var wg sync.WaitGroup
	var mu sync.Mutex
	errorChannel := make(chan error, len(filteredTables)*5) // Buffer size can be adjusted

	log.Printf("INFO: Processing %d filtered table(s)...", len(filteredTables))

	for _, tableName := range filteredTables {
		wg.Add(1)
		go func(table string) {
			defer wg.Done()
			tableLogPrefix := fmt.Sprintf("Table[%s]", table)

			tableMetadata := &TableMetadata{Table: table}
			if s.llmClient != nil && isEnrichmentRequested("description", params.Enrichments) {
				desc, descErr := s.llmClient.GenerateDescription(ctx, "table", table, "", params.AdditionalContext)
				if descErr != nil {
					log.Printf("WARN: %s Failed to generate table description via LLM: %v", tableLogPrefix, descErr)
				} else if desc != "" {
					tableMetadata.Description = desc
				}
			}

			tableCommentData := &database.TableCommentData{
				TableName:   tableMetadata.Table,
				Description: tableMetadata.Description,
			}
			tableSQL, genTableErr := s.dbAdapter.GenerateTableCommentSQL(tableCommentData, params.Enrichments)
			if genTableErr != nil {
				log.Printf("WARN: %s Failed to generate table comment SQL: %v", tableLogPrefix, genTableErr)
			} else if tableSQL != "" {
				mu.Lock()
				orderedSQLs = append(orderedSQLs, OrderedSQL{SQL: tableSQL, Table: table, IsTableComment: true})
				mu.Unlock()
			}

			columnInfos, listColErr := s.dbAdapter.ListColumns(table)
			if listColErr != nil {
				log.Printf("ERROR: %s Failed to list columns: %v", tableLogPrefix, listColErr)
				errorChannel <- fmt.Errorf("%s list columns: %w", tableLogPrefix, listColErr)
				return
			}
			filteredColumnInfos := filterColumns(table, columnInfos, params.TableFilters)

			var colWg sync.WaitGroup
			for _, colInfo := range filteredColumnInfos {
				colWg.Add(1)
				go func(ci database.ColumnInfo) {
					defer colWg.Done()
					colLogPrefix := fmt.Sprintf("Column[%s.%s]", table, ci.Name)

					columnMetadata, colMetaErr := s.collectColumnDBMetadata(ctx, table, ci, params.Enrichments)
					if colMetaErr != nil {
						log.Printf("ERROR: %s Failed to collect DB metadata: %v", colLogPrefix, colMetaErr)
						errorChannel <- fmt.Errorf("%s collect DB meta: %w", colLogPrefix, colMetaErr)
						return
					}

					if s.llmClient != nil {
						// PII Check / Example Synthesis
						if isEnrichmentRequested("examples", params.Enrichments) && len(columnMetadata.ExampleValues) > 0 {
							processedExamples, wasSynthesized, piiErr := s.llmClient.GenerateSyntheticExamples(ctx, ci.Name, table, ci.DataType, columnMetadata.ExampleValues)

							if piiErr != nil {
								log.Printf("WARN: %s Failed to process example values with LLM: %v. Using original examples.", colLogPrefix, piiErr)
							} else {
								if wasSynthesized {
									log.Printf("INFO: %s Used synthetic examples (PII detected/suspected).", colLogPrefix)
								}
								columnMetadata.ExampleValues = processedExamples
							}
						}

						// Description Generation
						if isEnrichmentRequested("description", params.Enrichments) {
							desc, descErr := s.llmClient.GenerateDescription(ctx, "column", ci.Name, table, params.AdditionalContext)
							if descErr != nil {
								log.Printf("WARN: %s Failed to generate column description via LLM: %v", colLogPrefix, descErr)
							} else if desc != "" {
								columnMetadata.Description = desc
							}
						}
					}

					commentData := &database.CommentData{
						TableName:      columnMetadata.Table,
						ColumnName:     columnMetadata.Column,
						ColumnDataType: columnMetadata.DataType,
						ExampleValues:  columnMetadata.ExampleValues,
						DistinctCount:  columnMetadata.DistinctCount,
						NullCount:      columnMetadata.NullCount,
						Description:    columnMetadata.Description,
					}
					sql, genErr := s.dbAdapter.GenerateCommentSQL(commentData, params.Enrichments)
					if genErr != nil {
						log.Printf("WARN: %s Failed to generate comment SQL: %v", colLogPrefix, genErr)
					} else if sql != "" {
						mu.Lock()
						orderedSQLs = append(orderedSQLs, OrderedSQL{SQL: sql, Table: table, Column: ci.Name, IsTableComment: false})
						mu.Unlock()
					}
				}(colInfo)
			}
			colWg.Wait()

		}(tableName)
	}

	wg.Wait()
	close(errorChannel)

	var allErrors []error
	for err := range errorChannel {
		allErrors = append(allErrors, err)
	}
	if len(allErrors) > 0 {
		errorMessages := make([]string, len(allErrors))
		for i, e := range allErrors {
			errorMessages[i] = e.Error()
		}
		return nil, fmt.Errorf("encountered %d error(s) during SQL generation:\n- %s",
			len(allErrors), strings.Join(errorMessages, "\n- "))
	}

	sortSQLs(orderedSQLs)
	allSQLs := extractSQL(orderedSQLs)

	log.Printf("INFO: SQL comment generation completed in %s. Generated %d statements.", time.Since(startTime), len(allSQLs))
	return allSQLs, nil
}

func (s *Service) collectColumnDBMetadata(ctx context.Context, tableName string, colInfo database.ColumnInfo, enrichments map[string]bool) (*ColumnMetadata, error) {

	metadata := &ColumnMetadata{
		Table:    tableName,
		Column:   colInfo.Name,
		DataType: colInfo.DataType,
	}

	needsDBQuery := isEnrichmentRequested("examples", enrichments) ||
		isEnrichmentRequested("distinct_values", enrichments) ||
		isEnrichmentRequested("null_count", enrichments)

	if !needsDBQuery {
		return metadata, nil
	}

	dbMetadata, err := s.dbAdapter.GetColumnMetadata(tableName, colInfo.Name)
	if err != nil {
		return nil, fmt.Errorf("get column DB metadata for %s.%s: %w", tableName, colInfo.Name, err)
	}

	if isEnrichmentRequested("examples", enrichments) {
		if examplesRaw, ok := dbMetadata["ExampleValues"]; ok {
			if ev, okCast := examplesRaw.([]string); okCast {
				metadata.ExampleValues = ev
			} else {
				log.Printf("WARN: Column[%s.%s] Unexpected type for ExampleValues from DB: %T", tableName, colInfo.Name, examplesRaw)
			}
		}
	}

	if isEnrichmentRequested("distinct_values", enrichments) {
		if dcRaw, ok := dbMetadata["DistinctCount"]; ok {
			metadata.DistinctCount = safeConvertToInt64(dcRaw)
		}
	}

	if isEnrichmentRequested("null_count", enrichments) {
		if ncRaw, ok := dbMetadata["NullCount"]; ok {
			metadata.NullCount = safeConvertToInt64(ncRaw)
		}
	}

	return metadata, nil
}

type GenerateDeleteSQLParams struct {
	TableFilters map[string][]string
}

func (s *Service) GenerateDeleteCommentSQLs(ctx context.Context, params GenerateDeleteSQLParams) ([]string, error) {
	startTime := time.Now()
	log.Println("INFO: Starting SQL comment deletion generation...")

	tables, err := s.dbAdapter.ListTables()
	if err != nil {
		return nil, fmt.Errorf("failed to list tables: %w", err)
	}

	filteredTables := filterTables(tables, params.TableFilters)
	if len(filteredTables) == 0 {
		log.Println("INFO: No tables match the provided filters (--tables) for deletion.")
		return []string{}, nil
	}

	var orderedSQLs []OrderedSQL
	var wg sync.WaitGroup
	var mu sync.Mutex
	errorChannel := make(chan error, len(filteredTables)*5)

	log.Printf("INFO: Processing %d filtered table(s) for deletion...", len(filteredTables))

	for _, tableName := range filteredTables {
		wg.Add(1)
		go func(table string) {
			defer wg.Done()
			tableLogPrefix := fmt.Sprintf("Table[%s]", table)

			// Direct call, no retry
			tableSQL, genTableErr := s.dbAdapter.GenerateDeleteTableCommentSQL(ctx, table)
			if genTableErr != nil {
				log.Printf("WARN: %s Failed to generate delete table comment SQL: %v", tableLogPrefix, genTableErr)
			} else if tableSQL != "" {
				mu.Lock()
				orderedSQLs = append(orderedSQLs, OrderedSQL{SQL: tableSQL, Table: table, IsTableComment: true})
				mu.Unlock()
			}

			columnInfos, listColErr := s.dbAdapter.ListColumns(table)
			if listColErr != nil {
				log.Printf("ERROR: %s Failed to list columns for delete: %v", tableLogPrefix, listColErr)
				errorChannel <- fmt.Errorf("%s list columns delete: %w", tableLogPrefix, listColErr)
				return
			}
			filteredColumnInfos := filterColumns(table, columnInfos, params.TableFilters)

			var colWg sync.WaitGroup
			for _, colInfo := range filteredColumnInfos {
				colWg.Add(1)
				go func(ci database.ColumnInfo) {
					defer colWg.Done()
					colLogPrefix := fmt.Sprintf("Column[%s.%s]", table, ci.Name)

					// Direct call, no retry
					sql, genErr := s.dbAdapter.GenerateDeleteCommentSQL(ctx, table, ci.Name)
					if genErr != nil {
						log.Printf("WARN: %s Failed to generate delete comment SQL: %v", colLogPrefix, genErr)
					} else if sql != "" {
						mu.Lock()
						orderedSQLs = append(orderedSQLs, OrderedSQL{SQL: sql, Table: table, Column: ci.Name, IsTableComment: false})
						mu.Unlock()
					}
				}(colInfo)
			}
			colWg.Wait()

		}(tableName)
	}

	wg.Wait()
	close(errorChannel)

	var allErrors []error
	for err := range errorChannel {
		allErrors = append(allErrors, err)
	}
	if len(allErrors) > 0 {
		errorMessages := make([]string, len(allErrors))
		for i, e := range allErrors {
			errorMessages[i] = e.Error()
		}
		return nil, fmt.Errorf("encountered %d error(s) during delete SQL generation:\n- %s",
			len(allErrors), strings.Join(errorMessages, "\n- "))
	}

	sortSQLs(orderedSQLs)
	allSQLs := extractSQL(orderedSQLs)

	if len(allSQLs) == 0 {
		log.Println("INFO: No SQL statements generated for deleting comments (no matching tables/columns or no relevant tags found).")
	} else {
		log.Printf("INFO: Generated %d SQL statements for deleting comments.", len(allSQLs))
	}
	log.Println("INFO: SQL comment deletion generation completed in:", time.Since(startTime))
	return allSQLs, nil
}

type GetCommentsParams struct {
	TableFilters map[string][]string
}

func (s *Service) GetComments(ctx context.Context, params GetCommentsParams) ([]*ColumnComment, error) {
	startTime := time.Now()
	log.Println("INFO: Starting comment retrieval...")

	tables, err := s.dbAdapter.ListTables()
	if err != nil {
		return nil, fmt.Errorf("failed to list tables: %w", err)
	}

	filteredTables := filterTables(tables, params.TableFilters)
	if len(filteredTables) == 0 {
		log.Println("INFO: No tables match the provided filters (--tables) for retrieval.")
		return []*ColumnComment{}, nil
	}

	var allComments []*ColumnComment
	var wg sync.WaitGroup
	var mu sync.Mutex
	errorChannel := make(chan error, len(filteredTables)*5)

	log.Printf("INFO: Retrieving comments for %d filtered table(s)...", len(filteredTables))

	for _, tableName := range filteredTables {
		wg.Add(1)
		go func(table string) {
			defer wg.Done()
			tableLogPrefix := fmt.Sprintf("Table[%s]", table)

			tableComment, err := s.dbAdapter.GetTableComment(ctx, table)
			if err != nil {
				log.Printf("WARN: %s Failed to get table comment: %v", tableLogPrefix, err)
			} else if tableComment != "" {
				mu.Lock()
				allComments = append(allComments, &ColumnComment{
					Table:   table,
					Column:  "",
					Comment: tableComment,
				})
				mu.Unlock()
			}

			columnInfos, listColErr := s.dbAdapter.ListColumns(table)
			if listColErr != nil {
				log.Printf("ERROR: %s Failed to list columns for get comments: %v", tableLogPrefix, listColErr)
				errorChannel <- fmt.Errorf("%s list columns get: %w", tableLogPrefix, listColErr)
				return
			}
			filteredColumnInfos := filterColumns(table, columnInfos, params.TableFilters)

			var colWg sync.WaitGroup
			for _, colInfo := range filteredColumnInfos {
				colWg.Add(1)
				go func(ci database.ColumnInfo) {
					defer colWg.Done()
					colLogPrefix := fmt.Sprintf("Column[%s.%s]", table, ci.Name)

					// Direct call, no retry
					comment, err := s.dbAdapter.GetColumnComment(ctx, table, ci.Name)
					if err != nil {
						log.Printf("WARN: %s Failed to get column comment: %v", colLogPrefix, err)
					} else if comment != "" {
						mu.Lock()
						allComments = append(allComments, &ColumnComment{
							Table:   table,
							Column:  ci.Name,
							Comment: comment,
						})
						mu.Unlock()
					}
				}(colInfo)
			}
			colWg.Wait()

		}(tableName)
	}

	wg.Wait()
	close(errorChannel)

	var allErrors []error
	for err := range errorChannel {
		allErrors = append(allErrors, err)
	}
	if len(allErrors) > 0 {
		errorMessages := make([]string, len(allErrors))
		for i, e := range allErrors {
			errorMessages[i] = e.Error()
		}
		aggError := fmt.Errorf("encountered %d error(s) during comment retrieval:\n- %s",
			len(allErrors), strings.Join(errorMessages, "\n- "))
		sortComments(allComments)
		return allComments, aggError
	}

	sortComments(allComments)

	log.Printf("INFO: Comment retrieval completed in %s. Found %d comments.", time.Since(startTime), len(allComments))
	return allComments, nil
}

// generateSchemaContext generates a string representation of the filtered database schema.
func (s *Service) generateSchemaContext(filteredTables []string, tableFilters map[string][]string) (string, error) {
	if s.dbAdapter == nil {
		return "", fmt.Errorf("database connection not available for generating schema context")
	}

	var schemaContext strings.Builder
	schemaContext.WriteString("Schema Context:\n")
	if len(filteredTables) == 0 {
		schemaContext.WriteString(" (No tables specified or found based on filters)\n")
		return schemaContext.String(), nil
	}

	schemaContext.WriteString("Tables and Columns (based on filters):\n")
	for _, table := range filteredTables {
		columns, err := s.dbAdapter.ListColumns(table)
		if err != nil {
			log.Printf("WARN: Failed to list columns for table %s in schema context: %v", table, err)
			schemaContext.WriteString(fmt.Sprintf("- %s: [Error fetching columns: %v]\n", table, err))
			continue
		}

		filteredColumns := filterColumns(table, columns, tableFilters)

		schemaContext.WriteString(fmt.Sprintf("- %s: [", table))
		if len(filteredColumns) > 0 {
			columnNames := make([]string, len(filteredColumns))
			for i, col := range filteredColumns {
				columnNames[i] = fmt.Sprintf("%s(%s)", col.Name, col.DataType)
			}
			schemaContext.WriteString(strings.Join(columnNames, ", "))
		} else {
			schemaContext.WriteString("(No columns specified by filters)")
		}
		schemaContext.WriteString("]\n")
	}
	return schemaContext.String(), nil
}

func filterTables(allTables []string, tableFilters map[string][]string) []string {
	if len(tableFilters) == 0 {
		return allTables
	}
	filtered := make([]string, 0, len(tableFilters))
	allowed := make(map[string]bool)
	for table := range tableFilters {
		allowed[table] = true
	}
	for _, table := range allTables {
		if allowed[table] {
			filtered = append(filtered, table)
		}
	}
	sort.Strings(filtered)
	return filtered
}

func filterColumns(tableName string, allColumns []database.ColumnInfo, tableFilters map[string][]string) []database.ColumnInfo {
	if len(tableFilters) == 0 {
		return allColumns
	}
	specificColumnFilters, tableIncluded := tableFilters[tableName]
	if !tableIncluded || len(specificColumnFilters) == 0 {
		return allColumns
	}
	filtered := make([]database.ColumnInfo, 0, len(specificColumnFilters))
	allowed := make(map[string]bool)
	for _, colName := range specificColumnFilters {
		allowed[colName] = true
	}
	for _, colInfo := range allColumns {
		if allowed[colInfo.Name] {
			filtered = append(filtered, colInfo)
		}
	}
	sort.Slice(filtered, func(i, j int) bool {
		return filtered[i].Name < filtered[j].Name
	})
	return filtered
}

func isEnrichmentRequested(enrichment string, enrichments map[string]bool) bool {
	if len(enrichments) == 0 {
		return true
	}
	return enrichments[strings.ToLower(enrichment)]
}

func safeConvertToInt64(value interface{}) int64 {
	switch v := value.(type) {
	case int:
		return int64(v)
	case int32:
		return int64(v)
	case int64:
		return v
	case float32:
		return int64(v)
	case float64:
		return int64(v)
	default:
		log.Printf("WARN: Could not convert value of type %T to int64", value)
		return 0
	}
}

func sortSQLs(sqls []OrderedSQL) {
	sort.Slice(sqls, func(i, j int) bool {
		if sqls[i].Table != sqls[j].Table {
			return sqls[i].Table < sqls[j].Table
		}
		if sqls[i].IsTableComment != sqls[j].IsTableComment {
			return sqls[i].IsTableComment // Table comments first
		}
		return sqls[i].Column < sqls[j].Column
	})
}

func extractSQL(orderedSQLs []OrderedSQL) []string {
	allSQLs := make([]string, len(orderedSQLs))
	for i, osql := range orderedSQLs {
		allSQLs[i] = osql.SQL
	}
	return allSQLs
}

func sortComments(comments []*ColumnComment) {
	sort.Slice(comments, func(i, j int) bool {
		if comments[i].Table != comments[j].Table {
			return comments[i].Table < comments[j].Table
		}
		if comments[i].Column == "" {
			return true
		}
		if comments[j].Column == "" {
			return false
		}
		return comments[i].Column < comments[j].Column
	})
}

// --- Types ---

type ColumnMetadata struct {
	Table         string
	Column        string
	DataType      string
	ExampleValues []string
	DistinctCount int64
	NullCount     int64
	Description   string
}

type TableMetadata struct {
	Table       string
	Description string
}

type OrderedSQL struct {
	SQL            string
	Table          string
	Column         string
	IsTableComment bool
}

type ColumnComment struct {
	Table   string `json:"table"`
	Column  string `json:"column"`
	Comment string `json:"comment"`
}

func FormatCommentsAsText(comments []*ColumnComment) string {
	if len(comments) == 0 {
		return "No comments found.\n"
	}
	var buffer bytes.Buffer
	lastTable := ""
	for _, comment := range comments {
		if comment.Table != lastTable {
			if lastTable != "" {
				buffer.WriteString("\n")
			}
			buffer.WriteString(fmt.Sprintf("--- Table: %s ---\n", comment.Table))
			lastTable = comment.Table
		}

		if comment.Column == "" {
			buffer.WriteString(fmt.Sprintf("  [Table Comment]: %s\n", strings.TrimSpace(comment.Comment)))
		} else {
			buffer.WriteString(fmt.Sprintf("  Column: %s\n", comment.Column))
			buffer.WriteString(fmt.Sprintf("  Comment: %s\n", strings.TrimSpace(comment.Comment)))
		}
	}
	return buffer.String()
}

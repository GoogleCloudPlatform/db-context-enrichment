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
	"encoding/json"
	"fmt"
	"log"
	"os"
	"sync"
	"time"

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
)

// MetadataCollector collects metadata and applies comments.
type MetadataCollector struct {
	db        *database.DB      // Database connection
	retryOpts *RetryOptions     // Retry configuration
	DryRun    bool              // Dry run mode flag
	Metadata  []*ColumnMetadata // Collected metadata
	mu        sync.Mutex        // Mutex to protect Metadata slice
}

// NewMetadataCollector creates a new MetadataCollector instance.
func NewMetadataCollector(db *database.DB, retryOpts *RetryOptions, dryRun bool) *MetadataCollector {
	return &MetadataCollector{
		db:        db,
		retryOpts: retryOpts,
		DryRun:    dryRun,
		Metadata:  []*ColumnMetadata{},
	}
}

// CollectColumnMetadata gathers comprehensive metadata for a specific database column.
func (mc *MetadataCollector) CollectColumnMetadata(ctx context.Context, tableName string, colInfo database.ColumnInfo) (*ColumnMetadata, error) {
	if tableName == "" || colInfo.Name == "" {
		return nil, &ErrInvalidInput{
			Msg: "table name and column name cannot be empty",
		}
	}

	dbMetadata, err := mc.db.GetColumnMetadata(tableName, colInfo.Name)
	if err != nil {
		return nil, &ErrQueryExecution{
			Msg: "failed to get column metadata",
			Err: err,
		}
	}

	exampleValues, ok := dbMetadata["ExampleValues"].([]string)
	if !ok {
		return nil, fmt.Errorf("unexpected type for ExampleValues: %T, expected []string", dbMetadata["ExampleValues"])
	}

	distinctCountFloat, ok := dbMetadata["DistinctCount"].(int)
	if !ok {
		return nil, fmt.Errorf("unexpected type for DistinctCount: %T, expected int", dbMetadata["DistinctCount"])
	}
	distinctCount := int64(distinctCountFloat)

	nullCountFloat, ok := dbMetadata["NullCount"].(int)
	if !ok {
		return nil, fmt.Errorf("unexpected type for NullCount: %T, expected int", dbMetadata["NullCount"])
	}
	nullCount := int64(nullCountFloat)

	fks, err := mc.db.GetForeignKeys(tableName, colInfo.Name)
	if err != nil {
		log.Printf("WARN: Failed to detect foreign keys for table: %s, column: %s, error: %v", tableName, colInfo.Name, err)
		fks = []database.ForeignKeyInfo{} // Proceed without foreign keys
	}

	metadata := &ColumnMetadata{
		Table:         tableName,
		Column:        colInfo.Name,
		DataType:      colInfo.DataType,
		ExampleValues: exampleValues,
		DistinctCount: distinctCount,
		NullCount:     nullCount,
		ForeignKeys:   fks,
	}

	return metadata, nil
}

// ApplyComments executes the generated comment SQL statements.
func (mc *MetadataCollector) ApplyComments(ctx context.Context, metadataList []*ColumnMetadata) ([]string, error) {
	if len(metadataList) == 0 {
		log.Println("INFO: No metadata to apply comments for.")
		return []string{}, nil
	}

	var generatedSQLs []string
	var appliedCount int
	var wg sync.WaitGroup
	errorChannel := make(chan error, len(metadataList)) // Buffered channel for errors
	sqlChannel := make(chan string, len(metadataList))  // Buffered channel

	log.Println("INFO: Applying comments to columns...")

	for _, col := range metadataList {
		wg.Add(1)
		go func(col *ColumnMetadata) {
			defer wg.Done()

			commentData := &database.CommentData{
				TableName:      col.Table,
				ColumnName:     col.Column,
				ColumnDataType: col.DataType,
				ExampleValues:  col.ExampleValues,
				DistinctCount:  col.DistinctCount,
				NullCount:      col.NullCount,
				ForeignKeys:    col.ForeignKeys,
			}
			sql, err := mc.db.GenerateCommentSQL(commentData)
			if err != nil {
				log.Printf("WARN: Failed to generate comment SQL for %s.%s: %v", col.Table, col.Column, err)
				errorChannel <- err // Send error to the channel
				return
			}

			if mc.DryRun {
				log.Printf("INFO: Dry-run mode: Would not execute comment SQL for table: %s, column: %s", col.Table, col.Column)
				sqlChannel <- sql // Collect even in dry-run
				return
			}

			_, execErr := mc.db.ExecContext(ctx, sql)
			if execErr != nil {
				log.Printf("ERROR: Failed to apply comment for table: %s, column: %s, error: %v", col.Table, col.Column, execErr)
				errorChannel <- execErr // Send error to the channel
				return
			}
			log.Println("INFO: Successfully updated column comment for table:", col.Table, "column:", col.Column)
			sqlChannel <- sql
			appliedCount++
		}(col)
	}

	wg.Wait()         // Wait for all goroutines to finish
	close(sqlChannel) // Close the channel to signal completion
	close(errorChannel)

	for sql := range sqlChannel {
		generatedSQLs = append(generatedSQLs, sql)
	}

	// Check for errors
	for err := range errorChannel {
		if err != nil {
			return generatedSQLs, fmt.Errorf("one or more errors occurred while applying comments: %w", err)
		}
	}

	log.Printf("INFO: Applied comments to %d columns.", appliedCount)
	log.Println("INFO: Finished processing metadata comments.")
	return generatedSQLs, nil
}

// CollectAndApplyMetadata collects metadata for all tables and columns and applies comments.
func (mc *MetadataCollector) CollectAndApplyMetadata(ctx context.Context) ([]string, error) {
	startTime := time.Now()
	log.Println("INFO: Starting metadata collection and comment application process...")

	tables, err := mc.db.ListTables()
	if err != nil {
		return nil, fmt.Errorf("failed to list tables: %w", err)
	}

	var wg sync.WaitGroup
	errorChannel := make(chan error, len(tables)) // Buffered channel for errors

	for _, table := range tables {
		wg.Add(1)
		go func(table string) {
			defer wg.Done()

			columnInfos, err := mc.db.ListColumns(table)
			if err != nil {
				log.Println("ERROR: Failed to list columns for table:", table, "error:", err)
				errorChannel <- err // Send error to channel
				return
			}

			for _, colInfo := range columnInfos {
				wg.Add(1)
				go func(colInfo database.ColumnInfo) {
					defer wg.Done()
					metadata, err := withRetry[*ColumnMetadata](ctx, DefaultRetryOptions, func(ctx context.Context) (*ColumnMetadata, error) {
						return mc.CollectColumnMetadata(ctx, table, colInfo)
					})
					if err != nil {
						log.Println("ERROR: Failed to collect metadata for column:", colInfo.Name, "in table:", table, "error:", err)
						errorChannel <- err
						return
					}

					mc.mu.Lock()
					mc.Metadata = append(mc.Metadata, metadata)
					mc.mu.Unlock()

				}(colInfo)
			}
		}(table)
	}

	wg.Wait()
	close(errorChannel)

	// Collect errors from the error channel
	var combinedErr error
	for err := range errorChannel {
		if err != nil {
			if combinedErr == nil {
				combinedErr = err
			} else {
				combinedErr = fmt.Errorf("%w; %v", combinedErr, err) // Accumulate errors
			}
		}
	}
	if combinedErr != nil {
		return nil, combinedErr // Return if any errors occurred
	}

	log.Println("INFO: Metadata collection completed in:", time.Since(startTime))

	generatedSQLs, applyErr := mc.ApplyComments(ctx, mc.Metadata)
	if applyErr != nil {
		return nil, fmt.Errorf("failed to apply comments: %w", applyErr)
	}

	totalDuration := time.Since(startTime)
	log.Println("INFO: Metadata collection and comment application completed in:", totalDuration)

	return generatedSQLs, nil
}

// GenerateCommentSQLs collects metadata and generates SQL statements, no application.
func (mc *MetadataCollector) GenerateCommentSQLs(ctx context.Context) ([]string, error) {
	startTime := time.Now()
	log.Println("INFO: Starting metadata collection and SQL comment generation...")

	tables, err := mc.db.ListTables()
	if err != nil {
		return nil, fmt.Errorf("failed to list tables: %w", err)
	}

	var allSQLs []string
	var wg sync.WaitGroup
	errorChannel := make(chan error, len(tables))

	for _, table := range tables {
		wg.Add(1)
		go func(table string) {
			defer wg.Done()

			columnInfos, err := mc.db.ListColumns(table)
			if err != nil {
				log.Println("ERROR: Failed to list columns for table:", table, "error:", err)
				errorChannel <- err
				return
			}

			for _, colInfo := range columnInfos {
				wg.Add(1)
				go func(colInfo database.ColumnInfo) {
					defer wg.Done()

					metadata, err := withRetry[*ColumnMetadata](ctx, DefaultRetryOptions, func(ctx context.Context) (*ColumnMetadata, error) {
						return mc.CollectColumnMetadata(ctx, table, colInfo)
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
						ForeignKeys:    metadata.ForeignKeys,
					}
					sql, genErr := mc.db.GenerateCommentSQL(commentData)
					if genErr != nil {
						log.Printf("WARN: Failed to generate comment SQL for %s.%s: %v", metadata.Table, metadata.Column, genErr)
						errorChannel <- genErr
						return
					}
					mc.mu.Lock()
					allSQLs = append(allSQLs, sql)
					mc.mu.Unlock()
				}(colInfo)
			}
		}(table)
	}

	wg.Wait()
	close(errorChannel)

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

	var allSQLs []string
	var wg sync.WaitGroup
	errorChannel := make(chan error, len(tables))

	for _, table := range tables {
		wg.Add(1)
		go func(table string) {
			defer wg.Done()

			columnInfos, err := mc.db.ListColumns(table)
			if err != nil {
				log.Println("ERROR: Failed to list columns for table:", table, "error:", err)
				errorChannel <- err
				return
			}

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

// GetComments retrieves all column comments.
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
	for _, comment := range comments {
		buffer.WriteString(fmt.Sprintf("Table: %s, Column: %s\n", comment.Table, comment.Column))
		buffer.WriteString(fmt.Sprintf("Comment: %s\n", comment.Comment))
		buffer.WriteString("\n") // Add an empty line
	}
	return buffer.String()
}

// FormatCommentsAsJSON formats the comments as JSON.
func FormatCommentsAsJSON(comments []*ColumnComment) (string, error) {
	jsonBytes, err := json.MarshalIndent(comments, "", "  ")
	if err != nil {
		return "", fmt.Errorf("failed to marshal comments to JSON: %w", err)
	}
	return string(jsonBytes), nil
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

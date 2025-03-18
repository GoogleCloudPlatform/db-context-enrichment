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
package mysql

import (
	"context"
	"database/sql"
	"fmt"
	"net"
	"os"
	"strings"

	"cloud.google.com/go/cloudsqlconn"
	"github.com/go-sql-driver/mysql"
	"github.com/lib/pq"

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/config"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
)

// mysqlHandler struct implements database.DialectHandler for MySQL.
type mysqlHandler struct{}

var _ database.DialectHandler = (*mysqlHandler)(nil)

// CreateCloudSQLPool for MySQL
func (h mysqlHandler) CreateCloudSQLPool(cfg config.DatabaseConfig) (*sql.DB, error) {
	mustGetenv := func(k string, cfg config.DatabaseConfig) string {
		v := ""
		switch k {
		case "user_name":
			v = cfg.User
		case "password":
			v = cfg.Password
		case "database_name":
			v = cfg.DBName
		case "instance_name":
			v = cfg.CloudSQLInstanceConnectionName
		case "PRIVATE_IP":
			if cfg.UsePrivateIP {
				v = "true"
			}
		}
		if v == "" {
			return os.Getenv(k)
		}
		return v
	}

	dbUser := mustGetenv("user_name", cfg)
	dbPwd := mustGetenv("password", cfg)
	dbName := mustGetenv("database_name", cfg)
	instanceConnectionName := mustGetenv("instance_name", cfg)
	usePrivate := mustGetenv("PRIVATE_IP", cfg)

	d, err := cloudsqlconn.NewDialer(context.Background())
	if err != nil {
		return nil, fmt.Errorf("cloudsqlconn.NewDialer: %w", err)
	}
	var opts []cloudsqlconn.DialOption
	if usePrivate != "" && strings.ToLower(usePrivate) != "false" && usePrivate != "0" {
		opts = append(opts, cloudsqlconn.WithPrivateIP())
	}

	mysql.RegisterDialContext("cloudsqlconn",
		func(ctx context.Context, addr string) (net.Conn, error) {
			return d.Dial(ctx, instanceConnectionName, opts...)
		})

	dbURI := fmt.Sprintf("%s:%s@cloudsqlconn(localhost:3306)/%s?parseTime=true",
		dbUser, dbPwd, dbName)

	dbPool, err := sql.Open("mysql", dbURI)
	if err != nil {
		return nil, fmt.Errorf("sql.Open: %w", err)
	}
	return dbPool, nil
}

// CreateStandardPool creates a standard MySQL connection pool
func (h mysqlHandler) CreateStandardPool(cfg config.DatabaseConfig) (*sql.DB, error) {
	connStr := fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?parseTime=true",
		cfg.User, cfg.Password, cfg.Host, cfg.Port, cfg.DBName)

	dbPool, err := sql.Open("mysql", connStr)
	if err != nil {
		return nil, fmt.Errorf("sql.Open (standard mysql): %w", err)
	}
	return dbPool, err
}

// QuoteIdentifier for MySQL
func (h mysqlHandler) QuoteIdentifier(name string) string {
	return fmt.Sprintf("`%s`", name)
}

// ListTables for MySQL
func (h mysqlHandler) ListTables(db *database.DB) ([]string, error) {
	query := "SHOW TABLES"

	rows, err := db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("error querying tables: %w", err)
	}
	defer rows.Close()

	var tables []string
	for rows.Next() {
		var tableName string
		if err := rows.Scan(&tableName); err != nil {
			return nil, fmt.Errorf("error scanning table name: %w", err)
		}
		tables = append(tables, tableName)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating table rows: %w", err)
	}
	return tables, nil
}

// ListColumns for MySQL
func (h mysqlHandler) ListColumns(db *database.DB, tableName string) ([]database.ColumnInfo, error) {
	query := fmt.Sprintf("SHOW COLUMNS FROM `%s`;", tableName)

	rows, err := db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("error querying columns for table %s: %w", tableName, err)
	}
	defer rows.Close()

	var columns []database.ColumnInfo // Modified to []database.ColumnInfo
	for rows.Next() {
		var columnDetails struct {
			Field   string      `db:"Field"`
			Type    string      `db:"Type"` // This is the datatype
			Null    string      `db:"Null"`
			Key     string      `db:"Key"`
			Default interface{} `db:"Default"`
			Extra   string      `db:"Extra"`
		}
		if err := rows.Scan(&columnDetails.Field, &columnDetails.Type, &columnDetails.Null, &columnDetails.Key, &columnDetails.Default, &columnDetails.Extra); err != nil {
			return nil, fmt.Errorf("error scanning column details: %w", err)
		}
		columns = append(columns, database.ColumnInfo{Name: columnDetails.Field, DataType: columnDetails.Type}) // Store both name and datatype
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating column rows: %w", err)
	}

	return columns, nil
}

// GetColumnMetadata for MySQL
func (h mysqlHandler) GetColumnMetadata(db *database.DB, tableName string, columnName string) (map[string]interface{}, error) {
	quotedTable := h.QuoteIdentifier(tableName)
	quotedColumn := h.QuoteIdentifier(columnName)

	distinctQuery := fmt.Sprintf("SELECT COUNT(DISTINCT %s) FROM %s", quotedColumn, quotedTable)
	var distinctCount int
	err := db.QueryRow(distinctQuery).Scan(&distinctCount)
	if err != nil {
		return nil, fmt.Errorf("failed to get distinct count: %w", err)
	}

	nullQuery := fmt.Sprintf("SELECT COUNT(*) FROM %s WHERE %s IS NULL", quotedTable, quotedColumn)
	var nullCount int
	err = db.QueryRow(nullQuery).Scan(&nullCount)
	if err != nil {
		return nil, fmt.Errorf("failed to get null count: %w", err)
	}

	exampleQuery := fmt.Sprintf("SELECT %s FROM %s WHERE %s IS NOT NULL LIMIT 3",
		quotedColumn, quotedTable, quotedColumn)
	rows, err := db.Query(exampleQuery)
	if err != nil {
		return nil, fmt.Errorf("failed to get example values: %w", err)
	}
	defer rows.Close()

	var examples []string
	for rows.Next() {
		var value string
		if err := rows.Scan(&value); err != nil {
			return nil, fmt.Errorf("error scanning example value: %w", err)
		}
		examples = append(examples, value)
	}

	return map[string]interface{}{
		"DistinctCount": distinctCount,
		"NullCount":     nullCount,
		"ExampleValues": examples,
	}, nil
}

// formatExampleValues formats a slice of example values for SQL comment in MySQL
func (h mysqlHandler) formatExampleValues(values []string) string {
	if len(values) == 0 {
		return "[]"
	}
	quoted := make([]string, len(values))
	for i, v := range values {
		quoted[i] = v
	}
	return fmt.Sprintf("[%s]", strings.Join(quoted, ", "))
}

func (h mysqlHandler) generateMetadataComment(data *database.CommentData, enrichments map[string]bool) string {
	if data == nil {
		return ""
	}
	if data.TableName == "" || data.ColumnName == "" {
		return ""
	}

	var commentParts []string

	// Helper function to check if enrichment is requested
	isEnrichmentRequested := func(enrichment string) bool {
		if len(enrichments) == 0 {
			return true // If no enrichments specified, include all
		}
		return enrichments[enrichment]
	}

	if isEnrichmentRequested("description") && data.Description != "" {
		commentParts = append(commentParts, fmt.Sprintf("Description: %s", data.Description))
	}

	if isEnrichmentRequested("examples") && len(data.ExampleValues) > 0 {
		commentParts = append(commentParts, fmt.Sprintf("Examples: %s", h.formatExampleValues(data.ExampleValues)))
	}
	if isEnrichmentRequested("distinct_values") {
		commentParts = append(commentParts, fmt.Sprintf("Distinct Values: %d", data.DistinctCount))
	}
	if isEnrichmentRequested("null_count") {
		commentParts = append(commentParts, fmt.Sprintf("Null Count: %d", data.NullCount))
	}

	return strings.Join(commentParts, " | ")
}

func (h mysqlHandler) generateTableMetadataComment(data *database.TableCommentData, enrichments map[string]bool) string {
	if data == nil || data.TableName == "" {
		return ""
	}

	var commentParts []string
	isEnrichmentRequested := func(enrichment string) bool {
		if len(enrichments) == 0 {
			return true // If no enrichments specified, include all
		}
		return enrichments[enrichment]
	}

	if isEnrichmentRequested("description") && data.Description != "" {
		commentParts = append(commentParts, fmt.Sprintf("Description: %s", data.Description))
	}
	return strings.Join(commentParts, " | ")
}

func (h mysqlHandler) mergeComments(existingComment string, newMetadataComment string, updateExistingMode string) string {
	startTag := "<gemini>"
	endTag := "</gemini>"
	startIndex := strings.Index(existingComment, startTag)
	endIndex := strings.LastIndex(existingComment, endTag)

	comment := ""

	if startIndex == -1 || endIndex == -1 || endIndex <= startIndex {
		// No Gemini tag found, append new comment with tags
		if existingComment != "" {
			comment = existingComment + " " + startTag + newMetadataComment + endTag
		} else {
			comment = startTag + newMetadataComment + endTag // Just add new comment with tags
		}
	} else if updateExistingMode == "append" {
		currentGeminiComment := existingComment[startIndex+len(startTag) : endIndex]
		if currentGeminiComment != "" {
			comment = existingComment[:endIndex] + " " + newMetadataComment + endTag + existingComment[endIndex+len(endTag):] // Append to existing gemini comment
		}

	} else {
		// Gemini tag found, replace content inside tags
		prefix := existingComment[:startIndex]
		suffix := existingComment[endIndex+len(endTag):]
		comment = prefix + startTag + newMetadataComment + endTag + suffix
	}
	if comment == "" {
		comment = existingComment
	}
	if comment == "<gemini></gemini>" {
		comment = ""
	}
	return comment
}

// GenerateCommentSQL creates SQL statements for column comments in MySQL
func (h mysqlHandler) GenerateCommentSQL(db *database.DB, data *database.CommentData, enrichments map[string]bool) (string, error) {
	if data == nil {
		return "", fmt.Errorf("metadata cannot be nil")
	}
	if data.TableName == "" || data.ColumnName == "" {
		return "", fmt.Errorf("table and column names cannot be empty")
	}
	if data.ColumnDataType == "" {
		return "", fmt.Errorf("column datatype cannot be empty for MySQL comment generation")
	}

	config := database.GetConfig() // Retrieve global config
	newMetadataComment := h.generateMetadataComment(data, enrichments)
	existingComment, err := h.GetColumnComment(context.Background(), db, data.TableName, data.ColumnName) // Get existing comment
	if err != nil {
		return "", err
	}
	finalComment := h.mergeComments(existingComment, newMetadataComment, config.UpdateExistingMode) // Pass updateExistingMode
	quotedComment, err := quotedCommentSQL(finalComment)
	if err != nil {
		return "", err
	}

	if finalComment == "" {
		return "", nil
	}

	return fmt.Sprintf(
		"ALTER TABLE %s MODIFY COLUMN %s %s COMMENT %s;",
		h.QuoteIdentifier(data.TableName),
		h.QuoteIdentifier(data.ColumnName),
		data.ColumnDataType,
		quotedComment,
	), nil
}

// GenerateDeleteCommentSQL for MySQL
func (h mysqlHandler) GenerateDeleteCommentSQL(ctx context.Context, db *database.DB, tableName string, columnName string) (string, error) {
	if tableName == "" || columnName == "" {
		return "", fmt.Errorf("table and column names cannot be empty")
	}

	existingComment, err := h.GetColumnComment(ctx, db, tableName, columnName)
	if err != nil {
		return "", err
	}

	startTag := "<gemini>"
	endTag := "</gemini>"
	startIndex := strings.Index(existingComment, startTag)
	endIndex := strings.LastIndex(existingComment, endTag)

	var finalComment string
	if startIndex != -1 && endIndex != -1 && endIndex > startIndex {
		// Gemini tags found, remove content within tags
		prefix := existingComment[:startIndex]
		suffix := existingComment[endIndex+len(endTag):]
		finalComment = strings.TrimSpace(prefix + suffix) // Trim leading/trailing spaces after removing gemini part
	} else {
		// Gemini tags not found, or invalid tags, keep original comment (or remove gemini tags if present but invalid)
		finalComment = existingComment
	}

	quotedComment, err := quotedCommentSQL(finalComment)
	if err != nil {
		return "", err
	}

	return fmt.Sprintf(
		"ALTER TABLE %s MODIFY COLUMN %s %s COMMENT %s;",
		h.QuoteIdentifier(tableName),
		h.QuoteIdentifier(columnName),
		getColumnDataType(ctx, db, tableName, columnName),
		quotedComment,
	), nil
}

func quotedCommentSQL(comment string) (string, error) {
	quotedComment := pq.QuoteLiteral(comment) // Use pq.QuoteLiteral for proper quoting
	return quotedComment, nil
}

// GetColumnComment for MySQL retrieves the comment for a specific column.
func (h mysqlHandler) GetColumnComment(ctx context.Context, db *database.DB, tableName string, columnName string) (string, error) {
	query := `
		SELECT column_comment
		FROM information_schema.columns
		WHERE table_name = ?
		  AND column_name = ?
		  AND table_schema = DATABASE();
	`

	var comment sql.NullString // Use sql.NullString to handle NULL values
	err := db.QueryRowContext(ctx, query, tableName, columnName).Scan(&comment)

	if err != nil {
		if err == sql.ErrNoRows {
			return "", nil // No comment found, return empty string
		}
		return "", fmt.Errorf("failed to retrieve column comment: %w", err)
	}

	if comment.Valid {
		return comment.String, nil
	} else {
		return "", nil // Comment is NULL in DB, return empty string
	}
}

// getColumnDataType retrieves the data type of a column for MySQL.
func getColumnDataType(ctx context.Context, db *database.DB, tableName string, columnName string) string {
	query := `
		SELECT column_type
		FROM information_schema.columns
		WHERE table_name = ?
		  AND column_name = ?
		  AND table_schema = DATABASE();
	`
	var columnType string
	err := db.QueryRowContext(ctx, query, tableName, columnName).Scan(&columnType)
	if err != nil {
		return ""
	}
	return columnType
}

// GenerateTableCommentSQL generates the SQL to comment on a table.
func (h mysqlHandler) GenerateTableCommentSQL(db *database.DB, data *database.TableCommentData, enrichments map[string]bool) (string, error) {
	if data == nil || data.TableName == "" {
		return "", fmt.Errorf("table comment data cannot be nil or empty")
	}

	config := database.GetConfig()

	newMetadataComment := h.generateTableMetadataComment(data, enrichments)
	existingComment, err := h.GetTableComment(context.Background(), db, data.TableName)
	if err != nil {
		return "", err
	}
	finalComment := h.mergeComments(existingComment, newMetadataComment, config.UpdateExistingMode)
	quotedComment, err := quotedCommentSQL(finalComment)
	if err != nil {
		return "", err
	}

	if finalComment == "" {
		return "", nil
	}

	return fmt.Sprintf(
		"ALTER TABLE %s COMMENT = %s;",
		h.QuoteIdentifier(data.TableName),
		quotedComment,
	), nil
}

// GetTableComment retrieves the existing comment for a table.
func (h mysqlHandler) GetTableComment(ctx context.Context, db *database.DB, tableName string) (string, error) {
	query := `
        SELECT table_comment
        FROM information_schema.tables
        WHERE table_name = ?
          AND table_schema = DATABASE();
    `

	var comment sql.NullString
	err := db.QueryRowContext(ctx, query, tableName).Scan(&comment)
	if err != nil {
		if err == sql.ErrNoRows {
			return "", nil // No comment, return empty string.
		}
		return "", fmt.Errorf("failed to retrieve table comment: %w", err)
	}

	if comment.Valid {
		return comment.String, nil
	}
	return "", nil // Comment is NULL.
}

// GenerateDeleteTableCommentSQL generates SQL to remove the Gemini-generated part of a table comment.
func (h mysqlHandler) GenerateDeleteTableCommentSQL(ctx context.Context, db *database.DB, tableName string) (string, error) {
	if tableName == "" {
		return "", fmt.Errorf("table name cannot be empty")
	}

	existingComment, err := h.GetTableComment(ctx, db, tableName)
	if err != nil {
		return "", err
	}

	startTag := "<gemini>"
	endTag := "</gemini>"
	startIndex := strings.Index(existingComment, startTag)
	endIndex := strings.LastIndex(existingComment, endTag)

	var finalComment string
	if startIndex != -1 && endIndex != -1 && endIndex > startIndex {
		prefix := existingComment[:startIndex]
		suffix := existingComment[endIndex+len(endTag):]
		finalComment = strings.TrimSpace(prefix + suffix)
	} else {
		finalComment = existingComment // No gemini tags, keep original.
	}

	quotedComment, err := quotedCommentSQL(finalComment)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("ALTER TABLE %s COMMENT = %s;", h.QuoteIdentifier(tableName), quotedComment), nil
}

func init() {
	database.RegisterDialectHandler("mysql", mysqlHandler{})
	database.RegisterDialectHandler("cloudsqlmysql", mysqlHandler{})
}

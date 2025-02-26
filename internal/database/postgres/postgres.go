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
package postgres

import (
	"context"
	"database/sql"
	"fmt"
	"net"
	"os"
	"strings"

	"cloud.google.com/go/cloudsqlconn"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/stdlib"
	"github.com/lib/pq"

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/config"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
)

// postgresHandler struct implements database.DialectHandler for PostgreSQL.
type postgresHandler struct{}

var _ database.DialectHandler = (*postgresHandler)(nil)

// CreateCloudSQLPool for PostgreSQL
func (h postgresHandler) CreateCloudSQLPool(cfg config.DatabaseConfig) (*sql.DB, error) {
	mustGetenv := func(k string, cfg config.DatabaseConfig) string { // Keep mustGetenv here as it's specific to connection
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
			return os.Getenv(k) // Fallback to environment variable if not in Config
		}
		return v
	}

	dbUser := mustGetenv("user_name", cfg)
	dbPwd := mustGetenv("password", cfg)
	dbName := mustGetenv("database_name", cfg)
	instanceConnectionName := mustGetenv("instance_name", cfg)
	usePrivate := mustGetenv("PRIVATE_IP", cfg)

	dsn := fmt.Sprintf("user=%s password=%s database=%s", dbUser, dbPwd, dbName)
	config, err := pgx.ParseConfig(dsn)
	if err != nil {
		return nil, err
	}
	var opts []cloudsqlconn.Option
	if usePrivate != "" && strings.ToLower(usePrivate) != "false" && usePrivate != "0" { // Handle boolean-like env vars
		opts = append(opts, cloudsqlconn.WithDefaultDialOptions(cloudsqlconn.WithPrivateIP()))
	}
	d, err := cloudsqlconn.NewDialer(context.Background(), opts...)
	if err != nil {
		return nil, err
	}
	config.DialFunc = func(ctx context.Context, network, instance string) (net.Conn, error) {
		return d.Dial(ctx, instanceConnectionName)
	}
	dbURI := stdlib.RegisterConnConfig(config)
	dbPool, err := sql.Open("pgx", dbURI)
	if err != nil {
		return nil, fmt.Errorf("sql.Open: %w", err)
	}

	return dbPool, nil
}

// CreateStandardPool creates a standard PostgreSQL connection pool
func (h postgresHandler) CreateStandardPool(cfg config.DatabaseConfig) (*sql.DB, error) {
	connStr := fmt.Sprintf(
		"host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		cfg.Host, cfg.Port, cfg.User, cfg.Password, cfg.DBName, cfg.SSLMode,
	)

	dbPool, err := sql.Open("postgres", connStr)
	if err != nil {
		return nil, fmt.Errorf("error opening database: %w", err)
	}
	return dbPool, err
}

// QuoteIdentifier for PostgreSQL
func (h postgresHandler) QuoteIdentifier(name string) string {
	// Replace any existing quotes with double quotes to escape them
	name = strings.Replace(name, `"`, `""`, -1)
	// Wrap the entire name in quotes
	return fmt.Sprintf(`"%s"`, name)
}

// ListTables for PostgreSQL
func (h postgresHandler) ListTables(db *database.DB) ([]string, error) {
	query := `
		SELECT table_name
		FROM information_schema.tables
		WHERE table_schema = 'public'
		AND table_type = 'BASE TABLE'
		ORDER BY table_name;`

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

// ListColumns for PostgreSQL
func (h postgresHandler) ListColumns(db *database.DB, tableName string) ([]database.ColumnInfo, error) {
	query := `
		SELECT column_name, data_type
		FROM information_schema.columns
		WHERE table_schema = 'public'
		AND table_name = $1
		ORDER BY ordinal_position;`

	rows, err := db.Query(query, tableName)
	if err != nil {
		return nil, fmt.Errorf("error querying columns for table %s: %w", tableName, err)
	}
	defer rows.Close()

	var columns []database.ColumnInfo
	for rows.Next() {
		var colInfo database.ColumnInfo
		if err := rows.Scan(&colInfo.Name, &colInfo.DataType); err != nil {
			return nil, fmt.Errorf("error scanning column name and data type: %w", err)
		}
		columns = append(columns, colInfo)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating column rows: %w", err)
	}

	return columns, nil
}

// GetColumnMetadata for PostgreSQL
func (h postgresHandler) GetColumnMetadata(db *database.DB, tableName string, columnName string) (map[string]interface{}, error) {
	// Quote table and column names to handle special characters and spaces
	quotedTable := h.QuoteIdentifier(tableName) // Use handler's QuoteIdentifier
	quotedColumn := h.QuoteIdentifier(columnName)

	// Get distinct count
	distinctQuery := fmt.Sprintf("SELECT COUNT(DISTINCT %s) FROM %s", quotedColumn, quotedTable)
	var distinctCount int
	err := db.QueryRow(distinctQuery).Scan(&distinctCount)
	if err != nil {
		return nil, fmt.Errorf("failed to get distinct count: %w", err)
	}

	// Get null count
	nullQuery := fmt.Sprintf("SELECT COUNT(*) FROM %s WHERE %s IS NULL", quotedTable, quotedColumn)
	var nullCount int
	err = db.QueryRow(nullQuery).Scan(&nullCount)
	if err != nil {
		return nil, fmt.Errorf("failed to get null count: %w", err)
	}

	// Get example values (top 3)
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

// GetForeignKeys for PostgreSQL (implements MetadataCollector).
func (h postgresHandler) GetForeignKeys(db *database.DB, tableName string, columnName string) ([]database.ForeignKeyInfo, error) {
	// Query to detect foreign keys from constraint metadata (PostgreSQL specific)
	query := `
        SELECT
            ccu.table_name as ref_table,
            ccu.column_name as ref_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND kcu.table_name = $1
            AND kcu.column_name = $2
            AND tc.table_schema = current_schema()`

	rows, err := db.Query(query, tableName, columnName)
	if err != nil {
		return nil, fmt.Errorf("failed to execute foreign key detection query: %w", err)
	}
	defer rows.Close()

	var fks []database.ForeignKeyInfo
	for rows.Next() {
		var fk database.ForeignKeyInfo
		if err := rows.Scan(&fk.RefTable, &fk.RefColumn); err != nil {
			return nil, fmt.Errorf("failed to scan foreign key info: %w", err)
		}
		fks = append(fks, fk)
	}

	if err = rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating foreign key rows: %w", err)
	}

	return fks, nil
}

// formatExampleValues formats a slice of example values for SQL comment in PostgreSQL
func (h postgresHandler) formatExampleValues(values []string) string {
	if len(values) == 0 {
		return "[]"
	}
	// Quote each value and join with comma
	quoted := make([]string, len(values))
	for i, v := range values {
		quoted[i] = pq.QuoteLiteral(v)
	}
	return fmt.Sprintf("[%s]", strings.Join(quoted, ", "))
}

func (h postgresHandler) generateMetadataComment(data *database.CommentData, updateExistingMode string) string {
	if data == nil {
		return ""
	}
	if data.TableName == "" || data.ColumnName == "" {
		return ""
	}

	commentText := fmt.Sprintf(
		"Examples: %s | Distinct Values: %d | Null Count: %d",
		h.formatExampleValues(data.ExampleValues),
		data.DistinctCount,
		data.NullCount,
	)

	if len(data.ForeignKeys) > 0 {
		fkStrings := make([]string, len(data.ForeignKeys))
		for i, fk := range data.ForeignKeys {
			fkStrings[i] = fmt.Sprintf("%s.%s",
				h.QuoteIdentifier(fk.RefTable),
				h.QuoteIdentifier(fk.RefColumn),
			)
		}
		commentText += fmt.Sprintf(" | Foreign Keys: [%s]", strings.Join(fkStrings, ", "))
	}

	return commentText
}

func (h postgresHandler) mergeComments(existingComment string, newMetadataComment string, updateExistingMode string) string {
	startTag := "<gemini>"
	endTag := "</gemini>"
	startIndex := strings.Index(existingComment, startTag)
	endIndex := strings.LastIndex(existingComment, endTag)

	if startIndex == -1 || endIndex == -1 || endIndex <= startIndex {
		// No Gemini tag found, append new comment with tags
		if existingComment != "" {
			return existingComment + " " + startTag + newMetadataComment + endTag
		} else {
			return startTag + newMetadataComment + endTag // Just add new comment with tags
		}
	} else if updateExistingMode == "append" {
		currentGeminiComment := existingComment[startIndex+len(startTag) : endIndex]
		if currentGeminiComment != "" {
			return existingComment[:endIndex] + " " + newMetadataComment + endTag + existingComment[endIndex+len(endTag):] // Append to existing gemini comment
		}
	} else {
		// Gemini tag found, replace content inside tags
		prefix := existingComment[:startIndex]
		suffix := existingComment[endIndex+len(endTag):]
		return prefix + startTag + newMetadataComment + endTag + suffix
	}
	return existingComment
}

// GenerateCommentSQL creates SQL statements for column comments in PostgreSQL
func (h postgresHandler) GenerateCommentSQL(db *database.DB, data *database.CommentData) (string, error) {
	if data == nil {
		return "", fmt.Errorf("comment data cannot be nil")
	}
	if data.TableName == "" || data.ColumnName == "" {
		return "", fmt.Errorf("table and column names cannot be empty")
	}

	config := database.GetConfig()                                                   // Retrieve global config to access updateExistingMode
	newMetadataComment := h.generateMetadataComment(data, config.UpdateExistingMode) // Pass updateExistingMode
	existingComment, err := h.GetColumnComment(context.Background(), db, data.TableName, data.ColumnName)
	if err != nil {
		return "", err
	}
	finalComment := h.mergeComments(existingComment, newMetadataComment, config.UpdateExistingMode) // Pass updateExistingMode
	// Escape single quotes in comment for SQL
	escapedComment := strings.ReplaceAll(finalComment, "'", "''")
	quotedComment := pq.QuoteLiteral(escapedComment)

	return fmt.Sprintf(
		"COMMENT ON COLUMN %s.%s IS %s;",
		h.QuoteIdentifier(data.TableName),
		h.QuoteIdentifier(data.ColumnName),
		quotedComment,
	), nil
}

// GenerateDeleteCommentSQL for PostgreSQL
func (h postgresHandler) GenerateDeleteCommentSQL(ctx context.Context, db *database.DB, tableName string, columnName string) (string, error) {
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
		// Gemini tags not found, or invalid tags, keep original comment
		finalComment = existingComment
	}
	quotedComment := pq.QuoteLiteral(finalComment)
	return fmt.Sprintf(
		"COMMENT ON COLUMN %s.%s IS %s;",
		h.QuoteIdentifier(tableName),
		h.QuoteIdentifier(columnName),
		quotedComment,
	), nil
}

// GetColumnComment for PostgreSQL retrieves the comment for a specific column.
func (h postgresHandler) GetColumnComment(ctx context.Context, db *database.DB, tableName string, columnName string) (string, error) {
	query := `
		SELECT description
		FROM pg_catalog.pg_description
		JOIN pg_catalog.pg_class c ON pg_description.objoid = c.oid
		JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
		JOIN pg_catalog.pg_attribute a ON pg_description.objoid = a.attrelid AND pg_description.objsubid = a.attnum
		WHERE n.nspname = 'public' -- Assuming public schema
		  AND c.relname = $1
		  AND a.attname = $2;
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
	}

	return "", nil // Comment is NULL in DB, return empty string
}

func init() {
	database.RegisterDialectHandler("postgres", postgresHandler{})
	database.RegisterDialectHandler("cloudsqlpostgres", postgresHandler{})
}

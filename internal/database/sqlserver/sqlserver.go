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
package sqlserver

import (
	"context"
	"database/sql"
	"fmt"
	"net"
	"os"
	"strings"

	"cloud.google.com/go/cloudsqlconn"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/config"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
	mssql "github.com/denisenkom/go-mssqldb"
)

// sqlServerHandler struct implements database.DialectHandler for SQL Server.
type sqlServerHandler struct{}

var _ database.DialectHandler = (*sqlServerHandler)(nil)

type csqlDialer struct {
	dialer     *cloudsqlconn.Dialer
	connName   string
	usePrivate bool
}

// DialContext adheres to the mssql.Dialer interface.
func (c *csqlDialer) DialContext(ctx context.Context, network, addr string) (net.Conn, error) {
	var opts []cloudsqlconn.DialOption
	if c.usePrivate {
		opts = append(opts, cloudsqlconn.WithPrivateIP())
	}
	return c.dialer.Dial(ctx, c.connName, opts...)
}

// CreateCloudSQLPool for SQL Server
func (h sqlServerHandler) CreateCloudSQLPool(cfg config.DatabaseConfig) (*sql.DB, error) {
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

	// WithLazyRefresh() Option is used to perform refresh
	// when needed, rather than on a scheduled interval.
	// This is recommended for serverless environments to
	// avoid background refreshes from throttling CPU.
	dialer, err := cloudsqlconn.NewDialer(context.Background(), cloudsqlconn.WithLazyRefresh())
	if err != nil {
		return nil, fmt.Errorf("cloudsqlconn.NewDailer: %w", err)
	}
	connector, err := mssql.NewConnector(fmt.Sprintf("sqlserver://%s:%s@localhost:1433?database=%s&dial=cloudsqlconn&instance=%s",
		dbUser, dbPwd, dbName, instanceConnectionName))
	if err != nil {
		return nil, fmt.Errorf("mssql.NewConnector: %w", err)
	}
	connector.Dialer = &csqlDialer{
		dialer:     dialer,
		connName:   instanceConnectionName,
		usePrivate: usePrivate != "",
	}

	dbPool := sql.OpenDB(connector)

	return dbPool, nil
}

// CreateStandardPool creates a standard SQL Server connection pool
func (h sqlServerHandler) CreateStandardPool(cfg config.DatabaseConfig) (*sql.DB, error) {
	port := cfg.Port
	if port == 0 {
		port = 1433 // Default SQL Server port
	}
	connStr := fmt.Sprintf("sqlserver://%s:%s@%s:%d?database=%s",
		cfg.User, cfg.Password, cfg.Host, port, cfg.DBName)

	dbPool, err := sql.Open("sqlserver", connStr)
	if err != nil {
		return nil, fmt.Errorf("sql.Open (standard sqlserver): %w", err)
	}
	return dbPool, nil
}

// QuoteIdentifier for SQL Server
// SQL Server uses square brackets [] for identifiers.
// Double quotes "" are also accepted in some contexts but square brackets are standard and safer.
func (h sqlServerHandler) QuoteIdentifier(name string) string {
	return fmt.Sprintf("[%s]", name)
}

// ListTables for SQL Server
func (h sqlServerHandler) ListTables(db *database.DB) ([]string, error) {
	query := "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_CATALOG = DB_NAME()"
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

// ListColumns for SQL Server
func (h sqlServerHandler) ListColumns(db *database.DB, tableName string) ([]database.ColumnInfo, error) {
	query := fmt.Sprintf("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '%s' AND TABLE_CATALOG = DB_NAME()", tableName)

	rows, err := db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("error querying columns for table %s: %w", tableName, err)
	}
	defer rows.Close()

	var columns []database.ColumnInfo

	for rows.Next() {
		var colInfo database.ColumnInfo
		if err := rows.Scan(&colInfo.Name, &colInfo.DataType); err != nil {
			return nil, fmt.Errorf("error scanning column details: %w", err)
		}
		columns = append(columns, colInfo)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating column rows: %w", err)
	}
	return columns, nil
}

// GetColumnMetadata for SQL Server
func (h sqlServerHandler) GetColumnMetadata(db *database.DB, tableName string, columnName string) (map[string]interface{}, error) {
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

	exampleQuery := fmt.Sprintf("SELECT TOP 3 %s FROM %s WHERE %s IS NOT NULL",
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

// GetForeignKeys for SQL Server
func (h sqlServerHandler) GetForeignKeys(db *database.DB, tableName string, columnName string) ([]database.ForeignKeyInfo, error) {
	query := `
		SELECT
			OBJECT_NAME(f.referenced_object_id) AS ref_table,
			COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS ref_column
		FROM
			sys.foreign_keys f
		JOIN
			sys.foreign_key_columns fkc ON f.object_id = fkc.constraint_object_id
		JOIN
			sys.columns c ON fkc.parent_column_id = c.column_id AND fkc.parent_object_id = c.object_id AND c.object_id = OBJECT_ID(@tableName)
		WHERE
			OBJECT_NAME(f.parent_object_id) = @tableName
			AND c.name = @columnName
	`

	rows, err := db.Query(query, sql.Named("tableName", tableName), sql.Named("columnName", columnName))

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

// formatExampleValues formats a slice of example values for SQL comment in SQL Server
func (h sqlServerHandler) formatExampleValues(values []string) string {
	if len(values) == 0 {
		return "[]"
	}
	quoted := make([]string, len(values))
	for i, v := range values {
		// Use %q to add double quotes and escape internal double quotes and backslashes.
		quoted[i] = fmt.Sprintf("%q", v)
	}
	return fmt.Sprintf("[%s]", strings.Join(quoted, ", ")) // Format as array
}

func (h sqlServerHandler) generateMetadataComment(data *database.CommentData, updateExistingMode string) string {
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

func (h sqlServerHandler) mergeComments(existingComment string, newMetadataComment string, updateExistingMode string) string {
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

// GenerateCommentSQL creates SQL statements for column comments in SQL Server
func (h sqlServerHandler) GenerateCommentSQL(db *database.DB, data *database.CommentData) (string, error) {
	if data == nil {
		return "", fmt.Errorf("metadata cannot be nil")
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
	// Escape single quotes within the comment.  This is essential for SQL Server.
	escapedComment := strings.ReplaceAll(finalComment, "'", "''")

	// Check if comment already exists to decide between sp_addextendedproperty and sp_updateextendedproperty
	query := `
		SELECT CAST(value as NVARCHAR(MAX))
		FROM fn_listextendedproperty (N'MS_Description', N'SCHEMA', N'dbo', N'TABLE', @tableName, N'COLUMN', @columnName)
	`
	var existingCommentDB string
	err = db.QueryRow(query, sql.Named("tableName", data.TableName), sql.Named("columnName", data.ColumnName)).Scan(&existingCommentDB)
	if err != nil && err != sql.ErrNoRows {
		return "", fmt.Errorf("failed to check for existing comment: %w", err)
	}

	var sqlStmt string
	if err == sql.ErrNoRows {
		// No existing comment, use sp_addextendedproperty
		sqlStmt = fmt.Sprintf(
			"EXEC sp_addextendedproperty N'MS_Description', N'%s', N'SCHEMA', N'dbo', N'TABLE', %s, N'COLUMN', %s;",
			escapedComment, // Use the merged comment
			h.QuoteIdentifier(data.TableName),
			h.QuoteIdentifier(data.ColumnName),
		)
	} else {
		// Existing comment found, use sp_updateextendedproperty
		sqlStmt = fmt.Sprintf(
			"EXEC sp_updateextendedproperty N'MS_Description', N'%s', N'SCHEMA', N'dbo', N'TABLE', %s, N'COLUMN', %s;",
			escapedComment, // Use the merged comment
			h.QuoteIdentifier(data.TableName),
			h.QuoteIdentifier(data.ColumnName),
		)
	}
	return sqlStmt, nil
}

// GenerateDeleteCommentSQL for SQL Server
func (h sqlServerHandler) GenerateDeleteCommentSQL(ctx context.Context, db *database.DB, tableName string, columnName string) (string, error) {
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

	escapedComment := strings.ReplaceAll(finalComment, "'", "''")

	// Generate SQL to update or add extended property (same as in GenerateCommentSQL, but with the modified comment)
	sqlStmt := fmt.Sprintf(
		"EXEC sp_updateextendedproperty N'MS_Description', N'%s', N'SCHEMA', N'dbo', N'TABLE', %s, N'COLUMN', %s;",
		escapedComment, // Use the modified comment (Gemini part removed)
		h.QuoteIdentifier(tableName),
		h.QuoteIdentifier(columnName),
	)
	return sqlStmt, nil
}

// GetColumnComment for SQL Server retrieves the comment for a specific column.
func (h sqlServerHandler) GetColumnComment(ctx context.Context, db *database.DB, tableName string, columnName string) (string, error) {
	query := `
		SELECT CAST(value as NVARCHAR(MAX))
		FROM fn_listextendedproperty (N'MS_Description', N'SCHEMA', N'dbo', N'TABLE', @tableName, N'COLUMN', @columnName)
	`

	var comment sql.NullString // Use sql.NullString to handle NULL values
	err := db.QueryRowContext(ctx, query, sql.Named("tableName", tableName), sql.Named("columnName", columnName)).Scan(&comment)

	if err != nil {
		if err == sql.ErrNoRows {
			return "", nil // No comment found, return empty string
		}
		return "", fmt.Errorf("failed to retrieve column comment: %w", err)
	}

	if comment.Valid {
		return comment.String, nil
	} else {
		return "", nil // Comment is NULL in DB, return nil, nil
	}
}

func init() {
	database.RegisterDialectHandler("sqlserver", sqlServerHandler{})
	database.RegisterDialectHandler("cloudsqlsqlserver", sqlServerHandler{})
}

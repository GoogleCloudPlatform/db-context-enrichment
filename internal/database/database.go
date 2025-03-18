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
package database

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/config"
)

// DB wraps the sql.DB instance and provides additional functionality
type DB struct {
	*sql.DB
	DialectHandler
}

// ForeignKeyInfo holds foreign key relationship details
type ForeignKeyInfo struct {
	RefTable  string
	RefColumn string
}

// ColumnInfo holds column name and datatype
type ColumnInfo struct {
	Name     string
	DataType string
}

// CommentData holds the data required to generate column comments.
// It's defined in the database package to avoid cyclic dependencies.
type CommentData struct {
	TableName      string
	ColumnName     string
	ColumnDataType string
	ExampleValues  []string
	DistinctCount  int64
	NullCount      int64
	Description    string
}

// TableCommentData holds data for table comments.
type TableCommentData struct {
	TableName   string
	Description string
}

// DialectHandler interface
type DialectHandler interface {
	CreateCloudSQLPool(cfg config.DatabaseConfig) (*sql.DB, error)
	CreateStandardPool(cfg config.DatabaseConfig) (*sql.DB, error)
	QuoteIdentifier(name string) string
	ListTables(db *DB) ([]string, error)
	ListColumns(db *DB, tableName string) ([]ColumnInfo, error)
	GetColumnMetadata(db *DB, tableName string, columnName string) (map[string]interface{}, error)
	GenerateCommentSQL(db *DB, data *CommentData, enrichments map[string]bool) (string, error)
	GetColumnComment(ctx context.Context, db *DB, tableName string, columnName string) (string, error)
	GenerateDeleteCommentSQL(ctx context.Context, db *DB, tableName string, columnName string) (string, error)

	// Added these methods for table-level comments
	GenerateTableCommentSQL(db *DB, data *TableCommentData, enrichments map[string]bool) (string, error)
	GetTableComment(ctx context.Context, db *DB, tableName string) (string, error)
	GenerateDeleteTableCommentSQL(ctx context.Context, db *DB, tableName string) (string, error)
}

var (
	globalConfig *config.DatabaseConfig
	mu           sync.RWMutex
)

// SetConfig sets the global database configuration
func SetConfig(cfg *config.DatabaseConfig) {
	mu.Lock()
	defer mu.Unlock()
	globalConfig = cfg
}

// GetConfig returns the current database configuration
func GetConfig() *config.DatabaseConfig {
	mu.RLock()
	defer mu.RUnlock()
	return globalConfig
}

var dialectHandlers = make(map[string]DialectHandler)

// RegisterDialectHandler registers a DialectHandler for a given dialect.
func RegisterDialectHandler(dialect string, handler DialectHandler) {
	dialectHandlers[dialect] = handler
}

// createPool sets up common connection pool parameters and pings the database.
func createPool(db *sql.DB) (*sql.DB, error) {
	db.SetMaxOpenConns(5)
	db.SetMaxIdleConns(2)
	db.SetConnMaxLifetime(time.Hour)

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := db.PingContext(ctx); err != nil {
		db.Close()
		return nil, fmt.Errorf("database ping failed: %w", err)
	}
	return db, nil
}

// New creates a new database connection based on the specified dialect
func New(cfg config.DatabaseConfig) (*DB, error) {
	var db *sql.DB
	var err error

	handler, ok := dialectHandlers[cfg.Dialect]
	if !ok {
		return nil, fmt.Errorf("unsupported dialect: %s", cfg.Dialect)
	}

	if strings.HasPrefix(cfg.Dialect, "cloudsql") && cfg.CloudSQLInstanceConnectionName != "" {
		db, err = handler.CreateCloudSQLPool(cfg)
	} else {
		db, err = handler.CreateStandardPool(cfg)
	}

	if err != nil {
		return nil, err
	}

	// Test the connection and setup pool
	db, err = createPool(db)
	if err != nil {
		log.Println("ERROR: Failed to create connection pool:", err)
		return nil, err
	}

	return &DB{
		DB:             db,
		DialectHandler: handler,
	}, nil
}

// ListTables returns all table names
func (db *DB) ListTables() ([]string, error) {
	return db.DialectHandler.ListTables(db)
}

// ListColumns returns all column names for the given table
func (db *DB) ListColumns(tableName string) ([]ColumnInfo, error) { // Modified to return []ColumnInfo
	return db.DialectHandler.ListColumns(db, tableName)
}

// GetColumnMetadata collects metadata for a specific column
func (db *DB) GetColumnMetadata(tableName string, columnName string) (map[string]interface{}, error) {
	return db.DialectHandler.GetColumnMetadata(db, tableName, columnName)
}

// GenerateCommentSQL generates the SQL query to add comment to a column
func (db *DB) GenerateCommentSQL(data *CommentData, enrichments map[string]bool) (string, error) {
	return db.DialectHandler.GenerateCommentSQL(db, data, enrichments)
}

// Close closes the database connection
func (db *DB) Close() error {
	return db.DB.Close()
}

// GetColumnComment retrieves the comment for a specific column
func (db *DB) GetColumnComment(ctx context.Context, tableName string, columnName string) (string, error) {
	return db.DialectHandler.GetColumnComment(ctx, db, tableName, columnName)
}

// GenerateDeleteCommentSQL generates the SQL query to delete gemini comment from a column
func (db *DB) GenerateDeleteCommentSQL(ctx context.Context, tableName string, columnName string) (string, error) {
	return db.DialectHandler.GenerateDeleteCommentSQL(ctx, db, tableName, columnName)
}

// GenerateTableCommentSQL generates the SQL query to add a comment to a table.
func (db *DB) GenerateTableCommentSQL(data *TableCommentData, enrichments map[string]bool) (string, error) {
	return db.DialectHandler.GenerateTableCommentSQL(db, data, enrichments)
}

// GetTableComment retrieves the comment for a specific table.
func (db *DB) GetTableComment(ctx context.Context, tableName string) (string, error) {
	return db.DialectHandler.GetTableComment(ctx, db, tableName)
}

// GenerateDeleteTableCommentSQL generates the SQL query to delete a gemini comment from a table.
func (db *DB) GenerateDeleteTableCommentSQL(ctx context.Context, tableName string) (string, error) {
	return db.DialectHandler.GenerateDeleteTableCommentSQL(ctx, db, tableName)
}

// ExecuteSQLStatements executes a batch of SQL statements from a string slice
func (db *DB) ExecuteSQLStatements(ctx context.Context, sqlStatements []string) error {
	for _, sqlStmt := range sqlStatements {
		_, err := db.ExecContext(ctx, sqlStmt)
		if err != nil {
			return fmt.Errorf("failed to execute SQL statement: %w\nStatement: %s", err, sqlStmt)
		}
	}
	return nil
}

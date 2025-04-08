package database

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"strings"
	"sync"

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/config"
)

// DBAdapter defines the interface for database operations needed by the enricher.
type DBAdapter interface {
	ListTables() ([]string, error)
	ListColumns(tableName string) ([]ColumnInfo, error)
	GetColumnMetadata(tableName string, columnName string) (map[string]interface{}, error)
	GetColumnComment(ctx context.Context, tableName string, columnName string) (string, error)
	GetTableComment(ctx context.Context, tableName string) (string, error)
	GenerateCommentSQL(data *CommentData, enrichments map[string]bool) (string, error)
	GenerateTableCommentSQL(data *TableCommentData, enrichments map[string]bool) (string, error)
	GenerateDeleteCommentSQL(ctx context.Context, tableName string, columnName string) (string, error)
	GenerateDeleteTableCommentSQL(ctx context.Context, tableName string) (string, error)
	ExecuteSQLStatements(ctx context.Context, sqlStatements []string) error
	Ping(ctx context.Context) error
	Close() error
	GetConfig() config.DatabaseConfig
}

var _ DBAdapter = (*DB)(nil)

// DB holds the database connection pool and dialect handler.
type DB struct {
	Pool    *sql.DB
	Handler DialectHandler
	Config  config.DatabaseConfig
}

// ColumnInfo holds basic information about a database column.
type ColumnInfo struct {
	Name     string
	DataType string
}

// CommentData holds information needed to generate a column comment.
type CommentData struct {
	TableName      string
	ColumnName     string
	ColumnDataType string
	ExampleValues  []string
	DistinctCount  int64
	NullCount      int64
	Description    string
}

// TableCommentData holds information needed to generate a table comment.
type TableCommentData struct {
	TableName   string
	Description string
}

var (
	dialectHandlers = make(map[string]DialectHandler)
	mu              sync.RWMutex
)

func RegisterDialectHandler(dialect string, handler DialectHandler) {
	mu.Lock()
	defer mu.Unlock()
	if _, exists := dialectHandlers[dialect]; exists {
		log.Printf("WARN: Dialect handler for '%s' is being overwritten.", dialect)
	}
	dialectHandlers[dialect] = handler
}

func GetDialectHandler(dialect string) (DialectHandler, error) {
	mu.RLock()
	defer mu.RUnlock()
	handler, ok := dialectHandlers[dialect]
	if !ok {
		return nil, fmt.Errorf("unsupported database dialect: %s", dialect)
	}
	return handler, nil
}

func New(cfg config.DatabaseConfig) (*DB, error) {
	handler, err := GetDialectHandler(cfg.Dialect)
	if err != nil {
		return nil, err
	}

	var pool *sql.DB
	if strings.HasPrefix(cfg.Dialect, "cloudsql") {
		pool, err = handler.CreateCloudSQLPool(cfg)
	} else {
		pool, err = handler.CreateStandardPool(cfg)
	}

	if err != nil {
		return nil, fmt.Errorf("failed to create database pool for dialect %s: %w", cfg.Dialect, err)
	}

	ctx := context.Background()
	if err := pool.PingContext(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("failed to connect to database (ping failed) for dialect %s: %w", cfg.Dialect, err)
	}

	return &DB{
		Pool:    pool,
		Handler: handler,
		Config:  cfg,
	}, nil
}

func (db *DB) GetConfig() config.DatabaseConfig {
	return db.Config
}

func (db *DB) Ping(ctx context.Context) error {
	if db.Pool == nil {
		return fmt.Errorf("database connection pool is not initialized")
	}
	return db.Pool.PingContext(ctx)
}

func (db *DB) Close() error {
	if db.Pool != nil {
		return db.Pool.Close()
	}
	log.Println("WARN: Attempted to close a nil database connection pool.")
	return nil
}

func (db *DB) ListTables() ([]string, error) {
	if db.Handler == nil {
		return nil, fmt.Errorf("dialect handler not initialized")
	}
	return db.Handler.ListTables(db)
}

func (db *DB) ListColumns(tableName string) ([]ColumnInfo, error) {
	if db.Handler == nil {
		return nil, fmt.Errorf("dialect handler not initialized")
	}
	return db.Handler.ListColumns(db, tableName)
}

func (db *DB) GetColumnMetadata(tableName string, columnName string) (map[string]interface{}, error) {
	if db.Handler == nil {
		return nil, fmt.Errorf("dialect handler not initialized")
	}
	return db.Handler.GetColumnMetadata(db, tableName, columnName)
}

func (db *DB) GetColumnComment(ctx context.Context, tableName string, columnName string) (string, error) {
	if db.Handler == nil {
		return "", fmt.Errorf("dialect handler not initialized")
	}
	return db.Handler.GetColumnComment(ctx, db, tableName, columnName)
}

func (db *DB) GetTableComment(ctx context.Context, tableName string) (string, error) {
	if db.Handler == nil {
		return "", fmt.Errorf("dialect handler not initialized")
	}
	return db.Handler.GetTableComment(ctx, db, tableName)
}

func (db *DB) GenerateCommentSQL(data *CommentData, enrichments map[string]bool) (string, error) {
	if db.Handler == nil {
		return "", fmt.Errorf("dialect handler not initialized")
	}
	return db.Handler.GenerateCommentSQL(db, data, enrichments)
}

func (db *DB) GenerateTableCommentSQL(data *TableCommentData, enrichments map[string]bool) (string, error) {
	if db.Handler == nil {
		return "", fmt.Errorf("dialect handler not initialized")
	}
	return db.Handler.GenerateTableCommentSQL(db, data, enrichments)
}

func (db *DB) GenerateDeleteCommentSQL(ctx context.Context, tableName string, columnName string) (string, error) {
	if db.Handler == nil {
		return "", fmt.Errorf("dialect handler not initialized")
	}
	return db.Handler.GenerateDeleteCommentSQL(ctx, db, tableName, columnName)
}

func (db *DB) GenerateDeleteTableCommentSQL(ctx context.Context, tableName string) (string, error) {
	if db.Handler == nil {
		return "", fmt.Errorf("dialect handler not initialized")
	}
	return db.Handler.GenerateDeleteTableCommentSQL(ctx, db, tableName)
}

func (db *DB) ExecuteSQLStatements(ctx context.Context, sqlStatements []string) error {
	if db.Pool == nil {
		return fmt.Errorf("database connection pool is not initialized")
	}
	if len(sqlStatements) == 0 {
		log.Println("INFO: No SQL statements provided to ExecuteSQLStatements.")
		return nil
	}

	tx, err := db.Pool.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	for i, stmt := range sqlStatements {
		trimmedStmt := strings.TrimSpace(stmt)
		if trimmedStmt == "" {
			continue
		}
		_, err = tx.ExecContext(ctx, trimmedStmt)
		if err != nil {
			log.Printf("ERROR: Failed executing statement #%d: %s\nError: %v", i+1, trimmedStmt, err)
			return fmt.Errorf("failed executing statement #%d: %w", i+1, err)
		}
	}

	if err = tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}
	return nil
}

// DialectHandler interface remains the same
type DialectHandler interface {
	CreateCloudSQLPool(cfg config.DatabaseConfig) (*sql.DB, error)
	CreateStandardPool(cfg config.DatabaseConfig) (*sql.DB, error)
	QuoteIdentifier(name string) string
	ListTables(db *DB) ([]string, error)
	ListColumns(db *DB, tableName string) ([]ColumnInfo, error)
	GetColumnMetadata(db *DB, tableName string, columnName string) (map[string]interface{}, error)
	GetColumnComment(ctx context.Context, db *DB, tableName string, columnName string) (string, error)
	GetTableComment(ctx context.Context, db *DB, tableName string) (string, error)
	GenerateCommentSQL(db *DB, data *CommentData, enrichments map[string]bool) (string, error)
	GenerateTableCommentSQL(db *DB, data *TableCommentData, enrichments map[string]bool) (string, error)
	GenerateDeleteCommentSQL(ctx context.Context, db *DB, tableName string, columnName string) (string, error)
	GenerateDeleteTableCommentSQL(ctx context.Context, db *DB, tableName string) (string, error)
}

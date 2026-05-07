package database

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"sync"
	"testing"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/config"
)

// Mock DialectHandler implementation
type mockDialectHandler struct {
	mu                         sync.Mutex
	createCloudSQLPoolFn       func(cfg config.DatabaseConfig) (*sql.DB, error)
	createStandardPoolFn       func(cfg config.DatabaseConfig) (*sql.DB, error)
	listTablesFn               func(db *DB) ([]string, error)
	listColumnsFn              func(db *DB, tableName string) ([]ColumnInfo, error)
	getColumnMetadataFn        func(db *DB, tableName string, columnName string) (map[string]interface{}, error)
	getColumnCommentFn         func(ctx context.Context, db *DB, tableName string, columnName string) (string, error)
	getTableCommentFn          func(ctx context.Context, db *DB, tableName string) (string, error)
	genCommentSQLFn            func(db *DB, data *CommentData, enrichments map[string]bool) (string, error)
	genTableCommentSQLFn       func(db *DB, data *TableCommentData, enrichments map[string]bool) (string, error)
	genDeleteCommentSQLFn      func(ctx context.Context, db *DB, tableName string, columnName string) (string, error)
	getForeignKeysFn               func(db *DB, tableName string, columnName string) ([]ForeignKeyReference, error)
	genDeleteTableCommentSQLFn func(ctx context.Context, db *DB, tableName string) (string, error)

	// Call counters/trackers
	listTablesCalls               int
	listColumnsCalls              int
	getColumnCommentCalls         int
	getTableCommentCalls          int
	genCommentSQLCalls            int
	genTableCommentSQLCalls       int
	genDeleteCommentSQLCalls      int
	genDeleteTableCommentSQLCalls int
	getColumnMetadataCalls        int
}

func (m *mockDialectHandler) CreateCloudSQLPool(cfg config.DatabaseConfig) (*sql.DB, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.createCloudSQLPoolFn != nil {
		return m.createCloudSQLPoolFn(cfg)
	}
	// Return a mock DB by default
	mockDb, _, _ := sqlmock.New()
	return mockDb, nil
}

func (m *mockDialectHandler) CreateStandardPool(cfg config.DatabaseConfig) (*sql.DB, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.createStandardPoolFn != nil {
		return m.createStandardPoolFn(cfg)
	}
	mockDb, _, _ := sqlmock.New()
	return mockDb, nil
}

func (m *mockDialectHandler) QuoteIdentifier(name string) string { return fmt.Sprintf(`"%s"`, name) }

func (m *mockDialectHandler) ListTables(db *DB) ([]string, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.listTablesCalls++
	if m.listTablesFn != nil {
		return m.listTablesFn(db)
	}
	return []string{"table1"}, nil
}

func (m *mockDialectHandler) ListColumns(db *DB, tableName string) ([]ColumnInfo, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.listColumnsCalls++
	if m.listColumnsFn != nil {
		return m.listColumnsFn(db, tableName)
	}
	return []ColumnInfo{{Name: "col1", DataType: "int"}}, nil
}

func (m *mockDialectHandler) GetColumnMetadata(db *DB, tableName string, columnName string) (map[string]interface{}, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.getColumnMetadataCalls++
	if m.getColumnMetadataFn != nil {
		return m.getColumnMetadataFn(db, tableName, columnName)
	}
	return map[string]interface{}{"NullCount": int64(0)}, nil
}

func (m *mockDialectHandler) GetColumnComment(ctx context.Context, db *DB, tableName string, columnName string) (string, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.getColumnCommentCalls++
	if m.getColumnCommentFn != nil {
		return m.getColumnCommentFn(ctx, db, tableName, columnName)
	}
	return "mock comment", nil
}

func (m *mockDialectHandler) GetTableComment(ctx context.Context, db *DB, tableName string) (string, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.getTableCommentCalls++
	if m.getTableCommentFn != nil {
		return m.getTableCommentFn(ctx, db, tableName)
	}
	return "mock table comment", nil
}

func (m *mockDialectHandler) GenerateCommentSQL(db *DB, data *CommentData, enrichments map[string]bool) (string, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.genCommentSQLCalls++
	if m.genCommentSQLFn != nil {
		return m.genCommentSQLFn(db, data, enrichments)
	}
	return "COMMENT ON COLUMN mock", nil
}

func (m *mockDialectHandler) GenerateTableCommentSQL(db *DB, data *TableCommentData, enrichments map[string]bool) (string, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.genTableCommentSQLCalls++
	if m.genTableCommentSQLFn != nil {
		return m.genTableCommentSQLFn(db, data, enrichments)
	}
	return "COMMENT ON TABLE mock", nil
}

func (m *mockDialectHandler) GenerateDeleteCommentSQL(ctx context.Context, db *DB, tableName string, columnName string) (string, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.genDeleteCommentSQLCalls++
	if m.genDeleteCommentSQLFn != nil {
		return m.genDeleteCommentSQLFn(ctx, db, tableName, columnName)
	}
	return "DELETE COMMENT mock", nil
}

func (m *mockDialectHandler) GenerateDeleteTableCommentSQL(ctx context.Context, db *DB, tableName string) (string, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.genDeleteTableCommentSQLCalls++
	if m.genDeleteTableCommentSQLFn != nil {
		return m.genDeleteTableCommentSQLFn(ctx, db, tableName)
	}
	return "DELETE TABLE COMMENT mock", nil
}


func (m *mockDialectHandler) GetForeignKeys(db *DB, tableName string, columnName string) ([]ForeignKeyReference, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.getForeignKeysFn != nil {
		return m.getForeignKeysFn(db, tableName, columnName)
	}
	// Return empty slice as default
	return []ForeignKeyReference{}, nil
}
// Reset mock state
func (m *mockDialectHandler) Reset() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.createCloudSQLPoolFn = nil
	m.createStandardPoolFn = nil
	m.listTablesFn = nil
	m.listColumnsFn = nil
	m.getColumnMetadataFn = nil
	m.getColumnCommentFn = nil
	m.getTableCommentFn = nil
	m.genCommentSQLFn = nil
	m.genTableCommentSQLFn = nil
	m.genDeleteCommentSQLFn = nil
	m.genDeleteTableCommentSQLFn = nil
	m.listTablesCalls = 0
	m.listColumnsCalls = 0
	m.getColumnMetadataCalls = 0
	m.getColumnCommentCalls = 0
	m.getTableCommentCalls = 0
	m.genCommentSQLCalls = 0
	m.genTableCommentSQLCalls = 0
	m.genDeleteCommentSQLCalls = 0
	m.genDeleteTableCommentSQLCalls = 0
}

func TestRegisterAndGetDialectHandler(t *testing.T) {
	// Clean up handlers registered by other tests or init()
	mu.Lock()
	originalHandlers := make(map[string]DialectHandler)
	for k, v := range dialectHandlers {
		originalHandlers[k] = v
	}
	dialectHandlers = make(map[string]DialectHandler)
	mu.Unlock()

	// Restore original handlers after test
	defer func() {
		mu.Lock()
		dialectHandlers = originalHandlers
		mu.Unlock()
	}()

	mockHandler := &mockDialectHandler{}
	testDialect := "testdialect"

	// Test Get before Register
	_, err := GetDialectHandler(testDialect)
	if err == nil {
		t.Errorf("Expected error when getting unregistered dialect, got nil")
	}

	// Test Register
	RegisterDialectHandler(testDialect, mockHandler)

	// Test Get after Register
	handler, err := GetDialectHandler(testDialect)
	if err != nil {
		t.Errorf("Unexpected error getting registered dialect: %v", err)
	}
	if handler != mockHandler {
		t.Errorf("Got wrong handler back, expected mock, got %T", handler)
	}

	// Test Overwrite
	mockHandler2 := &mockDialectHandler{}
	RegisterDialectHandler(testDialect, mockHandler2)
	handler, err = GetDialectHandler(testDialect)
	if err != nil {
		t.Errorf("Unexpected error getting overwritten dialect: %v", err)
	}
	if handler != mockHandler2 {
		t.Errorf("Got wrong handler back after overwrite, expected mock2, got %T", handler)
	}

	// Test Get unknown dialect again
	_, err = GetDialectHandler("unknown")
	if err == nil {
		t.Errorf("Expected error when getting unknown dialect, got nil")
	}
}

// Helper to create a DB with a mock handler and pool for delegation tests
func newTestDBWithMockHandler(t *testing.T, handler DialectHandler) (*DB, sqlmock.Sqlmock) {
	t.Helper()
	mockDb, mock, err := sqlmock.New(sqlmock.MonitorPingsOption(true))
	if err != nil {
		t.Fatalf("An error '%s' was not expected when opening a stub database connection", err)
	}

	// Mock Ping if needed by New
	mock.ExpectPing()

	return &DB{
		Pool:    mockDb,
		Handler: handler,
		Config:  config.DatabaseConfig{Dialect: "mock"},
	}, mock
}

func TestDBMethodsDelegateToHandler(t *testing.T) {
	mockHandler := &mockDialectHandler{}
	db, mock := newTestDBWithMockHandler(t, mockHandler)
	defer db.Close()
	ctx := context.Background()

	tests := []struct {
		name          string
		dbMethodCall  func() error // Function to call the DB method
		expectedCalls *int         // Pointer to the mock handler's call counter
	}{
		{"ListTables", func() error { _, err := db.ListTables(); return err }, &mockHandler.listTablesCalls},
		{"ListColumns", func() error { _, err := db.ListColumns("t1"); return err }, &mockHandler.listColumnsCalls},
		{"GetColumnMetadata", func() error { _, err := db.GetColumnMetadata("t1", "c1"); return err }, &mockHandler.getColumnMetadataCalls},
		{"GetColumnComment", func() error { _, err := db.GetColumnComment(ctx, "t1", "c1"); return err }, &mockHandler.getColumnCommentCalls},
		{"GetTableComment", func() error { _, err := db.GetTableComment(ctx, "t1"); return err }, &mockHandler.getTableCommentCalls},
		{"GenerateCommentSQL", func() error { _, err := db.GenerateCommentSQL(&CommentData{}, nil); return err }, &mockHandler.genCommentSQLCalls},
		{"GenerateTableCommentSQL", func() error { _, err := db.GenerateTableCommentSQL(&TableCommentData{}, nil); return err }, &mockHandler.genTableCommentSQLCalls},
		{"GenerateDeleteCommentSQL", func() error { _, err := db.GenerateDeleteCommentSQL(ctx, "t1", "c1"); return err }, &mockHandler.genDeleteCommentSQLCalls},
		{"GenerateDeleteTableCommentSQL", func() error { _, err := db.GenerateDeleteTableCommentSQL(ctx, "t1"); return err }, &mockHandler.genDeleteTableCommentSQLCalls},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			mockHandler.Reset() // Reset counters before each test
			initialCalls := *tt.expectedCalls

			err := tt.dbMethodCall()
			if err != nil {
				// We don't expect errors from the mock unless specifically configured
				t.Errorf("db.%s() returned unexpected error: %v", tt.name, err)
			}

			if *tt.expectedCalls != initialCalls+1 {
				t.Errorf("Expected handler method for %s to be called once, got %d calls", tt.name, *tt.expectedCalls)
			}
		})
	}

	// Test Ping separately
	err := db.Ping(ctx)
	if err != nil {
		t.Errorf("db.Ping() returned unexpected error: %v", err)
	}

	// Test GetConfig
	cfg := db.GetConfig()
	if cfg.Dialect != "mock" {
		t.Errorf("db.GetConfig() returned wrong dialect, got %s, want mock", cfg.Dialect)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("there were unfulfilled expectations: %s", err)
	}
}

func TestExecuteSQLStatements(t *testing.T) {
	ctx := context.Background()

	tests := []struct {
		name          string
		sqlStatements []string
		mockSetup     func(mock sqlmock.Sqlmock) // Setup mock expectations
		expectedError bool
	}{
		{
			name:          "Success case",
			sqlStatements: []string{"SELECT 1;", "UPDATE t SET c=1;"},
			mockSetup: func(mock sqlmock.Sqlmock) {
				mock.ExpectBegin()
				mock.ExpectExec("SELECT 1;").WillReturnResult(sqlmock.NewResult(0, 0))
				mock.ExpectExec("UPDATE t SET c=1;").WillReturnResult(sqlmock.NewResult(0, 1))
				mock.ExpectCommit()
			},
			expectedError: false,
		},
		{
			name:          "Empty statements list",
			sqlStatements: []string{},
			mockSetup:     func(mock sqlmock.Sqlmock) { /* No expectations */ },
			expectedError: false,
		},
		{
			name:          "Statements with only whitespace",
			sqlStatements: []string{"  ", "\n\t ", ";"},
			mockSetup: func(mock sqlmock.Sqlmock) {
				mock.ExpectBegin()
				mock.ExpectExec(";").WillReturnResult(sqlmock.NewResult(0, 0))
				mock.ExpectCommit()
			},
			expectedError: false,
		},
		{
			name:          "Begin fails",
			sqlStatements: []string{"SELECT 1;"},
			mockSetup: func(mock sqlmock.Sqlmock) {
				mock.ExpectBegin().WillReturnError(errors.New("begin failed"))
				// No Exec or Commit/Rollback expected
			},
			expectedError: true,
		},
		{
			name:          "Exec fails",
			sqlStatements: []string{"SELECT 1;", "BAD SQL;", "SELECT 3;"},
			mockSetup: func(mock sqlmock.Sqlmock) {
				mock.ExpectBegin()
				mock.ExpectExec("SELECT 1;").WillReturnResult(sqlmock.NewResult(0, 0))
				mock.ExpectExec("BAD SQL;").WillReturnError(errors.New("syntax error"))
				mock.ExpectRollback() // Expect rollback after error
			},
			expectedError: true,
		},
		{
			name:          "Commit fails",
			sqlStatements: []string{"SELECT 1;"},
			mockSetup: func(mock sqlmock.Sqlmock) {
				mock.ExpectBegin()
				mock.ExpectExec("SELECT 1;").WillReturnResult(sqlmock.NewResult(0, 0))
				mock.ExpectCommit().WillReturnError(errors.New("commit failed"))
			},
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			mockDb, mock, err := sqlmock.New()
			if err != nil {
				t.Fatalf("An error '%s' was not expected when opening a stub database connection", err)
			}
			defer mockDb.Close()

			db := &DB{Pool: mockDb} // Simple DB struct for this test

			tt.mockSetup(mock)

			err = db.ExecuteSQLStatements(ctx, tt.sqlStatements)

			if (err != nil) != tt.expectedError {
				t.Errorf("ExecuteSQLStatements() error = %v, expectedError %v", err, tt.expectedError)
			}

			// Verify all expectations were met
			if err := mock.ExpectationsWereMet(); err != nil {
				t.Errorf("there were unfulfilled expectations: %s", err)
			}
		})
	}
}

package postgres

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"regexp"
	"testing"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/config"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
	"github.com/lib/pq"
)

// Helper to create a mock DB and handler for testing
func newMockPostgresDB(t *testing.T) (*database.DB, sqlmock.Sqlmock, *postgresHandler) {
	t.Helper()
	mockDb, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("An error '%s' was not expected when opening a stub database connection", err)
	}

	handler := postgresHandler{}
	db := &database.DB{
		Pool:    mockDb,
		Handler: &handler,
		Config: config.DatabaseConfig{
			Dialect:            "postgres",
			UpdateExistingMode: "overwrite",
		},
	}
	return db, mock, &handler
}

func TestPostgresQuoteIdentifier(t *testing.T) {
	handler := postgresHandler{}

	tests := []struct {
		name string
		in   string
		want string
	}{
		{"Simple name", "mytable", `"mytable"`},
		{"Name with spaces", "my table", `"my table"`},
		{"Name with quotes", `my"table`, `"my""table"`},
		{"Empty name", "", `""`},
		{"Keyword", "user", `"user"`},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := handler.QuoteIdentifier(tt.in); got != tt.want {
				t.Errorf("QuoteIdentifier() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestPostgresListTables(t *testing.T) {
	db, mock, handler := newMockPostgresDB(t)
	defer db.Close()

	query := `
		SELECT table_name
		FROM information_schema.tables
		WHERE table_schema = current_schema()
		AND table_type = 'BASE TABLE'
		ORDER BY table_name;`

	expectedQuery := regexp.QuoteMeta(query)

	t.Run("Success", func(t *testing.T) {
		rows := sqlmock.NewRows([]string{"table_name"}).
			AddRow("users").
			AddRow("products")
		mock.ExpectQuery(expectedQuery).WillReturnRows(rows)

		tables, err := handler.ListTables(db)
		if err != nil {
			t.Fatalf("ListTables() unexpected error: %v", err)
		}

		if len(tables) != 2 || tables[0] != "users" || tables[1] != "products" {
			t.Errorf("ListTables() got %v, want [users products]", tables)
		}
	})

	t.Run("Query Error", func(t *testing.T) {
		dbError := errors.New("connection failed")
		mock.ExpectQuery(expectedQuery).WillReturnError(dbError)

		_, err := handler.ListTables(db)
		if err == nil {
			t.Fatalf("ListTables() expected error, got nil")
		}
		if !errors.Is(err, dbError) {
			t.Errorf("ListTables() got error %v, want error containing %v", err, dbError)
		}
	})

	t.Run("Scan Error", func(t *testing.T) {
		rows := sqlmock.NewRows([]string{"table_name"}).
			AddRow("users").
			AddRow(nil) // Simulate a scan error
		mock.ExpectQuery(expectedQuery).WillReturnRows(rows)

		_, err := handler.ListTables(db)
		if err == nil {
			t.Fatalf("ListTables() expected scan error, got nil")
		}
	})

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("there were unfulfilled expectations: %s", err)
	}
}

func TestPostgresListColumns(t *testing.T) {
	db, mock, handler := newMockPostgresDB(t)
	defer db.Close()
	tableName := "users"

	query := `
		SELECT column_name, data_type
		FROM information_schema.columns
		WHERE table_schema = current_schema()
		AND table_name = $1
		ORDER BY ordinal_position;`
	expectedQuery := regexp.QuoteMeta(query)

	t.Run("Success", func(t *testing.T) {
		rows := sqlmock.NewRows([]string{"column_name", "data_type"}).
			AddRow("id", "integer").
			AddRow("email", "character varying")
		mock.ExpectQuery(expectedQuery).WithArgs(tableName).WillReturnRows(rows)

		cols, err := handler.ListColumns(db, tableName)
		if err != nil {
			t.Fatalf("ListColumns() unexpected error: %v", err)
		}

		expectedCols := []database.ColumnInfo{
			{Name: "id", DataType: "integer"},
			{Name: "email", DataType: "character varying"},
		}
		if len(cols) != len(expectedCols) {
			t.Fatalf("ListColumns() got %d columns, want %d", len(cols), len(expectedCols))
		}
		for i := range cols {
			if cols[i] != expectedCols[i] {
				t.Errorf("ListColumns() col %d got %+v, want %+v", i, cols[i], expectedCols[i])
			}
		}
	})

	t.Run("Query Error", func(t *testing.T) {
		dbError := errors.New("table not found")
		mock.ExpectQuery(expectedQuery).WithArgs(tableName).WillReturnError(dbError)

		_, err := handler.ListColumns(db, tableName)
		if err == nil {
			t.Fatalf("ListColumns() expected error, got nil")
		}
		if !errors.Is(err, dbError) {
			t.Errorf("ListColumns() got error %v, want error containing %v", err, dbError)
		}
	})

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("there were unfulfilled expectations: %s", err)
	}
}

func TestPostgresGetColumnComment(t *testing.T) {
	db, mock, handler := newMockPostgresDB(t)
	defer db.Close()
	ctx := context.Background()
	tableName := "users"
	columnName := "email"

	query := `
		SELECT description
		FROM pg_catalog.pg_description
		JOIN pg_catalog.pg_class c ON pg_description.objoid = c.oid
		JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
		JOIN pg_catalog.pg_attribute a ON pg_description.objoid = a.attrelid AND pg_description.objsubid = a.attnum
		WHERE n.nspname = current_schema()
		  AND c.relname = $1
		  AND a.attname = $2;
	`
	expectedQuery := regexp.QuoteMeta(query)

	t.Run("Comment Exists", func(t *testing.T) {
		expectedComment := "User email address <gemini>Some data</gemini>"
		rows := sqlmock.NewRows([]string{"description"}).AddRow(expectedComment)
		mock.ExpectQuery(expectedQuery).WithArgs(tableName, columnName).WillReturnRows(rows)

		comment, err := handler.GetColumnComment(ctx, db, tableName, columnName)
		if err != nil {
			t.Fatalf("GetColumnComment() unexpected error: %v", err)
		}
		if comment != expectedComment {
			t.Errorf("GetColumnComment() got %q, want %q", comment, expectedComment)
		}
	})

	t.Run("Comment Not Found", func(t *testing.T) {
		mock.ExpectQuery(expectedQuery).WithArgs(tableName, columnName).WillReturnError(sql.ErrNoRows)

		comment, err := handler.GetColumnComment(ctx, db, tableName, columnName)
		if err != nil {
			t.Fatalf("GetColumnComment() unexpected error: %v", err)
		}
		if comment != "" {
			t.Errorf("GetColumnComment() got %q, want empty string", comment)
		}
	})

	t.Run("Database Error", func(t *testing.T) {
		dbError := errors.New("connection lost")
		mock.ExpectQuery(expectedQuery).WithArgs(tableName, columnName).WillReturnError(dbError)

		_, err := handler.GetColumnComment(ctx, db, tableName, columnName)
		if err == nil {
			t.Fatalf("GetColumnComment() expected error, got nil")
		}
		if !errors.Is(err, dbError) {
			t.Errorf("GetColumnComment() got error %v, want error containing %v", err, dbError)
		}
	})

	// Check expectations after all subtests
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("there were unfulfilled expectations: %s", err)
	}
}

func TestPostgresGenerateCommentSQL(t *testing.T) {
	data := &database.CommentData{
		TableName:      "users",
		ColumnName:     "email",
		ColumnDataType: "character varying",
		ExampleValues:  []string{"test@example.com", "another'email@test.co"},
		Description:    "User Email",
		DistinctCount:  150,
		NullCount:      5,
	}
	enrichments := map[string]bool{ // Request all
		"description":     true,
		"examples":        true,
		"distinct_values": true,
		"null_count":      true,
	}

	getCommentQuery := regexp.QuoteMeta(`
		SELECT description
		FROM pg_catalog.pg_description
		JOIN pg_catalog.pg_class c ON pg_description.objoid = c.oid
		JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
		JOIN pg_catalog.pg_attribute a ON pg_description.objoid = a.attrelid AND pg_description.objsubid = a.attnum
		WHERE n.nspname = current_schema()
		  AND c.relname = $1
		  AND a.attname = $2;
	`)

	t.Run("New Comment", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		defer db.Close()

		// Expect GetColumnComment to find nothing
		mock.ExpectQuery(getCommentQuery).
			WithArgs(data.TableName, data.ColumnName).
			WillReturnError(sql.ErrNoRows)

		sqlStmt, err := handler.GenerateCommentSQL(db, data, enrichments)
		if err != nil {
			t.Fatalf("GenerateCommentSQL() unexpected error: %v", err)
		}

		expectedMetadata := "User Email | Examples: 'test@example.com', 'another''email@test.co' | Distinct: 150 | Nulls: 5"
		expectedFinalComment := fmt.Sprintf("<gemini>%s</gemini>", expectedMetadata)
		expectedSQL := fmt.Sprintf(`COMMENT ON COLUMN "users"."email" IS %s;`, pq.QuoteLiteral(expectedFinalComment))

		if sqlStmt != expectedSQL {
			t.Errorf("GenerateCommentSQL() mismatch:\ngot:  %s\nwant: %s", sqlStmt, expectedSQL)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("Overwrite Existing Comment", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		db.Config.UpdateExistingMode = "overwrite" // Explicitly set
		defer db.Close()

		existingComment := "Old user comment <gemini>Old Data</gemini>"
		rows := sqlmock.NewRows([]string{"description"}).AddRow(existingComment)
		mock.ExpectQuery(getCommentQuery).
			WithArgs(data.TableName, data.ColumnName).
			WillReturnRows(rows)

		sqlStmt, err := handler.GenerateCommentSQL(db, data, enrichments)
		if err != nil {
			t.Fatalf("GenerateCommentSQL() unexpected error: %v", err)
		}

		expectedMetadata := "User Email | Examples: 'test@example.com', 'another''email@test.co' | Distinct: 150 | Nulls: 5"
		expectedFinalComment := fmt.Sprintf("Old user comment <gemini>%s</gemini>", expectedMetadata) // Overwrites <gemini> content
		expectedSQL := fmt.Sprintf(`COMMENT ON COLUMN "users"."email" IS %s;`, pq.QuoteLiteral(expectedFinalComment))

		if sqlStmt != expectedSQL {
			t.Errorf("GenerateCommentSQL() mismatch:\ngot:  %s\nwant: %s", sqlStmt, expectedSQL)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("Append To Existing Comment", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		db.Config.UpdateExistingMode = "append" // Set append mode
		defer db.Close()

		existingComment := "Old user comment <gemini>Old Data</gemini>"
		rows := sqlmock.NewRows([]string{"description"}).AddRow(existingComment)
		mock.ExpectQuery(getCommentQuery).
			WithArgs(data.TableName, data.ColumnName).
			WillReturnRows(rows)

		sqlStmt, err := handler.GenerateCommentSQL(db, data, enrichments)
		if err != nil {
			t.Fatalf("GenerateCommentSQL() unexpected error: %v", err)
		}

		expectedMetadata := "User Email | Examples: 'test@example.com', 'another''email@test.co' | Distinct: 150 | Nulls: 5"
		expectedFinalComment := fmt.Sprintf("Old user comment <gemini>Old Data | %s</gemini>", expectedMetadata) // Appends to <gemini> content
		expectedSQL := fmt.Sprintf(`COMMENT ON COLUMN "users"."email" IS %s;`, pq.QuoteLiteral(expectedFinalComment))

		if sqlStmt != expectedSQL {
			t.Errorf("GenerateCommentSQL() mismatch:\ngot:  %s\nwant: %s", sqlStmt, expectedSQL)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("Error getting existing comment", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		defer db.Close()

		dbError := errors.New("some read error")
		mock.ExpectQuery(getCommentQuery).
			WithArgs(data.TableName, data.ColumnName).
			WillReturnError(dbError)

		// Should still generate the SQL, but proceed as if comment was empty
		sqlStmt, err := handler.GenerateCommentSQL(db, data, enrichments)
		if err != nil {
			t.Fatalf("GenerateCommentSQL() unexpected error: %v", err)
		}

		// Expects the new comment structure as if existing was empty
		expectedMetadata := "User Email | Examples: 'test@example.com', 'another''email@test.co' | Distinct: 150 | Nulls: 5"
		expectedFinalComment := fmt.Sprintf("<gemini>%s</gemini>", expectedMetadata)
		expectedSQL := fmt.Sprintf(`COMMENT ON COLUMN "users"."email" IS %s;`, pq.QuoteLiteral(expectedFinalComment))

		if sqlStmt != expectedSQL {
			t.Errorf("GenerateCommentSQL() mismatch after error:\ngot:  %s\nwant: %s", sqlStmt, expectedSQL)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("Invalid Input", func(t *testing.T) {
		db, _, handler := newMockPostgresDB(t)
		defer db.Close()
		_, err := handler.GenerateCommentSQL(db, nil, enrichments)
		if err == nil {
			t.Error("Expected error for nil data, got nil")
		}
		_, err = handler.GenerateCommentSQL(db, &database.CommentData{}, enrichments) // Missing table/column name
		if err == nil {
			t.Error("Expected error for empty table/column name, got nil")
		}
	})
}

func TestPostgresGenerateDeleteCommentSQL(t *testing.T) {
	ctx := context.Background()
	tableName := "users"
	columnName := "email"

	getCommentQuery := regexp.QuoteMeta(`
		SELECT description
		FROM pg_catalog.pg_description
		JOIN pg_catalog.pg_class c ON pg_description.objoid = c.oid
		JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
		JOIN pg_catalog.pg_attribute a ON pg_description.objoid = a.attrelid AND pg_description.objsubid = a.attnum
		WHERE n.nspname = current_schema()
		  AND c.relname = $1
		  AND a.attname = $2;
	`)

	t.Run("Delete existing tagged comment", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		defer db.Close()

		existingComment := "Keep this part <gemini>Remove this data</gemini> Also keep this"
		rows := sqlmock.NewRows([]string{"description"}).AddRow(existingComment)
		mock.ExpectQuery(getCommentQuery).WithArgs(tableName, columnName).WillReturnRows(rows)

		sqlStmt, err := handler.GenerateDeleteCommentSQL(ctx, db, tableName, columnName)
		if err != nil {
			t.Fatalf("GenerateDeleteCommentSQL() unexpected error: %v", err)
		}

		expectedFinalComment := "Keep this part Also keep this"
		expectedSQL := fmt.Sprintf(`COMMENT ON COLUMN "users"."email" IS %s;`, pq.QuoteLiteral(expectedFinalComment))

		if sqlStmt != expectedSQL {
			t.Errorf("GenerateDeleteCommentSQL() mismatch:\ngot:  %s\nwant: %s", sqlStmt, expectedSQL)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("Comment exists but no tag", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		defer db.Close()

		existingComment := "Just a regular comment"
		rows := sqlmock.NewRows([]string{"description"}).AddRow(existingComment)
		mock.ExpectQuery(getCommentQuery).WithArgs(tableName, columnName).WillReturnRows(rows)

		// Expect empty SQL because MergeComments("", "") on the existing comment results in no change
		sqlStmt, err := handler.GenerateDeleteCommentSQL(ctx, db, tableName, columnName)
		if err != nil {
			t.Fatalf("GenerateDeleteCommentSQL() unexpected error: %v", err)
		}
		if sqlStmt != "" {
			t.Errorf("GenerateDeleteCommentSQL() expected empty SQL, got: %s", sqlStmt)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("No existing comment", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		defer db.Close()

		mock.ExpectQuery(getCommentQuery).WithArgs(tableName, columnName).WillReturnError(sql.ErrNoRows)

		// Expect empty SQL because there's nothing to delete
		sqlStmt, err := handler.GenerateDeleteCommentSQL(ctx, db, tableName, columnName)
		if err != nil {
			t.Fatalf("GenerateDeleteCommentSQL() unexpected error: %v", err)
		}
		if sqlStmt != "" {
			t.Errorf("GenerateDeleteCommentSQL() expected empty SQL, got: %s", sqlStmt)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("Error getting existing comment", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		defer db.Close()

		dbError := errors.New("connection failed")
		mock.ExpectQuery(getCommentQuery).WithArgs(tableName, columnName).WillReturnError(dbError)

		// Expect an error from GenerateDeleteCommentSQL itself
		_, err := handler.GenerateDeleteCommentSQL(ctx, db, tableName, columnName)
		if err == nil {
			t.Fatal("GenerateDeleteCommentSQL() expected error, got nil")
		}
		if !errors.Is(err, dbError) { // Check if the underlying error matches
			t.Errorf("GetColumnComment() got error %v, want error containing %v", err, dbError)
		}

		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("Invalid Input", func(t *testing.T) {
		db, _, handler := newMockPostgresDB(t)
		defer db.Close()
		_, err := handler.GenerateDeleteCommentSQL(ctx, db, "", "col")
		if err == nil {
			t.Error("Expected error for empty table name, got nil")
		}
		_, err = handler.GenerateDeleteCommentSQL(ctx, db, "tab", "")
		if err == nil {
			t.Error("Expected error for empty column name, got nil")
		}
	})
}

func TestPostgresGetColumnMetadata(t *testing.T) {
	db, mock, handler := newMockPostgresDB(t)
	defer db.Close()
	tableName := "products"
	columnName := "price"

	distinctQuery := regexp.QuoteMeta(fmt.Sprintf(`SELECT COUNT(DISTINCT %s::text) FROM %s`, handler.QuoteIdentifier(columnName), handler.QuoteIdentifier(tableName)))
	nullQuery := regexp.QuoteMeta(fmt.Sprintf(`SELECT COUNT(*) FROM %s WHERE %s IS NULL`, handler.QuoteIdentifier(tableName), handler.QuoteIdentifier(columnName)))
	exampleQuery := regexp.QuoteMeta(fmt.Sprintf(`SELECT DISTINCT %s::text FROM %s WHERE %s IS NOT NULL LIMIT 3`, handler.QuoteIdentifier(columnName), handler.QuoteIdentifier(tableName), handler.QuoteIdentifier(columnName)))

	t.Run("Success", func(t *testing.T) {
		mock.ExpectQuery(distinctQuery).WillReturnRows(sqlmock.NewRows([]string{"count"}).AddRow(int64(50)))
		mock.ExpectQuery(nullQuery).WillReturnRows(sqlmock.NewRows([]string{"count"}).AddRow(int64(3)))
		mock.ExpectQuery(exampleQuery).WillReturnRows(sqlmock.NewRows([]string{"price"}).AddRow("10.99").AddRow("25.50").AddRow("99.00"))

		metadata, err := handler.GetColumnMetadata(db, tableName, columnName)
		if err != nil {
			t.Fatalf("GetColumnMetadata() unexpected error: %v", err)
		}

		if dc, ok := metadata["DistinctCount"].(int64); !ok || dc != 50 {
			t.Errorf("Expected DistinctCount 50, got %v (%T)", metadata["DistinctCount"], metadata["DistinctCount"])
		}
		if nc, ok := metadata["NullCount"].(int64); !ok || nc != 3 {
			t.Errorf("Expected NullCount 3, got %v (%T)", metadata["NullCount"], metadata["NullCount"])
		}
		if ev, ok := metadata["ExampleValues"].([]string); !ok || len(ev) != 3 || ev[0] != "10.99" || ev[1] != "25.50" || ev[2] != "99.00" {
			t.Errorf("Expected ExampleValues ['10.99', '25.50', '99.00'], got %v (%T)", metadata["ExampleValues"], metadata["ExampleValues"])
		}
	})

	t.Run("Distinct Count Fails", func(t *testing.T) {
		// Distinct count fails, but others succeed
		mock.ExpectQuery(distinctQuery).WillReturnError(errors.New("distinct error"))
		mock.ExpectQuery(nullQuery).WillReturnRows(sqlmock.NewRows([]string{"count"}).AddRow(int64(5)))
		mock.ExpectQuery(exampleQuery).WillReturnRows(sqlmock.NewRows([]string{"price"}).AddRow("1.00"))

		metadata, err := handler.GetColumnMetadata(db, tableName, columnName)
		if err != nil {
			// The function should handle distinct error gracefully and continue
			t.Fatalf("GetColumnMetadata() unexpected error: %v", err)
		}

		// Expect -1 for distinct count when it fails
		if dc, ok := metadata["DistinctCount"].(int64); !ok || dc != -1 {
			t.Errorf("Expected DistinctCount -1 on error, got %v (%T)", metadata["DistinctCount"], metadata["DistinctCount"])
		}
		if nc, ok := metadata["NullCount"].(int64); !ok || nc != 5 {
			t.Errorf("Expected NullCount 5, got %v (%T)", metadata["NullCount"], metadata["NullCount"])
		}
		if ev, ok := metadata["ExampleValues"].([]string); !ok || len(ev) != 1 || ev[0] != "1.00" {
			t.Errorf("Expected ExampleValues ['1.00'], got %v (%T)", metadata["ExampleValues"], metadata["ExampleValues"])
		}
	})

	t.Run("Null Count Fails", func(t *testing.T) {
		// Null count fails, should return an error for the whole function
		mock.ExpectQuery(distinctQuery).WillReturnRows(sqlmock.NewRows([]string{"count"}).AddRow(int64(10)))
		mock.ExpectQuery(nullQuery).WillReturnError(errors.New("null count error"))
		// Example query might not even be reached

		_, err := handler.GetColumnMetadata(db, tableName, columnName)
		if err == nil {
			t.Fatalf("GetColumnMetadata() expected error when null count fails, got nil")
		}
	})

	t.Run("Example Query Fails", func(t *testing.T) {
		// Example query fails, should return an error
		mock.ExpectQuery(distinctQuery).WillReturnRows(sqlmock.NewRows([]string{"count"}).AddRow(int64(10)))
		mock.ExpectQuery(nullQuery).WillReturnRows(sqlmock.NewRows([]string{"count"}).AddRow(int64(0)))
		mock.ExpectQuery(exampleQuery).WillReturnError(errors.New("example fetch error"))

		_, err := handler.GetColumnMetadata(db, tableName, columnName)
		if err == nil {
			t.Fatalf("GetColumnMetadata() expected error when example query fails, got nil")
		}
	})

	// Check expectations after all subtests
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("there were unfulfilled expectations: %s", err)
	}
}

func TestPostgresFormatExampleValues(t *testing.T) {
	handler := postgresHandler{}

	tests := []struct {
		name   string
		values []string
		want   string
	}{
		{"No values", []string{}, ""},
		{"Single value", []string{"abc"}, "Examples: 'abc'"},
		{"Multiple values", []string{"abc", "123", "def"}, "Examples: 'abc', '123', 'def'"},
		{"Value with single quote", []string{"it's"}, "Examples: 'it''s'"},
		{"Value with backslash", []string{`a\b`}, `Examples:  E'a\\b'`}, // pq handles this with E''
		{"Mixed values", []string{"a", "b'c", `d\e`}, `Examples: 'a', 'b''c',  E'd\\e'`},
		{"Empty string value", []string{""}, "Examples: ''"},
		{"Mixed with empty", []string{"a", "", "b"}, "Examples: 'a', '', 'b'"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := handler.formatExampleValues(tt.values); got != tt.want {
				t.Errorf("formatExampleValues() = %q, want %q", got, tt.want)
			}
		})
	}
}

func TestPostgresGetTableComment(t *testing.T) {
	db, mock, handler := newMockPostgresDB(t)
	defer db.Close()
	ctx := context.Background()
	tableName := "orders"

	query := `
        SELECT pg_catalog.obj_description(c.oid, 'pg_class')
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = current_schema()
          AND c.relname = $1;
    `
	expectedQuery := regexp.QuoteMeta(query)

	t.Run("Comment Exists", func(t *testing.T) {
		expectedComment := "Customer orders <gemini>...</gemini>"
		rows := sqlmock.NewRows([]string{"obj_description"}).AddRow(expectedComment)
		mock.ExpectQuery(expectedQuery).WithArgs(tableName).WillReturnRows(rows)

		comment, err := handler.GetTableComment(ctx, db, tableName)
		if err != nil {
			t.Fatalf("GetTableComment() unexpected error: %v", err)
		}
		if comment != expectedComment {
			t.Errorf("GetTableComment() got %q, want %q", comment, expectedComment)
		}
	})

	t.Run("Comment Not Found", func(t *testing.T) {
		mock.ExpectQuery(expectedQuery).WithArgs(tableName).WillReturnError(sql.ErrNoRows)

		comment, err := handler.GetTableComment(ctx, db, tableName)
		if err != nil {
			t.Fatalf("GetTableComment() unexpected error: %v", err)
		}
		if comment != "" {
			t.Errorf("GetTableComment() got %q, want empty string", comment)
		}
	})

	t.Run("Database Error", func(t *testing.T) {
		dbError := errors.New("invalid table oid")
		mock.ExpectQuery(expectedQuery).WithArgs(tableName).WillReturnError(dbError)

		_, err := handler.GetTableComment(ctx, db, tableName)
		if err == nil {
			t.Fatalf("GetTableComment() expected error, got nil")
		}
		if !errors.Is(err, dbError) {
			t.Errorf("GetTableComment() got error %v, want error containing %v", err, dbError)
		}
	})

	// Check expectations after all subtests
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("there were unfulfilled expectations: %s", err)
	}
}

func TestPostgresGenerateTableCommentSQL(t *testing.T) {
	tableName := "orders"
	data := &database.TableCommentData{
		TableName:   tableName,
		Description: "Table Description",
	}
	enrichments := map[string]bool{"description": true}

	getTableCommentQuery := regexp.QuoteMeta(`
        SELECT pg_catalog.obj_description(c.oid, 'pg_class')
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = current_schema()
          AND c.relname = $1;
    `)

	t.Run("Error getting existing comment", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		defer db.Close()

		dbError := errors.New("read error")
		mock.ExpectQuery(getTableCommentQuery).WithArgs(tableName).WillReturnError(dbError)

		// Should still generate SQL, treating existing as empty
		sqlStmt, err := handler.GenerateTableCommentSQL(db, data, enrichments)
		if err != nil {
			t.Fatalf("GenerateTableCommentSQL() unexpected error: %v", err)
		}

		data.Description = "Table Description"                       // Reset to original description
		expectedFinalComment := "<gemini>Table Description</gemini>" // Reset data description
		expectedSQL := fmt.Sprintf(`COMMENT ON TABLE "orders" IS %s;`, pq.QuoteLiteral(expectedFinalComment))

		if sqlStmt != expectedSQL {
			t.Errorf("GenerateTableCommentSQL() mismatch after error:\ngot:  %s\nwant: %s", sqlStmt, expectedSQL)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("New Table Comment", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		defer db.Close()

		mock.ExpectQuery(getTableCommentQuery).WithArgs(tableName).WillReturnError(sql.ErrNoRows)

		sqlStmt, err := handler.GenerateTableCommentSQL(db, data, enrichments)
		if err != nil {
			t.Fatalf("GenerateTableCommentSQL() unexpected error: %v", err)
		}

		expectedFinalComment := "<gemini>Table Description</gemini>"
		expectedSQL := fmt.Sprintf(`COMMENT ON TABLE "orders" IS %s;`, pq.QuoteLiteral(expectedFinalComment))

		if sqlStmt != expectedSQL {
			t.Errorf("GenerateTableCommentSQL() mismatch:\ngot:  %s\nwant: %s", sqlStmt, expectedSQL)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("Overwrite Existing Table Comment", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		db.Config.UpdateExistingMode = "overwrite"
		defer db.Close()

		existingComment := "Old table def <gemini>Old data</gemini>"
		rows := sqlmock.NewRows([]string{"obj_description"}).AddRow(existingComment)
		mock.ExpectQuery(getTableCommentQuery).WithArgs(tableName).WillReturnRows(rows)

		sqlStmt, err := handler.GenerateTableCommentSQL(db, data, enrichments)
		if err != nil {
			t.Fatalf("GenerateTableCommentSQL() unexpected error: %v", err)
		}

		expectedFinalComment := "Old table def <gemini>Table Description</gemini>"
		expectedSQL := fmt.Sprintf(`COMMENT ON TABLE "orders" IS %s;`, pq.QuoteLiteral(expectedFinalComment))

		if sqlStmt != expectedSQL {
			t.Errorf("GenerateTableCommentSQL() mismatch:\ngot:  %s\nwant: %s", sqlStmt, expectedSQL)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("Append To Existing Table Comment", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		db.Config.UpdateExistingMode = "append"
		defer db.Close()

		existingComment := "Old table def <gemini>Old data</gemini>"
		rows := sqlmock.NewRows([]string{"obj_description"}).AddRow(existingComment)
		mock.ExpectQuery(getTableCommentQuery).WithArgs(tableName).WillReturnRows(rows)

		sqlStmt, err := handler.GenerateTableCommentSQL(db, data, enrichments)
		if err != nil {
			t.Fatalf("GenerateTableCommentSQL() unexpected error: %v", err)
		}

		expectedFinalComment := "Old table def <gemini>Old data | Table Description</gemini>"
		expectedSQL := fmt.Sprintf(`COMMENT ON TABLE "orders" IS %s;`, pq.QuoteLiteral(expectedFinalComment))

		if sqlStmt != expectedSQL {
			t.Errorf("GenerateTableCommentSQL() mismatch:\ngot:  %s\nwant: %s", sqlStmt, expectedSQL)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("No change needed", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		db.Config.UpdateExistingMode = "overwrite"
		defer db.Close()

		// Set the new description to exactly match the gemini part of existing
		data.Description = "Existing data"
		existingComment := "Prefix <gemini>Existing data</gemini>"
		rows := sqlmock.NewRows([]string{"obj_description"}).AddRow(existingComment)
		mock.ExpectQuery(getTableCommentQuery).WithArgs(tableName).WillReturnRows(rows)

		sqlStmt, err := handler.GenerateTableCommentSQL(db, data, enrichments)
		if err != nil {
			t.Fatalf("GenerateTableCommentSQL() unexpected error: %v", err)
		}

		// Expect empty SQL because the merged comment is identical to existing
		if sqlStmt != "" {
			t.Errorf("GenerateTableCommentSQL() expected empty SQL for no change, got: %s", sqlStmt)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("Invalid Input", func(t *testing.T) {
		db, _, handler := newMockPostgresDB(t)
		defer db.Close()
		_, err := handler.GenerateTableCommentSQL(db, nil, enrichments)
		if err == nil {
			t.Error("Expected error for nil data, got nil")
		}
		_, err = handler.GenerateTableCommentSQL(db, &database.TableCommentData{}, enrichments) // Missing table name
		if err == nil {
			t.Error("Expected error for empty table name, got nil")
		}
	})
}

func TestPostgresGenerateDeleteTableCommentSQL(t *testing.T) {
	ctx := context.Background()
	tableName := "orders"

	getTableCommentQuery := regexp.QuoteMeta(`
        SELECT pg_catalog.obj_description(c.oid, 'pg_class')
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = current_schema()
          AND c.relname = $1;
    `)

	t.Run("Delete existing tagged table comment", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		defer db.Close()

		existingComment := "Keep this <gemini>Delete This</gemini> And This"
		rows := sqlmock.NewRows([]string{"obj_description"}).AddRow(existingComment)
		mock.ExpectQuery(getTableCommentQuery).WithArgs(tableName).WillReturnRows(rows)

		sqlStmt, err := handler.GenerateDeleteTableCommentSQL(ctx, db, tableName)
		if err != nil {
			t.Fatalf("GenerateDeleteTableCommentSQL() unexpected error: %v", err)
		}

		expectedFinalComment := "Keep this And This"
		expectedSQL := fmt.Sprintf(`COMMENT ON TABLE "orders" IS %s;`, pq.QuoteLiteral(expectedFinalComment))

		if sqlStmt != expectedSQL {
			t.Errorf("GenerateDeleteTableCommentSQL() mismatch:\ngot:  %s\nwant: %s", sqlStmt, expectedSQL)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("Table comment exists but no tag", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		defer db.Close()

		existingComment := "Just a normal table comment"
		rows := sqlmock.NewRows([]string{"obj_description"}).AddRow(existingComment)
		mock.ExpectQuery(getTableCommentQuery).WithArgs(tableName).WillReturnRows(rows)

		sqlStmt, err := handler.GenerateDeleteTableCommentSQL(ctx, db, tableName)
		if err != nil {
			t.Fatalf("GenerateDeleteTableCommentSQL() unexpected error: %v", err)
		}
		// Expect empty SQL as no change occurs
		if sqlStmt != "" {
			t.Errorf("GenerateDeleteTableCommentSQL() expected empty SQL, got: %s", sqlStmt)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("No existing table comment", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		defer db.Close()

		mock.ExpectQuery(getTableCommentQuery).WithArgs(tableName).WillReturnError(sql.ErrNoRows)

		sqlStmt, err := handler.GenerateDeleteTableCommentSQL(ctx, db, tableName)
		if err != nil {
			t.Fatalf("GenerateDeleteTableCommentSQL() unexpected error: %v", err)
		}
		// Expect empty SQL as nothing to delete
		if sqlStmt != "" {
			t.Errorf("GenerateDeleteTableCommentSQL() expected empty SQL, got: %s", sqlStmt)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("Error getting existing table comment", func(t *testing.T) {
		db, mock, handler := newMockPostgresDB(t)
		defer db.Close()

		dbError := errors.New("connection failed")
		mock.ExpectQuery(getTableCommentQuery).WithArgs(tableName).WillReturnError(dbError)

		_, err := handler.GenerateDeleteTableCommentSQL(ctx, db, tableName)
		if err == nil {
			t.Fatal("GenerateDeleteTableCommentSQL() expected error, got nil")
		}
		if !errors.Is(err, dbError) {
			t.Errorf("GenerateDeleteTableCommentSQL() got error %v, want error containing %v", err, dbError)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("there were unfulfilled expectations: %s", err)
		}
	})

	t.Run("Invalid Input", func(t *testing.T) {
		db, _, handler := newMockPostgresDB(t)
		defer db.Close()
		_, err := handler.GenerateDeleteTableCommentSQL(ctx, db, "")
		if err == nil {
			t.Error("Expected error for empty table name, got nil")
		}
	})
}

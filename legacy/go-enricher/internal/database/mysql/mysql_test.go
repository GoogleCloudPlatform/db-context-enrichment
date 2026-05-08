package mysql

import (
	"errors"
	"testing"

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
	"github.com/DATA-DOG/go-sqlmock"
)

func TestMySQLGetForeignKeys(t *testing.T) {
	tests := []struct {
		name           string
		tableName      string
		columnName     string
		expectedFKs    []database.ForeignKeyReference
		expectedError  string
		mockSetup      func(sqlmock.Sqlmock)
	}{
		{
			name:       "Success with foreign keys found",
			tableName:  "orders",
			columnName: "customer_id",
			expectedFKs: []database.ForeignKeyReference{
				{
					ReferencedTable:  "customers",
					ReferencedColumn: "id",
					ConstraintName:   "fk_orders_customer_id",
				},
			},
			expectedError: "",
			mockSetup: func(mock sqlmock.Sqlmock) {
				rows := sqlmock.NewRows([]string{"referenced_table", "referenced_column", "constraint_name"}).
					AddRow("customers", "id", "fk_orders_customer_id")
				mock.ExpectQuery(`SELECT\s+REFERENCED_TABLE_NAME as referenced_table,\s+REFERENCED_COLUMN_NAME as referenced_column,\s+CONSTRAINT_NAME as constraint_name\s+FROM information_schema\.KEY_COLUMN_USAGE`).WithArgs("orders", "customer_id").WillReturnRows(rows)
			},
		},
		{
			name:          "No foreign keys found",
			tableName:     "standalone_table",
			columnName:    "id",
			expectedFKs:   []database.ForeignKeyReference{},
			expectedError: "",
			mockSetup: func(mock sqlmock.Sqlmock) {
				rows := sqlmock.NewRows([]string{"referenced_table", "referenced_column", "constraint_name"})
				mock.ExpectQuery(`SELECT\s+REFERENCED_TABLE_NAME as referenced_table,\s+REFERENCED_COLUMN_NAME as referenced_column,\s+CONSTRAINT_NAME as constraint_name\s+FROM information_schema\.KEY_COLUMN_USAGE`).WithArgs("standalone_table", "id").WillReturnRows(rows)
			},
		},
		{
			name:          "Database query error",
			tableName:     "test_table",
			columnName:    "test_column",
			expectedFKs:   nil,
			expectedError: "error querying foreign keys for test_table.test_column",
			mockSetup: func(mock sqlmock.Sqlmock) {
				mock.ExpectQuery(`SELECT\s+REFERENCED_TABLE_NAME as referenced_table,\s+REFERENCED_COLUMN_NAME as referenced_column,\s+CONSTRAINT_NAME as constraint_name\s+FROM information_schema\.KEY_COLUMN_USAGE`).WithArgs("test_table", "test_column").WillReturnError(errors.New("database connection failed"))
			},
		},
		{
			name:          "Row scanning error",
			tableName:     "test_table",
			columnName:    "test_column",
			expectedFKs:   nil,
			expectedError: "error scanning foreign key data for test_table.test_column",
			mockSetup: func(mock sqlmock.Sqlmock) {
				rows := sqlmock.NewRows([]string{"referenced_table", "referenced_column", "constraint_name"}).
					AddRow(nil, "id", "fk_test") // nil value will cause scan error
				mock.ExpectQuery(`SELECT\s+REFERENCED_TABLE_NAME as referenced_table,\s+REFERENCED_COLUMN_NAME as referenced_column,\s+CONSTRAINT_NAME as constraint_name\s+FROM information_schema\.KEY_COLUMN_USAGE`).WithArgs("test_table", "test_column").WillReturnRows(rows)
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create mock database
			mockDB, mock, err := sqlmock.New()
			if err != nil {
				t.Fatalf("Failed to create mock database: %v", err)
			}
			defer mockDB.Close()

			// Setup mock expectations
			tt.mockSetup(mock)

			// Create database wrapper
			db := &database.DB{Pool: mockDB}

			// Create handler and call GetForeignKeys
			handler := mysqlHandler{}
			result, err := handler.GetForeignKeys(db, tt.tableName, tt.columnName)

			// Check error expectations
			if tt.expectedError != "" {
				if err == nil {
					t.Errorf("Expected error containing '%s', but got nil", tt.expectedError)
				} else if err.Error() == "" || len(err.Error()) == 0 {
					t.Errorf("Expected error containing '%s', but got empty error", tt.expectedError)
				}
			} else {
				if err != nil {
					t.Errorf("Expected no error, but got: %v", err)
				}
			}

			// Check result expectations
			if tt.expectedError == "" {
				if len(result) != len(tt.expectedFKs) {
					t.Errorf("Expected %d foreign keys, got %d", len(tt.expectedFKs), len(result))
				} else {
					for i, expectedFK := range tt.expectedFKs {
						if result[i].ReferencedTable != expectedFK.ReferencedTable ||
							result[i].ReferencedColumn != expectedFK.ReferencedColumn ||
							result[i].ConstraintName != expectedFK.ConstraintName {
							t.Errorf("Foreign key %d mismatch. Expected: %+v, Got: %+v", i, expectedFK, result[i])
						}
					}
				}
			}

			// Ensure all expectations were met
			if err := mock.ExpectationsWereMet(); err != nil {
				t.Errorf("Unfulfilled mock expectations: %v", err)
			}
		})
	}
}
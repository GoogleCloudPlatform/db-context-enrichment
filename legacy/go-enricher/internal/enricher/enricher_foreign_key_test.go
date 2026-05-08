package enricher

import (
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
)

// MockDBAdapter for testing foreign key collection
type MockDBAdapter struct {
	mock.Mock
}

func (m *MockDBAdapter) GetForeignKeys(tableName, columnName string) ([]database.ForeignKeyReference, error) {
	args := m.Called(tableName, columnName)
	return args.Get(0).([]database.ForeignKeyReference), args.Error(1)
}

func (m *MockDBAdapter) GetColumns(tableName string) ([]database.ColumnInfo, error) {
	args := m.Called(tableName)
	return args.Get(0).([]database.ColumnInfo), args.Error(1)
}

func (m *MockDBAdapter) GetTables() ([]string, error) {
	args := m.Called()
	return args.Get(0).([]string), args.Error(1)
}

func (m *MockDBAdapter) GetColumnMetadata(tableName, columnName string) (map[string]interface{}, error) {
	args := m.Called(tableName, columnName)
	return args.Get(0).(map[string]interface{}), args.Error(1)
}

func (m *MockDBAdapter) GenerateCommentSQL(data *database.CommentData, enrichments map[string]bool) (string, error) {
	args := m.Called(data, enrichments)
	return args.Get(0).(string), args.Error(1)
}

func (m *MockDBAdapter) GenerateDeleteCommentSQL(tableName, columnName string) (string, error) {
	args := m.Called(tableName, columnName)
	return args.Get(0).(string), args.Error(1)
}

func TestCollectColumnDBMetadataWithForeignKeys(t *testing.T) {
	tests := []struct {
		name                string
		enrichments         map[string]bool
		expectedForeignKeys []database.ForeignKeyReference
		foreignKeyError     error
		expectForeignKeys   bool
	}{
		{
			name: "foreign_keys_enrichment_requested_with_results",
			enrichments: map[string]bool{
				"foreign_keys": true,
			},
			expectedForeignKeys: []database.ForeignKeyReference{
				{
					ReferencedTable:  "users",
					ReferencedColumn: "id",
					ConstraintName:   "fk_orders_user_id",
				},
			},
			foreignKeyError:   nil,
			expectForeignKeys: true,
		},
		{
			name: "foreign_keys_enrichment_not_requested",
			enrichments: map[string]bool{
				"examples": true,
			},
			expectedForeignKeys: nil,
			foreignKeyError:     nil,
			expectForeignKeys:   false,
		},
		{
			name: "foreign_keys_enrichment_with_empty_results",
			enrichments: map[string]bool{
				"foreign_keys": true,
			},
			expectedForeignKeys: []database.ForeignKeyReference{},
			foreignKeyError:     nil,
			expectForeignKeys:   true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Setup mock
			mockAdapter := &MockDBAdapter{}
			service := &Service{
				dbAdapter: mockAdapter,
			}

			// Setup expectations
			if tt.expectForeignKeys {
				mockAdapter.On("GetForeignKeys", "orders", "user_id").Return(tt.expectedForeignKeys, tt.foreignKeyError)
			}

			// Mock GetColumnMetadata for other enrichments
			mockAdapter.On("GetColumnMetadata", "orders", "user_id").Return(map[string]interface{}{}, nil)

			// Test data
			colInfo := database.ColumnInfo{
				Name:     "user_id",
				DataType: "INTEGER",
			}

			// Execute
			result, err := service.collectColumnDBMetadata(context.Background(), "orders", colInfo, tt.enrichments)

			// Verify
			assert.NoError(t, err)
			assert.NotNil(t, result)
			assert.Equal(t, "orders", result.Table)
			assert.Equal(t, "user_id", result.Column)
			assert.Equal(t, "INTEGER", result.DataType)

			if tt.expectForeignKeys {
				assert.Equal(t, tt.expectedForeignKeys, result.ForeignKeys)
			} else {
				assert.Nil(t, result.ForeignKeys)
			}

			// Verify mock expectations
			mockAdapter.AssertExpectations(t)
		})
	}
}

func TestForeignKeyIntegrationWithCommentData(t *testing.T) {
	// Setup mock
	mockAdapter := &MockDBAdapter{}
	service := &Service{
		dbAdapter: mockAdapter,
	}

	// Expected foreign keys
	expectedForeignKeys := []database.ForeignKeyReference{
		{
			ReferencedTable:  "users",
			ReferencedColumn: "id",
			ConstraintName:   "fk_orders_user_id",
		},
	}

	// Setup expectations
	mockAdapter.On("GetForeignKeys", "orders", "user_id").Return(expectedForeignKeys, nil)
	mockAdapter.On("GetColumnMetadata", "orders", "user_id").Return(map[string]interface{}{}, nil)

	// Test data
	colInfo := database.ColumnInfo{
		Name:     "user_id",
		DataType: "INTEGER",
	}
	enrichments := map[string]bool{
		"foreign_keys": true,
	}

	// Execute
	result, err := service.collectColumnDBMetadata(context.Background(), "orders", colInfo, enrichments)

	// Verify
	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, expectedForeignKeys, result.ForeignKeys)

	// Verify that CommentData would be created correctly
	commentData := &database.CommentData{
		TableName:      result.Table,
		ColumnName:     result.Column,
		ColumnDataType: result.DataType,
		ExampleValues:  result.ExampleValues,
		DistinctCount:  result.DistinctCount,
		NullCount:      result.NullCount,
		Description:    result.Description,
		ForeignKeys:    result.ForeignKeys,
	}

	assert.Equal(t, "orders", commentData.TableName)
	assert.Equal(t, "user_id", commentData.ColumnName)
	assert.Equal(t, expectedForeignKeys, commentData.ForeignKeys)

	// Verify mock expectations
	mockAdapter.AssertExpectations(t)
}
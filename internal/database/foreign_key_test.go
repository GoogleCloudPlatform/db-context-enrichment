package database

import (
	"testing"
)

// TestForeignKeyReference verifies the ForeignKeyReference struct is properly defined
func TestForeignKeyReference(t *testing.T) {
	fk := ForeignKeyReference{
		ReferencedTable:  "users",
		ReferencedColumn: "id",
		ConstraintName:   "fk_user_id",
	}

	if fk.ReferencedTable != "users" {
		t.Errorf("Expected ReferencedTable to be 'users', got %s", fk.ReferencedTable)
	}
	if fk.ReferencedColumn != "id" {
		t.Errorf("Expected ReferencedColumn to be 'id', got %s", fk.ReferencedColumn)
	}
	if fk.ConstraintName != "fk_user_id" {
		t.Errorf("Expected ConstraintName to be 'fk_user_id', got %s", fk.ConstraintName)
	}
}

// TestCommentDataWithForeignKeys verifies the CommentData struct includes ForeignKeys field
func TestCommentDataWithForeignKeys(t *testing.T) {
	foreignKeys := []ForeignKeyReference{
		{
			ReferencedTable:  "users",
			ReferencedColumn: "id",
			ConstraintName:   "fk_user_id",
		},
	}

	commentData := CommentData{
		TableName:      "orders",
		ColumnName:     "user_id",
		ColumnDataType: "int",
		ExampleValues:  []string{"1", "2", "3"},
		DistinctCount:  100,
		NullCount:      0,
		Description:    "Foreign key to users table",
		ForeignKeys:    foreignKeys,
	}

	if len(commentData.ForeignKeys) != 1 {
		t.Errorf("Expected 1 foreign key, got %d", len(commentData.ForeignKeys))
	}

	if commentData.ForeignKeys[0].ReferencedTable != "users" {
		t.Errorf("Expected foreign key to reference 'users' table, got %s", commentData.ForeignKeys[0].ReferencedTable)
	}
}

// TestDBAdapterInterface verifies that DB struct implements DBAdapter interface with new method
func TestDBAdapterInterface(t *testing.T) {
	// This test ensures that DB struct satisfies the DBAdapter interface
	// If the interface is not properly implemented, this will fail at compile time
	var _ DBAdapter = (*DB)(nil)

	// Test passes if compilation succeeds
	t.Log("DB struct successfully implements DBAdapter interface with GetForeignKeys method")
}
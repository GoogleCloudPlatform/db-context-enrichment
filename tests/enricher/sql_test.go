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
package enricher

import (
	"context"
	"fmt"
	"testing"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestFormatExampleValues(t *testing.T) {
	tests := []struct {
		name   string
		values []string
		want   string
	}{
		{
			name:   "empty values",
			values: []string{},
			want:   "[]",
		},
		{
			name:   "single value",
			values: []string{"test"},
			want:   "[test]",
		},
		{
			name:   "multiple values",
			values: []string{"test1", "test2", "test3"},
			want:   "[test1 test2 test3]",
		},
		{
			name:   "values with special chars",
			values: []string{"test's", "test\"", "test;"},
			want:   "[test''s test\" test;]",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := formatExampleValues(tt.values)
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestGenerateCommentSQL(t *testing.T) {
	tests := []struct {
		name     string
		metadata *ColumnMetadata
		want     string
		wantErr  bool
	}{
		{
			name:     "nil metadata",
			metadata: nil,
			wantErr:  true,
		},
		{
			name: "basic metadata without foreign keys",
			metadata: &ColumnMetadata{
				Table:         "users",
				Column:        "email",
				ExampleValues: []string{"test@example.com", "user@domain.com"},
				DistinctCount: 100,
				NullCount:     5,
			},
			want: `COMMENT ON COLUMN "users"."email" IS 'example_values: [test@example.com user@domain.com], distinct_count: 100, null_count: 5';`,
		},
		{
			name: "metadata with foreign keys",
			metadata: &ColumnMetadata{
				Table:         "orders",
				Column:        "user_id",
				ExampleValues: []string{"1", "2", "3"},
				DistinctCount: 50,
				NullCount:     0,
				ForeignKeys: []ForeignKeyInfo{
					{RefTable: "users", RefColumn: "id", MatchRatio: 98.5},
				},
			},
			want: `COMMENT ON COLUMN "orders"."user_id" IS 'example_values: [1 2 3], distinct_count: 50, null_count: 0, foreign_keys: [users.id (98.50%)]';`,
		},
		{
			name: "metadata with special characters",
			metadata: &ColumnMetadata{
				Table:         "test'table",
				Column:        "test;column",
				ExampleValues: []string{"value's", "value;"},
				DistinctCount: 10,
				NullCount:     1,
			},
			want: `COMMENT ON COLUMN "test'table"."test;column" IS 'example_values: [value''s value;], distinct_count: 10, null_count: 1';`,
		},
	}

	mc := &MetadataCollector{}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := mc.GenerateCommentSQL(tt.metadata)
			if tt.wantErr {
				assert.Error(t, err)
				return
			}
			require.NoError(t, err)
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestApplyComments(t *testing.T) {
	db, mock, err := sqlmock.New()
	require.NoError(t, err)
	defer db.Close()

	ctx := context.Background()
	mc := &MetadataCollector{
		db: db,
		Metadata: []*ColumnMetadata{
			{
				Table:         "users",
				Column:        "email",
				ExampleValues: []string{"test@example.com"},
				DistinctCount: 100,
				NullCount:     5,
			},
			{
				Table:         "orders",
				Column:        "user_id",
				ExampleValues: []string{"1", "2"},
				DistinctCount: 50,
				NullCount:     0,
				ForeignKeys: []ForeignKeyInfo{
					{RefTable: "users", RefColumn: "id", MatchRatio: 98.5},
				},
			},
		},
	}

	tests := []struct {
		name    string
		dryRun  bool
		setup   func()
		wantErr bool
	}{
		{
			name:   "dry run only prints SQL",
			dryRun: true,
			setup:  func() {},
		},
		{
			name:   "successful comments application",
			dryRun: false,
			setup: func() {
				mock.ExpectBegin()
				mock.ExpectExec(`COMMENT ON COLUMN "users"."email"`).WillReturnResult(sqlmock.NewResult(0, 1))
				mock.ExpectExec(`COMMENT ON COLUMN "orders"."user_id"`).WillReturnResult(sqlmock.NewResult(0, 1))
				mock.ExpectCommit()
			},
		},
		{
			name:   "transaction begin error",
			dryRun: false,
			setup: func() {
				mock.ExpectBegin().WillReturnError(fmt.Errorf("begin error"))
			},
			wantErr: true,
		},
		{
			name:   "comment execution error",
			dryRun: false,
			setup: func() {
				mock.ExpectBegin()
				mock.ExpectExec(`COMMENT ON COLUMN "users"."email"`).WillReturnError(fmt.Errorf("exec error"))
				mock.ExpectRollback()
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tt.setup()
			err := mc.ApplyComments(ctx, tt.dryRun)
			if tt.wantErr {
				assert.Error(t, err)
				return
			}
			require.NoError(t, err)
		})
	}

	assert.NoError(t, mock.ExpectationsWereMet())
}

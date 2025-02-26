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
package enricher_test

import (
	"context"
	"database/sql"
	"fmt"
	"testing"
	"time"

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/enricher"
	_ "github.com/lib/pq"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

const (
	testDBHost     = "localhost"
	testDBPort     = 5432
	testDBUser     = "test_user"
	testDBPassword = "test_password"
	testDBName     = "test_db"
)

func setupTestDB(t *testing.T) (*sql.DB, func()) {
	dsn := fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=disable",
		testDBHost, testDBPort, testDBUser, testDBPassword, testDBName)

	db, err := sql.Open("postgres", dsn)
	require.NoError(t, err)

	// Create test tables
	_, err = db.Exec(`
		CREATE TABLE test_users (
			id SERIAL PRIMARY KEY,
			name VARCHAR(100),
			email VARCHAR(255) UNIQUE
		);

		CREATE TABLE test_orders (
			id SERIAL PRIMARY KEY,
			user_id INTEGER REFERENCES test_users(id),
			amount DECIMAL(10,2),
			status VARCHAR(50)
		);
	`)
	require.NoError(t, err)

	cleanup := func() {
		_, err := db.Exec(`
			DROP TABLE IF EXISTS test_orders;
			DROP TABLE IF EXISTS test_users;
		`)
		require.NoError(t, err)
		db.Close()
	}

	return db, cleanup
}

func TestDatabaseConnectionFailure(t *testing.T) {
	// Test with invalid credentials
	db, err := sql.Open("postgres", "host=localhost port=5432 user=invalid dbname=invalid")
	require.NoError(t, err)

	enricher := enricher.New(&database.DB{DB: db})
	ctx := context.Background()

	_, err = enricher.CollectColumnMetadata(ctx, "test_table", "test_column")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "connection")
}

func TestQueryTimeout(t *testing.T) {
	db, cleanup := setupTestDB(t)
	defer cleanup()

	enricher := enricher.New(&database.DB{DB: db})

	// Insert large dataset to cause timeout
	_, err := db.Exec(`
		INSERT INTO test_users (name, email)
		SELECT
			'User' || generate_series,
			'user' || generate_series || '@test.com'
		FROM generate_series(1, 100000);
	`)
	require.NoError(t, err)

	// Test with very short timeout
	ctx, cancel := context.WithTimeout(context.Background(), 1*time.Millisecond)
	defer cancel()

	_, err = enricher.CollectColumnMetadata(ctx, "test_users", "email")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "context deadline exceeded")
}

func TestLargeDatasetHandling(t *testing.T) {
	db, cleanup := setupTestDB(t)
	defer cleanup()

	enricher := enricher.New(&database.DB{DB: db})

	// Insert large dataset
	_, err := db.Exec(`
		INSERT INTO test_users (name, email)
		SELECT
			'User' || generate_series,
			'user' || generate_series || '@test.com'
		FROM generate_series(1, 100000);
	`)
	require.NoError(t, err)

	ctx := context.Background()
	metadata, err := enricher.CollectColumnMetadata(ctx, "test_users", "email")
	require.NoError(t, err)
	assert.NotNil(t, metadata)
	assert.Equal(t, int64(100000), metadata.DistinctCount)
	assert.Equal(t, int64(0), metadata.NullCount)
	assert.NotEmpty(t, metadata.ExampleValues)
}

func TestForeignKeyDetectionAccuracy(t *testing.T) {
	db, cleanup := setupTestDB(t)
	defer cleanup()

	enricher := enricher.New(&database.DB{DB: db})

	// Insert test data
	_, err := db.Exec(`
		INSERT INTO test_users (name, email) VALUES
		('User1', 'user1@test.com'),
		('User2', 'user2@test.com');

		INSERT INTO test_orders (user_id, amount, status) VALUES
		(1, 100.00, 'completed'),
		(2, 200.00, 'pending'),
		(1, 150.00, 'completed');
	`)
	require.NoError(t, err)

	ctx := context.Background()
	metadata, err := enricher.CollectColumnMetadata(ctx, "test_orders", "user_id")
	require.NoError(t, err)
	assert.NotNil(t, metadata)

	// Verify foreign key detection
	assert.Len(t, metadata.ForeignKeys, 1)
	assert.Equal(t, "test_users", metadata.ForeignKeys[0].RefTable)
	assert.Equal(t, "id", metadata.ForeignKeys[0].RefColumn)
	assert.Equal(t, 100.0, metadata.ForeignKeys[0].MatchRatio)
}

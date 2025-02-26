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
package database_test

import (
	"context"
	"testing"

	"github.com/GoogleCloudPlatform/db-context-enrichment/pkg/database"
	"github.com/stretchr/testify/require"
)

func setupTestDB(t *testing.T) *database.Connection {
	config := &database.Config{
		Host:     "localhost",
		Port:     5432,
		User:     "test_user",
		Password: "test_password",
		DBName:   "test_db",
		SSLMode:  "disable",
	}

	conn, err := database.New(config)
	require.NoError(t, err)
	require.NotNil(t, conn)

	ctx := context.Background()

	// Create test tables
	_, err = conn.ExecContext(ctx, `
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS customers;

        CREATE TABLE customers (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE orders (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            order_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            total_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00
        );
    `)
	require.NoError(t, err)

	return conn
}

func TestConnection_ListTables(t *testing.T) {
	conn := setupTestDB(t)
	defer conn.Close()

	ctx := context.Background()
	tables, err := conn.ListTables(ctx)
	require.NoError(t, err)
	require.Contains(t, tables, "customers")
	require.Contains(t, tables, "orders")
}

func TestConnection_GetTableInfo(t *testing.T) {
	conn := setupTestDB(t)
	defer conn.Close()

	ctx := context.Background()
	info, err := conn.GetTableInfo(ctx, "customers")
	require.NoError(t, err)
	require.Equal(t, "customers", info.Name)

	// Verify columns
	var foundColumns = make(map[string]bool)
	for _, col := range info.Columns {
		foundColumns[col.Name] = true
		switch col.Name {
		case "id":
			require.True(t, col.IsPrimaryKey)
			require.Equal(t, "integer", col.DataType)
		case "name":
			require.False(t, col.IsNullable)
			require.Equal(t, "character varying", col.DataType)
			require.Equal(t, 100, *col.CharMaxLength)
		case "email":
			require.False(t, col.IsNullable)
			require.Equal(t, "character varying", col.DataType)
			require.Equal(t, 255, *col.CharMaxLength)
		}
	}

	require.True(t, foundColumns["id"])
	require.True(t, foundColumns["name"])
	require.True(t, foundColumns["email"])
}

func TestConnection_GetTableInfo_NonExistentTable(t *testing.T) {
	conn := setupTestDB(t)
	defer conn.Close()

	ctx := context.Background()
	info, err := conn.GetTableInfo(ctx, "nonexistent_table")
	require.Error(t, err)
	require.Nil(t, info)
	require.Contains(t, err.Error(), "does not exist")
}

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
	"time"

	"github.com/GoogleCloudPlatform/db-context-enrichment/pkg/database"
	"github.com/stretchr/testify/require"
)

func TestConfig_Validate(t *testing.T) {
	tests := []struct {
		name    string
		config  *database.Config
		wantErr bool
	}{
		{
			name: "valid_config",
			config: &database.Config{
				Host:     "localhost",
				Port:     5432,
				User:     "test_user",
				Password: "test_password",
				DBName:   "test_db",
				SSLMode:  "disable",
			},
			wantErr: false,
		},
		{
			name: "empty_host",
			config: &database.Config{
				Port:     5432,
				User:     "test_user",
				Password: "test_password",
				DBName:   "test_db",
			},
			wantErr: true,
		},
		{
			name: "invalid_port",
			config: &database.Config{
				Host:     "localhost",
				Port:     70000,
				User:     "test_user",
				Password: "test_password",
				DBName:   "test_db",
			},
			wantErr: true,
		},
		{
			name: "empty_user",
			config: &database.Config{
				Host:     "localhost",
				Port:     5432,
				Password: "test_password",
				DBName:   "test_db",
			},
			wantErr: true,
		},
		{
			name: "empty_database_name",
			config: &database.Config{
				Host:     "localhost",
				Port:     5432,
				User:     "test_user",
				Password: "test_password",
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.config.Validate()
			if tt.wantErr {
				require.Error(t, err)
			} else {
				require.NoError(t, err)
			}
		})
	}
}

func TestConnection_New(t *testing.T) {
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
	defer conn.Close()

	// Test connection with context
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err = conn.TestConnection(ctx)
	require.NoError(t, err)
}

func TestConnection_New_InvalidConfig(t *testing.T) {
	config := &database.Config{
		Host:     "",
		Port:     5432,
		User:     "test_user",
		Password: "test_password",
		DBName:   "test_db",
	}

	conn, err := database.New(config)
	require.Error(t, err)
	require.Nil(t, conn)
}

func TestConnection_TestConnection_Timeout(t *testing.T) {
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
	defer conn.Close()

	// Test with a very short timeout
	ctx, cancel := context.WithTimeout(context.Background(), 1*time.Nanosecond)
	defer cancel()

	err = conn.TestConnection(ctx)
	require.Error(t, err)
}

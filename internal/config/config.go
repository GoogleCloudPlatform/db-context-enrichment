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
package config

// Config holds all configuration for the application
type Config struct {
	Database     DatabaseConfig
	GeminiAPIKey string
}

// DatabaseConfig holds database connection configuration
type DatabaseConfig struct {
	Dialect                        string
	Host                           string
	Port                           int
	User                           string
	Password                       string
	DBName                         string
	SSLMode                        string
	CloudSQLInstanceConnectionName string
	UsePrivateIP                   bool
	UpdateExistingMode             string
}

var globalConfig *Config

// GetConfig returns a default configuration. Configuration will be set by flags in root.go
func GetConfig() *Config {
	return &Config{
		Database: DatabaseConfig{
			Dialect:            "postgres",
			Host:               "localhost",
			Port:               5432,
			SSLMode:            "disable",
			UpdateExistingMode: "overwrite",
		},
		GeminiAPIKey: "", // Gemini API key can be set via flag or env var
	}
}

// SetConfig sets the global configuration.
func SetConfig(cfg *Config) {
	globalConfig = cfg
}

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

import (
	"fmt"

	"github.com/spf13/viper"
)

// Config holds all configuration for the application
type Config struct {
	Database DatabaseConfig `mapstructure:"database"`
}

// DatabaseConfig holds database connection configuration
type DatabaseConfig struct {
	Dialect                        string `mapstructure:"dialect"`
	Host                           string `mapstructure:"host"`
	Port                           int    `mapstructure:"port"`
	User                           string `mapstructure:"user"`
	Password                       string `mapstructure:"password"`
	DBName                         string `mapstructure:"dbname"`
	SSLMode                        string `mapstructure:"sslmode"`
	CloudSQLInstanceConnectionName string `mapstructure:"cloudsql_instance_connection_name"`
	UsePrivateIP                   bool   `mapstructure:"cloudsql_use_private_ip"`
	UpdateExistingMode             string `mapstructure:"update_existing"`
}

var globalConfig *Config

// LoadConfig reads configuration from viper
func LoadConfig() (*Config, error) {
	viper.SetConfigName(".db_schema_enricher")
	viper.SetConfigType("yaml")
	viper.AddConfigPath("$HOME")
	viper.AutomaticEnv()

	setDefaults()

	if err := viper.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			return nil, fmt.Errorf("failed to read config file: %w", err)
		}
		// Config file not found is okay, continue with defaults/env vars
	}

	var config Config
	if err := viper.Unmarshal(&config); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}
	globalConfig = &config
	return &config, nil
}

// GetConfig returns the loaded configuration.
func GetConfig() *Config {
	if globalConfig == nil {
		// Fallback to default config if not loaded
		return &Config{
			Database: DatabaseConfig{
				Dialect:            "postgres", // Default dialect
				Host:               "localhost",
				Port:               5432,
				SSLMode:            "disable",
				UpdateExistingMode: "overwrite", //Default update mode
			},
		}
	}
	return globalConfig
}

// SetConfig sets the global configuration.
func SetConfig(cfg *Config) {
	globalConfig = cfg
}

// setDefaults sets default values for configuration
func setDefaults() {
	viper.SetDefault("database.dialect", "postgres")
	viper.SetDefault("database.host", "localhost")
	viper.SetDefault("database.port", 0) // Let each dialect handler decide default port if 0
	viper.SetDefault("database.sslmode", "disable")
	viper.SetDefault("database.cloudsql_instance_connection_name", "")
	viper.SetDefault("database.cloudsql_use_private_ip", false)
	viper.SetDefault("database.update_existing", "overwrite") // Default update mode
}

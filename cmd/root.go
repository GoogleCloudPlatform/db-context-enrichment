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
package cmd

import (
	"fmt"
	"log"
	"os"
	"strings"

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/config"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
	_ "github.com/GoogleCloudPlatform/db-context-enrichment/internal/database/mysql"
	_ "github.com/GoogleCloudPlatform/db-context-enrichment/internal/database/postgres"
	_ "github.com/GoogleCloudPlatform/db-context-enrichment/internal/database/sqlserver"
	"github.com/spf13/cobra"
)

var (
	dryRun             bool
	updateExistingMode string
	geminiAPIKey       string

	// Database connection flags
	dialect                        string
	host                           string
	port                           int
	username                       string
	password                       string
	dbName                         string
	cloudSQLInstanceConnectionName string
	cloudSQLUsePrivateIP           bool
)

var rootCmd = &cobra.Command{
	Use:   "db_schema_enricher",
	Short: "A tool to enrich database schema with metadata",
	Long: `db_schema_enricher is a CLI tool that helps enrich database schemas
with metadata like column descriptions, example values, and foreign key relationships.`,
	PersistentPreRunE: initFlagsAndConfig,
}

// initFlagsAndConfig initializes database configuration using command flags.
func initFlagsAndConfig(cmd *cobra.Command, args []string) error {
	cfg := config.GetConfig()
	dbCfg := cfg.Database

	if cmd != nil {
		dbCfg.Dialect = dialect
		dbCfg.Host = host
		dbCfg.Port = port
		dbCfg.User = username
		dbCfg.Password = password
		dbCfg.DBName = dbName
		dbCfg.CloudSQLInstanceConnectionName = cloudSQLInstanceConnectionName
		dbCfg.UsePrivateIP = cloudSQLUsePrivateIP
		dbCfg.UpdateExistingMode = strings.ToLower(updateExistingMode)
	}

	database.SetConfig(&dbCfg)
	config.SetConfig(cfg)

	if geminiAPIKey == "" {
		geminiAPIKey = os.Getenv("GEMINI_API_KEY")
	}
	cfg.GeminiAPIKey = geminiAPIKey
	config.SetConfig(cfg)

	return nil
}

func validateDialect(dialect string) error {
	supportedDialects := []string{"postgres", "cloudsqlpostgres", "mysql", "cloudsqlmysql", "sqlserver", "cloudsqlsqlserver"}
	isValidDialect := false
	for _, supportedDialect := range supportedDialects {
		if dialect == supportedDialect {
			isValidDialect = true
			break
		}
	}
	if !isValidDialect {
		return fmt.Errorf("unsupported dialect: %s (only %s are supported)", dialect, strings.Join(supportedDialects, ", "))
	}
	return nil
}

func setupDatabase() (*database.DB, error) {
	dbConfig := database.GetConfig()
	if dbConfig == nil {
		return nil, fmt.Errorf("database config is not initialized")
	}
	db, err := database.New(*dbConfig)
	if err != nil {
		log.Println("ERROR: Failed to connect to database:", err)
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}
	return db, nil
}

// Execute adds all child commands to the root command and sets flags appropriately.
func Execute() error {
	return rootCmd.Execute()
}

func init() {
	// Global persistent flags
	rootCmd.PersistentFlags().BoolVar(&dryRun, "dry-run", true, "Enable dry-run mode (no database modifications)")

	// Database connection flags
	rootCmd.PersistentFlags().StringVar(&dialect, "dialect", "", fmt.Sprintf("Database dialect (%s) - MANDATORY", strings.Join([]string{"postgres", "mysql", "sqlserver", "cloudsqlpostgres", "cloudsqlmysql", "cloudsqlsqlserver"}, ", ")))
	rootCmd.PersistentFlags().StringVar(&host, "host", "", "Database host - MANDATORY")
	rootCmd.PersistentFlags().IntVar(&port, "port", 0, "Database port - MANDATORY")
	rootCmd.PersistentFlags().StringVar(&username, "username", "", "Database username - MANDATORY")
	rootCmd.PersistentFlags().StringVar(&password, "password", "", "Database password - MANDATORY")
	rootCmd.PersistentFlags().StringVar(&dbName, "database", "", "Database name - MANDATORY")
	rootCmd.PersistentFlags().StringVar(&cloudSQLInstanceConnectionName, "cloudsql-instance-connection-name", "", "Cloud SQL instance connection name (for Cloud SQL dialects) - MANDATORY for CloudSQL")
	rootCmd.PersistentFlags().BoolVar(&cloudSQLUsePrivateIP, "cloudsql-use-private-ip", false, "Use private IP for Cloud SQL connection (Cloud SQL)")
	rootCmd.PersistentFlags().StringVar(&updateExistingMode, "update_existing", "overwrite", "Mode to update existing comments ('overwrite' or 'append')")

	// Gemini API Key flag
	rootCmd.PersistentFlags().StringVar(&geminiAPIKey, "gemini-api-key", "", "Gemini API key (can also be set via GEMINI_API_KEY environment variable)")

	// Add subcommands
	rootCmd.AddCommand(addCommentsCmd)
	rootCmd.AddCommand(getCommentsCmd)
	rootCmd.AddCommand(deleteCommentsCmd)
	rootCmd.AddCommand(applyCommentsCmd)
}

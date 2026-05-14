package cmd

import (
	"fmt"
	"log"
	"strings"

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/config"
	_ "github.com/GoogleCloudPlatform/db-context-enrichment/internal/database/mysql"
	_ "github.com/GoogleCloudPlatform/db-context-enrichment/internal/database/postgres"
	_ "github.com/GoogleCloudPlatform/db-context-enrichment/internal/database/sqlserver"

	"github.com/spf13/cobra"
)

// appCfg holds the application configuration, populated by flags and env vars.
// This instance is configured in init() and validated in PersistentPreRunE.
var appCfg = config.NewAppConfig()

var rootCmd = &cobra.Command{
	Use:   "db_schema_enricher",
	Short: "A tool to enrich database schema with metadata",
	Long: `db_schema_enricher is a CLI tool that helps enrich database schemas
with metadata like column descriptions, example values, distinct values, null counts, and foreign key relationships.`,
	PersistentPreRunE: func(cmd *cobra.Command, args []string) error {
		err := appCfg.LoadAndValidate()
		if err != nil {
			log.Printf("ERROR: Configuration validation failed: %v", err)
		}
		return err
	},
}

func Execute() error {
	log.SetFlags(log.LstdFlags | log.Lshortfile)
	return rootCmd.Execute()
}

func init() {
	// Global persistent flags
	rootCmd.PersistentFlags().BoolVar(&appCfg.DryRun, "dry-run", appCfg.DryRun, "Preview changes without modifying the database.")

	// Database connection flags
	rootCmd.PersistentFlags().StringVar(&appCfg.Database.Dialect, "dialect", "", fmt.Sprintf("Database dialect (%s) - MANDATORY", strings.Join([]string{"postgres", "mysql", "sqlserver", "cloudsqlpostgres", "cloudsqlmysql", "cloudsqlsqlserver"}, ", ")))
	rootCmd.PersistentFlags().StringVar(&appCfg.Database.Host, "host", "", "Database host (for non-Cloud SQL connections).")
	rootCmd.PersistentFlags().IntVar(&appCfg.Database.Port, "port", 0, "Database port (for non-Cloud SQL connections).")
	rootCmd.PersistentFlags().StringVar(&appCfg.Database.User, "username", "", "Database username.")
	rootCmd.PersistentFlags().StringVar(&appCfg.Database.Password, "password", "", "Database password.")
	rootCmd.PersistentFlags().StringVar(&appCfg.Database.DBName, "database", "", "Database name.")
	rootCmd.PersistentFlags().StringVar(&appCfg.Database.CloudSQLInstanceConnectionName, "cloudsql-instance-connection-name", "", "Cloud SQL instance connection name (required for Cloud SQL).")
	rootCmd.PersistentFlags().BoolVar(&appCfg.Database.UsePrivateIP, "cloudsql-use-private-ip", appCfg.Database.UsePrivateIP, "Use the private IP address for the Cloud SQL connection.")
	rootCmd.PersistentFlags().StringVar(&appCfg.Database.UpdateExistingMode, "update_existing", appCfg.Database.UpdateExistingMode, "How to handle existing comments: 'overwrite' or 'append'.")

	// Gemini API Key flag
	rootCmd.PersistentFlags().StringVar(&appCfg.GeminiAPIKey, "gemini-api-key", "", "Gemini API key. Required for generating descriptions using additional context. Can also be set via the GEMINI_API_KEY environment variable.")

	// Add subcommands
	rootCmd.AddCommand(addCommentsCmd)
	rootCmd.AddCommand(getCommentsCmd)
	rootCmd.AddCommand(deleteCommentsCmd)
	rootCmd.AddCommand(applyCommentsCmd)
}

// GetAppConfig returns the application configuration.
func getAppConfig() *config.AppConfig {
	return appCfg
}

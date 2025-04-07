package cmd

import (
	"fmt"
	"log"
	"os"
	"strings"

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/enricher"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/utils"
	"github.com/spf13/cobra"
)

var deleteCommentsCmd = &cobra.Command{
	Use:   "delete-comments",
	Short: "Generate SQL to remove comments previously added by this tool",
	Long: `Generates SQL statements to remove comments containing the specific <gemini> tags added by the 'add-comments' command.
Outputs the SQL to a file. If --dry-run=false, prompts for application.`,
	Example: `./db_schema_enricher delete-comments --dialect cloudsqlsqlserver --username user --password pass --database sales_db --cloudsql-instance-connection-name proj:reg:inst --out_file ./delete_sales_comments.sql --tables "orders,customers[email]"`,
	RunE:    runDeleteComments,
}

func runDeleteComments(cmd *cobra.Command, args []string) error {
	cfg := getAppConfig()
	ctx := cmd.Context()

	outputFile := cfg.OutputFile
	if outputFile == "" {
		outputFile = cfg.GetDefaultOutputFile("delete-comments")
	}

	log.Println("INFO: Starting delete-comments operation", "dialect:", cfg.Database.Dialect, "database:", cfg.Database.DBName, "dry-run:", cfg.DryRun)

	dbAdapter, err := database.New(cfg.Database)
	if err != nil {
		return fmt.Errorf("failed to initialize database connection: %w", err)
	}
	defer dbAdapter.Close()
	log.Println("INFO: Database connection established successfully.")

	enricherCfg := enricher.Config{}
	svc := enricher.NewService(dbAdapter, nil, enricherCfg)

	tableFilters, err := utils.ParseTablesFlag(cfg.TablesRaw)
	if err != nil {
		return fmt.Errorf("error parsing --tables flag: %w", err)
	}

	deleteParams := enricher.GenerateDeleteSQLParams{
		TableFilters: tableFilters,
	}
	sqlStatements, err := svc.GenerateDeleteCommentSQLs(ctx, deleteParams)
	if err != nil {
		return fmt.Errorf("failed to generate SQL for comment deletion: %w", err)
	}

	if len(sqlStatements) == 0 {
		log.Println("INFO: No SQL statements generated for deletion. This might be due to filters or no tagged comments found matching the criteria.")
		return nil
	}

	fileContent := strings.Join(sqlStatements, "\n") + "\n"
	writeErr := os.WriteFile(outputFile, []byte(fileContent), 0644)
	if writeErr != nil {
		return fmt.Errorf("failed to write output file '%s': %w", outputFile, writeErr)
	}
	log.Println("INFO: SQL statements successfully written to:", outputFile)

	if cfg.DryRun {
		log.Println("INFO: Delete comments operation completed in dry-run mode. Review the generated SQL file:", outputFile)
		return nil
	}

	// Dry run is false
	if utils.ConfirmAction(fmt.Sprintf("apply %d generated SQL statements for comment DELETION from '%s'", len(sqlStatements), outputFile)) {
		log.Println("INFO: Applying SQL statements to the database...")

		if execErr := dbAdapter.ExecuteSQLStatements(ctx, sqlStatements); execErr != nil {
			return fmt.Errorf("failed to execute SQL statements for comment deletion from '%s': %w. Review the file and database logs", outputFile, execErr)
		}
		log.Printf("INFO: Successfully applied %d SQL statements for comment deletion.", len(sqlStatements))
	} else {
		log.Println("INFO: Comment deletion aborted by user. Generated SQL statements remain in:", outputFile)
	}

	log.Println("INFO: Delete comments operation completed.")
	return nil
}

func init() {
	deleteCommentsCmd.Flags().StringVarP(&appCfg.OutputFile, "out_file", "o", "", "Path to the output SQL file (defaults to <database_name>_comments.sql)")
	deleteCommentsCmd.Flags().StringVar(&appCfg.TablesRaw, "tables", "", "Comma-separated list of tables/columns to target for comment deletion (e.g., 'table1[col1],table2')")
}

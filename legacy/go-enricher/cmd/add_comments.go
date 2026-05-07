package cmd

import (
	"fmt"
	"log"
	"os"
	"strings"

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/enricher"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/genai"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/utils"
	"github.com/spf13/cobra"
)

var addCommentsCmd = &cobra.Command{
	Use:   "add-comments",
	Short: "Generate SQL for adding comments to database columns based on metadata",
	Long: `Connects to the database, collects metadata, potentially uses an LLM for descriptions/PII checks,
and generates SQL statements to add column comments. These SQL statements are outputted to a file for review.
If --dry-run=false, prompts for application.`,
		Example: `./db_schema_enricher add-comments --dialect cloudsqlpostgres --username user --password pass --database mydb --cloudsql-instance-connection-name my-project:my-region:my-instance --out_file ./mydb_comments.sql --tables "table1[col1,column3],table2,table4[columnx,columnz]" --enrichments "description,examples,distinct_values,foreign_keys" --context docs.txt --gemini-api-key YOUR_API_KEY`,
	RunE:    runAddComments,
}

func runAddComments(cmd *cobra.Command, args []string) error {
	cfg := getAppConfig()
	ctx := cmd.Context()

	outputFile := cfg.OutputFile
	if outputFile == "" {
		outputFile = cfg.GetDefaultOutputFile("add-comments")
	}

	log.Println("INFO: Starting add-comments operation", "dialect:", cfg.Database.Dialect, "database:", cfg.Database.DBName, "dry-run:", cfg.DryRun)

	// Setup Database Connection
	dbAdapter, err := database.New(cfg.Database)
	if err != nil {
		return fmt.Errorf("failed to initialize database connection: %w", err)
	}
	defer dbAdapter.Close()

	var llmClient genai.LLMClient
	var llmErr error
	if cfg.GeminiAPIKey != "" {
		llmConfig := genai.Config{
			APIKey: cfg.GeminiAPIKey,
			Model:  cfg.Model,
		}
		llmClient, llmErr = genai.NewClient(ctx, llmConfig)
		if llmErr != nil {
			return fmt.Errorf("failed to initialize Gemini client: %w", llmErr)
		}
		defer llmClient.Close()
		log.Println("INFO: LLM client initialized.")
	} else {
		log.Println("INFO: No Gemini API key provided. LLM-based enrichments (Description, PII check) will be skipped.")
	}

	// Setup Enricher Service
	enricherCfg := enricher.Config{MaskPII: appCfg.MaskPII}
	svc := enricher.NewService(dbAdapter, llmClient, enricherCfg)

	// Parse filters
	tableFilters, err := utils.ParseTablesFlag(cfg.TablesRaw)
	if err != nil {
		return fmt.Errorf("error parsing --tables flag: %w", err)
	}

	// Parse enrichments
	enrichmentSet := make(map[string]bool)
	if cfg.EnrichmentsRaw != "" {
		enrichmentsList := strings.Split(strings.ReplaceAll(cfg.EnrichmentsRaw, " ", ""), ",")
		for _, e := range enrichmentsList {
			enrichmentSet[strings.TrimSpace(strings.ToLower(e))] = true
		}
	}

	// Read context files
	additionalContext, err := utils.ReadContextFiles(cfg.ContextFilesRaw)
	if err != nil {
		return fmt.Errorf("failed to read context files specified via --context: %w", err)
	}
	if additionalContext != "" {
		log.Printf("INFO: Loaded additional context from: %s", cfg.ContextFilesRaw)
	}

	needsLLM := additionalContext != "" || enrichmentSet["description"]
	if needsLLM {
		if llmClient == nil {
			requiredBy := ""
			if additionalContext != "" || enrichmentSet["description"] {
				requiredBy = " for Description enrichment"
			}
			errorMsg := fmt.Sprintf("LLM features (%s) requested/implied, but Gemini API key is missing", strings.TrimSpace(requiredBy))
			log.Println("ERROR:", errorMsg)
			return fmt.Errorf("%s. Set --gemini-api-key flag or GEMINI_API_KEY environment variable", errorMsg)
		}
		if err := llmClient.IsAPIKeyValid(ctx); err != nil {
			return fmt.Errorf("Gemini API key validation failed: %w. Ensure the key is correct and has permissions", err)
		}
	}

	generationParams := enricher.GenerateSQLParams{
		TableFilters:      tableFilters,
		Enrichments:       enrichmentSet,
		AdditionalContext: additionalContext,
	}
	sqlStatements, err := svc.GenerateCommentSQLs(ctx, generationParams)
	if err != nil {
		return fmt.Errorf("SQL generation failed: %w", err)
	}

	if len(sqlStatements) == 0 {
		log.Println("INFO: No SQL statements generated. This might be due to filters or lack of enrichable content meeting criteria.")
		return nil
	}

	// Write SQL to File
	fileContent := strings.Join(sqlStatements, "\n") + "\n"
	writeErr := os.WriteFile(outputFile, []byte(fileContent), 0644)
	if writeErr != nil {
		return fmt.Errorf("failed to write output file '%s': %w", outputFile, writeErr)
	}
	log.Println("INFO: SQL statements successfully written to:", outputFile)

	if cfg.DryRun {
		log.Println("INFO: Add comments operation completed in dry-run mode. Review the generated SQL file:", outputFile)
		return nil
	}

	// Dry run is false
	if utils.ConfirmAction(fmt.Sprintf("apply %d generated SQL statements from '%s'", len(sqlStatements), outputFile)) {
		log.Println("INFO: Applying SQL statements to the database...")

		if execErr := dbAdapter.ExecuteSQLStatements(ctx, sqlStatements); execErr != nil {
			return fmt.Errorf("failed to execute SQL statements from '%s': %w. Review the file and database logs", outputFile, execErr)
		}
		log.Printf("INFO: Successfully applied %d SQL statements from %s.", len(sqlStatements), outputFile)
	} else {
		log.Println("INFO: Comment addition aborted by user. Generated SQL statements remain in:", outputFile)
	}

	log.Println("INFO: Add comments operation completed.")
	return nil
}

func init() {
	addCommentsCmd.Flags().StringVarP(&appCfg.OutputFile, "out_file", "o", "", "File path to output generated SQL statements (defaults to <database>_comments.sql)")
	addCommentsCmd.Flags().StringVar(&appCfg.TablesRaw, "tables", "", "Comma-separated list of tables/columns to include (e.g., 'table1[col1,col2],table2')")
	addCommentsCmd.Flags().StringVar(&appCfg.EnrichmentsRaw, "enrichments", "", "Comma-separated list of enrichments to include (e.g., 'description,examples,distinct_values,foreign_keys'). If empty, all are included.")
	addCommentsCmd.Flags().StringVar(&appCfg.ContextFilesRaw, "context", "", "Comma-separated list of context files for description generation.")
	addCommentsCmd.Flags().StringVar(&appCfg.Model, "model", appCfg.Model, "Model to use for description/PII enrichment.")
	addCommentsCmd.Flags().BoolVar(&appCfg.MaskPII, "mask_pii", appCfg.MaskPII, "Enable PII masking using LLM-based detection (default: true). When false, skips LLM PII handling.")
}

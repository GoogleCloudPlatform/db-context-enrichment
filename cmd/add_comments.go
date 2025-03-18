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

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/enricher"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/utils"
	"github.com/spf13/cobra"
)

// addCommentsCmd represents the addComments command
var addCommentsCmd = &cobra.Command{
	Use:               "add-comments",
	Short:             "Generate SQL for adding comments to database columns based on metadata",
	Long:              `Connects to the database, collects metadata, and generates SQL statements to add column comments. These SQL statements are outputted to a file for review before actual application.`,
	Example:           `./db_schema_enricher add-comments --dialect cloudsqlpostgres --username user --password pass --database mydb --cloudsql-instance-connection-name my-project:my-region:my-instance --out_file ./mydb_comments.sql --tables "table1[column1,column3],table2,table4[columnx,columnz]" --enrichments "examples,distinct_values,null_count,foreign_keys,primary_keys"`,
	PersistentPreRunE: initFlagsAndConfig,
	RunE:              runAddComments,
}

func runAddComments(cmd *cobra.Command, args []string) error {
	dbConfig := database.GetConfig()
	if dbConfig == nil {
		return fmt.Errorf("database config is not initialized")
	}

	if err := validateDialect(dialect); err != nil {
		return err
	}

	outputFile := cmd.Flag("out_file").Value.String()
	if outputFile == "" {
		outputFile = utils.GetDefaultOutputFilePath(dbConfig.DBName, "add-comments")
	}

	log.Println("INFO: Starting add-comments operation", "dialect:", dbConfig.Dialect, "database:", dbConfig.DBName)

	db, err := setupDatabase()
	if err != nil {
		return err
	}
	defer db.Close()

	model := cmd.Flag("model").Value.String()
	metadataCollector := enricher.NewMetadataCollector(db, &enricher.DefaultRetryOptions, dryRun, geminiAPIKey, "", model)

	ctx := cmd.Context()

	tablesFlag := cmd.Flag("tables").Value.String()
	tableFilters, err := utils.ParseTablesFlag(tablesFlag)
	if err != nil {
		return err
	}
	metadataCollector.TableFilters = tableFilters

	enrichmentsFlag := cmd.Flag("enrichments").Value.String()
	enrichmentSet := make(map[string]bool)
	if enrichmentsFlag != "" {
		enrichmentsFlag = strings.ReplaceAll(enrichmentsFlag, " ", "")
		for _, e := range strings.Split(enrichmentsFlag, ",") {
			enrichmentSet[strings.TrimSpace(strings.ToLower(e))] = true
		}
	}
	metadataCollector.Enrichments = enrichmentSet

	contextFilesFlag := cmd.Flag("context").Value.String()
	additionalContext, err := utils.ReadContextFiles(contextFilesFlag)
	if err != nil {
		return fmt.Errorf("failed to read context files: %w", err)
	}
	metadataCollector.AdditionalContext = additionalContext

	// API Key Validation Logic
	if additionalContext != "" {
		if geminiAPIKey == "" {
			return fmt.Errorf("additional context is provided, but Gemini API key is not configured. Please set the GEMINI_API_KEY environment variable")
		}
		if err := metadataCollector.IsGeminiAPIKeyValid(ctx); err != nil {
			return fmt.Errorf("\nGemini API key is invalid. Please provide a valid api key\n")
		}
	}

	if len(enrichmentSet) == 0 || enrichmentSet["examples"] {
		if geminiAPIKey == "" {
			log.Println("WARN: No Gemini API key provided. PII identification will be skipped.")
		}
		if err := metadataCollector.IsGeminiAPIKeyValid(ctx); err != nil {
			geminiAPIKey = ""
			log.Println("WARN: Gemini API key provided is invalid. PII identification will be skipped.\n")
		}
	}

	metadataCollector.GeminiAPIKey = geminiAPIKey

	sqlStatements, err := metadataCollector.GenerateCommentSQLs(ctx)
	if err != nil {
		return fmt.Errorf("metadata collection and SQL generation failed: %w", err)
	}

	file, createErr := os.Create(outputFile)
	if createErr != nil {
		return fmt.Errorf("failed to create output file: %w", createErr)
	}
	defer file.Close()

	for _, sqlStmt := range sqlStatements {
		if _, writeErr := file.WriteString(sqlStmt + "\n"); writeErr != nil {
			return fmt.Errorf("failed to write SQL statement to file: %w", writeErr)
		}
	}

	log.Println("INFO: SQL statements to add column comments have been written to:", outputFile)

	if dryRun {
		log.Println("INFO: Add comments operation completed in dry-run mode.  No changes were made to the database.")
		return nil
	}

	// --- User Confirmation ---
	if len(sqlStatements) > 0 {
		if utils.ConfirmAction("SQL statements to add column comments") {
			// Re-read the SQL statements from the output file as changes may have been
			fileContent, readErr := os.ReadFile(outputFile)
			if readErr != nil {
				return fmt.Errorf("failed to read SQL statements from output file: %w", readErr)
			}
			sqlStatements = strings.Split(strings.TrimSpace(string(fileContent)), "\n")

			if execErr := db.ExecuteSQLStatements(ctx, sqlStatements); execErr != nil {
				return fmt.Errorf("failed to execute SQL statements to add comments: %w", execErr)
			}
			log.Println("INFO: Successfully added comments to the database.")
		} else {
			log.Println("INFO: Comment addition aborted by user.")
		}
	} else {
		log.Println("INFO: No comments to add.")
	}

	log.Println("INFO: Add comments operation completed.")
	return nil
}

func init() {
	var outputFile string
	var tables string
	var enrichments string
	var contextFiles string
	var model string

	// Flags for add-comments command
	addCommentsCmd.Flags().StringVarP(&outputFile, "out_file", "o", "", "File path to output generated SQL statements (defaults to <database>_comments.sql)")
	addCommentsCmd.Flags().StringVar(&tables, "tables", "", "Comma-separated list of tables and columns to include (e.g., 'table1[col1,col2],table2,table3[col4]')")
	addCommentsCmd.Flags().StringVar(&enrichments, "enrichments", "", "Comma-separated list of enrichments to include (e.g., 'examples,distinct_values,null_count,foreign_keys,primary_keys,description').  If empty, all enrichments are included.")
	addCommentsCmd.Flags().StringVar(&contextFiles, "context", "", "Comma-separated list of context files to provide additional information for description generation.")
	addCommentsCmd.Flags().StringVar(&model, "model", "gemini-1.5-pro-002", "Model to use for description enrichment.  If empty, the default modelb is used.")
}

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

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/enricher"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/utils"
	"github.com/spf13/cobra"
)

var deleteCommentsCmd = &cobra.Command{
	Use:     "delete-comments",
	Short:   "Delete comments added by gemini from database columns",
	Long:    `Deletes the portion of column comments that are within the <gemini> tags, leaving other parts of the comment untouched.`,
	Example: `./db_schema_enricher delete-comments --dialect cloudsqlpostgres --username user --password pass --database mydb --cloudsql-instance-connection-name my-project:my-region:my-instance --dry-run --tables "table1[column1,column3],table2,table4[columnx,columnz]"`,
	RunE:    runDeleteComments,
}

func runDeleteComments(cmd *cobra.Command, args []string) error {
	dbConfig := database.GetConfig()
	if dbConfig == nil {
		return fmt.Errorf("database config is not initialized")
	}

	if err := validateDialect(dialect); err != nil {
		return err
	}

	outputFile := cmd.Flag("out_file").Value.String()
	if outputFile == "" {
		outputFile = utils.GetDefaultOutputFilePath(dbConfig.DBName, "delete-comments")
	}

	log.Println("INFO: Starting delete-comments operation", "dialect:", dbConfig.Dialect, "database:", dbConfig.DBName)

	db, err := setupDatabase()
	if err != nil {
		return err
	}
	defer db.Close()

	metadataCollector := enricher.NewMetadataCollector(db, &enricher.DefaultRetryOptions, dryRun, geminiAPIKey, "", "")

	ctx := cmd.Context()

	tablesFlag := cmd.Flag("tables").Value.String()
	tableFilters, err := utils.ParseTablesFlag(tablesFlag)
	if err != nil {
		return err
	}
	metadataCollector.TableFilters = tableFilters

	sqlStatements, err := metadataCollector.GenerateDeleteCommentSQLs(ctx)
	if err != nil {
		return fmt.Errorf("metadata collection and SQL generation for delete comments failed: %w", err)
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
	log.Println("INFO: SQL statements to delete column comments have been written to:", outputFile)

	if dryRun {
		log.Println("INFO: No comments were actually deleted in dry-run mode. Run apply-comments to delete comments.")
		return nil
	}

	if len(sqlStatements) > 0 {
		if utils.ConfirmAction("SQL statements to delete column comments") {
			if execErr := db.ExecuteSQLStatements(ctx, sqlStatements); execErr != nil {
				return fmt.Errorf("failed to execute SQL statements to delete comments: %w", execErr)
			}
			log.Println("INFO: Successfully deleted gemini comments from the database.")
		} else {
			log.Println("INFO: Comment deletion aborted by user.")
		}
	} else {
		log.Println("INFO: No gemini comments found to delete.")
	}

	log.Println("INFO: Delete comments operation completed, dry_run:", dryRun)
	return nil
}

func init() {
	var outputFile string
	var tables string

	// Flags for delete-comments command
	deleteCommentsCmd.Flags().StringVarP(&outputFile, "out_file", "o", "", "File path to output generated SQL statements (defaults to <database>_comments.sql)")
	deleteCommentsCmd.Flags().StringVar(&tables, "tables", "", "Comma-separated list of tables and columns to include for comment deletion (e.g., 'table1[col1,col2],table2,table3[col4]')")
}

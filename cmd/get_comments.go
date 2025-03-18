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

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/enricher"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/utils"
	"github.com/spf13/cobra"
)

var getCommentsCmd = &cobra.Command{
	Use:     "get-comments",
	Short:   "Get comments from database columns",
	Long:    `Retrieves column comments from the database and outputs them to the terminal or a file.`,
	Example: `./db_schema_enricher get-comments --dialect cloudsqlpostgres --username user --password pass --database mydb --cloudsql-instance-connection-name my-project:my-region:my-instance --out ./mydb_comments.txt`,
	RunE:    runGetComments,
}

func runGetComments(cmd *cobra.Command, args []string) error {
	if err := validateDialect(dialect); err != nil {
		return err
	}

	dbConfig := database.GetConfig()
	if dbConfig == nil {
		return fmt.Errorf("database config is not initialized")
	}

	outputFile := cmd.Flag("out_file").Value.String()
	if outputFile == "" {
		outputFile = utils.GetDefaultOutputFilePath(dbConfig.DBName, "get-comments")
	}

	log.Println("INFO: Starting get-comments operation",
		"dialect:", dialect,
		"database:", dbName,
	)

	db, err := setupDatabase()
	if err != nil {
		return err
	}
	defer db.Close()

	metadataCollector := enricher.NewMetadataCollector(db, &enricher.DefaultRetryOptions, dryRun, geminiAPIKey, "", "")
	ctx := cmd.Context()
	comments, err := metadataCollector.GetComments(ctx)
	if err != nil {
		return fmt.Errorf("failed to retrieve comments: %w", err)
	}

	output := enricher.FormatCommentsAsText(comments)
	if err := enricher.WriteCommentsToFile(output, outputFile); err != nil {
		return fmt.Errorf("failed to write comments to file: %w", err)
	}
	fmt.Printf("Comments written to: %s\n", outputFile)

	log.Println("INFO: Get comments operation completed")
	return nil
}

func init() {
	var outputFile string

	// Flags for get-comments command
	getCommentsCmd.Flags().StringVarP(&outputFile, "out_file", "o", "", "File path to save comments to (optional, defaults to <database>_comments.txt)")
}

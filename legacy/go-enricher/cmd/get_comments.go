package cmd

import (
	"fmt"
	"log"
	"os"

	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/enricher"
	"github.com/spf13/cobra"
)

var getCommentsCmd = &cobra.Command{
	Use:     "get-comments",
	Short:   "Retrieve existing column and table comments from the database",
	Long:    `Connects to the database and fetches all existing comments associated with tables and columns. Outputs the comments to a specified file or a default file.`,
	Example: `./db_schema_enricher get-comments --dialect mysql --host db.example.com --port 3306 --username user --password pass --database inventory_db --out_file ./inventory_comments.txt --tables "orders,products[product_id]"`,
	RunE:    runGetComments,
}

func runGetComments(cmd *cobra.Command, args []string) error {
	cfg := getAppConfig()
	ctx := cmd.Context()

	outputFile := cfg.OutputFile
	if outputFile == "" {
		outputFile = cfg.GetDefaultOutputFile("get-comments")
	}

	log.Println("INFO: Starting get-comments operation", "dialect:", cfg.Database.Dialect, "database:", cfg.Database.DBName)

	dbAdapter, err := database.New(cfg.Database)
	if err != nil {
		return fmt.Errorf("failed to initialize database connection: %w", err)
	}
	defer dbAdapter.Close()
	log.Println("INFO: Database connection established successfully.")

	enricherCfg := enricher.Config{MaskPII: appCfg.MaskPII}
	svc := enricher.NewService(dbAdapter, nil, enricherCfg)

	getParams := enricher.GetCommentsParams{}

	comments, err := svc.GetComments(ctx, getParams)
	if err != nil {
		log.Printf("ERROR: Failed during comment retrieval: %v", err)
		if len(comments) > 0 {
			log.Printf("WARN: %d comments were retrieved before the error occurred.", len(comments))
		}
		return fmt.Errorf("failed to retrieve comments: %w", err)
	}

	if len(comments) == 0 {
		log.Println("INFO: No comments found in the database (or matching the specified filters).")
		return nil
	}

	log.Printf("INFO: Retrieved %d comments.", len(comments))

	formattedComments := enricher.FormatCommentsAsText(comments)

	writeErr := os.WriteFile(outputFile, []byte(formattedComments), 0644)
	if writeErr != nil {
		return fmt.Errorf("failed to write comments to file '%s': %w", outputFile, writeErr)
	}

	log.Println("INFO: Comments successfully written to:", outputFile)
	log.Println("INFO: Get comments operation completed.")
	return nil
}

func init() {
	getCommentsCmd.Flags().StringVarP(&appCfg.OutputFile, "out_file", "o", "", "Path to the output file to save the comments (defaults to <database_name>_comments.txt)")
}

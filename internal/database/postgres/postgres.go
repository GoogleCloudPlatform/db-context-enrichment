package postgres

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"net"
	"strings"

	"cloud.google.com/go/cloudsqlconn"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/config"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/stdlib"
	"github.com/lib/pq"
)

type postgresHandler struct{}

var _ database.DialectHandler = (*postgresHandler)(nil)

func (h postgresHandler) CreateCloudSQLPool(cfg config.DatabaseConfig) (*sql.DB, error) {
	mustGetenv := func(k string, cfg config.DatabaseConfig) string {
		v := ""
		switch k {
		case "user_name":
			v = cfg.User
		case "password":
			v = cfg.Password
		case "database_name":
			v = cfg.DBName
		case "instance_name":
			v = cfg.CloudSQLInstanceConnectionName
		case "PRIVATE_IP":
			if cfg.UsePrivateIP {
				v = "true"
			}
		}
		return v
	}

	dbUser := mustGetenv("user_name", cfg)
	dbPwd := mustGetenv("password", cfg)
	dbName := mustGetenv("database_name", cfg)
	instanceConnectionName := mustGetenv("instance_name", cfg)
	usePrivate := mustGetenv("PRIVATE_IP", cfg)

	if dbUser == "" || dbPwd == "" || dbName == "" || instanceConnectionName == "" {
		return nil, fmt.Errorf("missing required CloudSQL connection parameter (user, pass, db, instance)")
	}

	dsn := fmt.Sprintf("user=%s password=%s database=%s", dbUser, dbPwd, dbName)
	pgxCfg, err := pgx.ParseConfig(dsn)
	if err != nil {
		return nil, fmt.Errorf("pgx.ParseConfig failed: %w", err)
	}

	var opts []cloudsqlconn.Option
	if usePrivate != "" && strings.ToLower(usePrivate) != "false" && usePrivate != "0" {
		opts = append(opts, cloudsqlconn.WithDefaultDialOptions(cloudsqlconn.WithPrivateIP()))
	}
	d, err := cloudsqlconn.NewDialer(context.Background(), opts...)
	if err != nil {
		return nil, fmt.Errorf("cloudsqlconn.NewDialer failed: %w", err)
	}

	pgxCfg.DialFunc = func(ctx context.Context, network, instance string) (net.Conn, error) {
		return d.Dial(ctx, instanceConnectionName)
	}

	dbURI := stdlib.RegisterConnConfig(pgxCfg)
	dbPool, err := sql.Open("pgx", dbURI)
	if err != nil {
		d.Close()
		return nil, fmt.Errorf("sql.Open failed for CloudSQL: %w", err)
	}

	return dbPool, nil
}

func (h postgresHandler) CreateStandardPool(cfg config.DatabaseConfig) (*sql.DB, error) {
	sslmode := cfg.SSLMode
	if sslmode == "" {
		sslmode = "disable"
	}
	connStr := fmt.Sprintf(
		"host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		cfg.Host, cfg.Port, cfg.User, cfg.Password, cfg.DBName, sslmode,
	)

	dbPool, err := sql.Open("postgres", connStr)
	if err != nil {
		return nil, fmt.Errorf("error opening standard database connection: %w", err)
	}
	return dbPool, nil
}

func (h postgresHandler) QuoteIdentifier(name string) string {
	name = strings.Replace(name, `"`, `""`, -1)
	return fmt.Sprintf(`"%s"`, name)
}

func (h postgresHandler) ListTables(db *database.DB) ([]string, error) {
	query := `
		SELECT table_name
		FROM information_schema.tables
		WHERE table_schema = current_schema()
		AND table_type = 'BASE TABLE'
		ORDER BY table_name;`

	rows, err := db.Pool.Query(query)
	if err != nil {
		return nil, fmt.Errorf("error querying tables: %w", err)
	}
	defer rows.Close()

	var tables []string
	for rows.Next() {
		var tableName string
		if err := rows.Scan(&tableName); err != nil {
			return nil, fmt.Errorf("error scanning table name: %w", err)
		}
		tables = append(tables, tableName)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating table rows: %w", err)
	}

	return tables, nil
}

func (h postgresHandler) ListColumns(db *database.DB, tableName string) ([]database.ColumnInfo, error) {
	query := `
		SELECT column_name, data_type
		FROM information_schema.columns
		WHERE table_schema = current_schema()
		AND table_name = $1
		ORDER BY ordinal_position;`

	rows, err := db.Pool.Query(query, tableName)
	if err != nil {
		return nil, fmt.Errorf("error querying columns for table %s: %w", tableName, err)
	}
	defer rows.Close()

	var columns []database.ColumnInfo
	for rows.Next() {
		var colInfo database.ColumnInfo
		if err := rows.Scan(&colInfo.Name, &colInfo.DataType); err != nil {
			return nil, fmt.Errorf("error scanning column name and data type: %w", err)
		}
		columns = append(columns, colInfo)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating column rows: %w", err)
	}

	return columns, nil
}

func (h postgresHandler) GetColumnMetadata(db *database.DB, tableName string, columnName string) (map[string]interface{}, error) {
	quotedTable := h.QuoteIdentifier(tableName)
	quotedColumn := h.QuoteIdentifier(columnName)

	ctx := context.Background()

	distinctQuery := fmt.Sprintf("SELECT COUNT(DISTINCT %s::text) FROM %s", quotedColumn, quotedTable)
	var distinctCount int64
	err := db.Pool.QueryRowContext(ctx, distinctQuery).Scan(&distinctCount)
	if err != nil {
		log.Printf("WARN: Failed to get distinct count for %s.%s: %v. Reporting -1.", tableName, columnName, err)
		distinctCount = -1
	}

	nullQuery := fmt.Sprintf("SELECT COUNT(*) FROM %s WHERE %s IS NULL", quotedTable, quotedColumn)
	var nullCount int64
	err = db.Pool.QueryRowContext(ctx, nullQuery).Scan(&nullCount)
	if err != nil {
		return nil, fmt.Errorf("failed to get null count for %s.%s: %w", tableName, columnName, err)
	}

	exampleQuery := fmt.Sprintf("SELECT DISTINCT %s::text FROM %s WHERE %s IS NOT NULL LIMIT 3",
		quotedColumn, quotedTable, quotedColumn)
	rows, err := db.Pool.QueryContext(ctx, exampleQuery)
	if err != nil {
		return nil, fmt.Errorf("failed to get example values for %s.%s: %w", tableName, columnName, err)
	}
	defer rows.Close()

	var examples []string
	for rows.Next() {
		var value sql.NullString
		if err := rows.Scan(&value); err != nil {
			return nil, fmt.Errorf("error scanning example value for %s.%s: %w", tableName, columnName, err)
		}
		if value.Valid {
			examples = append(examples, value.String)
		}
	}
	if rows.Err() != nil {
		return nil, fmt.Errorf("error iterating example values for %s.%s: %w", tableName, columnName, rows.Err())
	}

	return map[string]interface{}{
		"DistinctCount": distinctCount,
		"NullCount":     nullCount,
		"ExampleValues": examples,
	}, nil
}

func (h postgresHandler) formatExampleValues(values []string) string {
	if len(values) == 0 {
		return ""
	}
	quoted := make([]string, len(values))
	for i, v := range values {
		trimmed := strings.ReplaceAll(v, "\n", " ")
		if len(trimmed) > 100 {
			trimmed = trimmed[:100] + "...[truncated]"
		}
		quoted[i] = pq.QuoteLiteral(trimmed)
	}
	return fmt.Sprintf("Examples: [%s]", strings.Join(quoted, ", "))
}

func (h postgresHandler) GenerateCommentSQL(db *database.DB, data *database.CommentData, enrichments map[string]bool) (string, error) {
	if data == nil || data.TableName == "" || data.ColumnName == "" {
		return "", fmt.Errorf("invalid input for GenerateCommentSQL")
	}

	formattedExamples := h.formatExampleValues(data.ExampleValues)
	newMetadataComment := database.GenerateMetadataCommentString(data, enrichments, formattedExamples) // Use database.Generate...

	existingComment, err := h.GetColumnComment(context.Background(), db, data.TableName, data.ColumnName)
	if err != nil && err != sql.ErrNoRows {
		log.Printf("WARN: Failed to get existing column comment for %s.%s: %v. Proceeding as if empty.", data.TableName, data.ColumnName, err)
		existingComment = ""
	}

	finalComment := database.MergeComments(existingComment, newMetadataComment, db.Config.UpdateExistingMode) // Use database.Merge...

	quotedComment := pq.QuoteLiteral(finalComment)
	return fmt.Sprintf(
		"COMMENT ON COLUMN %s.%s IS %s;",
		h.QuoteIdentifier(data.TableName),
		h.QuoteIdentifier(data.ColumnName),
		quotedComment,
	), nil
}

func (h postgresHandler) GenerateDeleteCommentSQL(ctx context.Context, db *database.DB, tableName string, columnName string) (string, error) {
	if tableName == "" || columnName == "" {
		return "", fmt.Errorf("table and column names cannot be empty for GenerateDeleteCommentSQL")
	}

	existingComment, err := h.GetColumnComment(ctx, db, tableName, columnName)
	if err != nil {
		if err == sql.ErrNoRows {
			return "", nil
		}
		return "", fmt.Errorf("failed to get existing column comment for %s.%s before delete: %w", tableName, columnName, err)
	}

	finalComment := database.MergeComments(existingComment, "", "")

	if finalComment == strings.TrimSpace(existingComment) {
		return "", nil
	}

	quotedComment := pq.QuoteLiteral(finalComment)
	return fmt.Sprintf(
		"COMMENT ON COLUMN %s.%s IS %s;",
		h.QuoteIdentifier(tableName),
		h.QuoteIdentifier(columnName),
		quotedComment,
	), nil
}

func (h postgresHandler) GetColumnComment(ctx context.Context, db *database.DB, tableName string, columnName string) (string, error) {
	query := `
		SELECT description
		FROM pg_catalog.pg_description
		JOIN pg_catalog.pg_class c ON pg_description.objoid = c.oid
		JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
		JOIN pg_catalog.pg_attribute a ON pg_description.objoid = a.attrelid AND pg_description.objsubid = a.attnum
		WHERE n.nspname = current_schema()
		  AND c.relname = $1
		  AND a.attname = $2;
	`
	var comment sql.NullString
	err := db.Pool.QueryRowContext(ctx, query, tableName, columnName).Scan(&comment)

	if err != nil {
		if err == sql.ErrNoRows {
			return "", nil
		}
		log.Printf("ERROR: Failed retrieving column comment for %s.%s: %v", tableName, columnName, err)
		return "", fmt.Errorf("failed to retrieve column comment for %s.%s: %w", tableName, columnName, err)
	}
	return comment.String, nil
}

func (h postgresHandler) GenerateTableCommentSQL(db *database.DB, data *database.TableCommentData, enrichments map[string]bool) (string, error) {
	if data == nil || data.TableName == "" {
		return "", fmt.Errorf("invalid input for GenerateTableCommentSQL")
	}

	newMetadataComment := database.GenerateTableMetadataCommentString(data, enrichments) // Use database.Generate...

	existingComment, err := h.GetTableComment(context.Background(), db, data.TableName)
	if err != nil && err != sql.ErrNoRows {
		log.Printf("WARN: Failed to get existing table comment for %s: %v. Proceeding as if empty.", data.TableName, err)
		existingComment = ""
	}

	finalComment := database.MergeComments(existingComment, newMetadataComment, db.Config.UpdateExistingMode) // Use database.Merge...

	if finalComment == strings.TrimSpace(existingComment) {
		return "", nil
	}

	quotedComment := pq.QuoteLiteral(finalComment)
	return fmt.Sprintf(
		"COMMENT ON TABLE %s IS %s;",
		h.QuoteIdentifier(data.TableName),
		quotedComment,
	), nil
}

func (h postgresHandler) GetTableComment(ctx context.Context, db *database.DB, tableName string) (string, error) {
	query := `
        SELECT pg_catalog.obj_description(c.oid, 'pg_class')
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = current_schema()
          AND c.relname = $1;
    `
	var comment sql.NullString
	err := db.Pool.QueryRowContext(ctx, query, tableName).Scan(&comment)
	if err != nil {
		if err == sql.ErrNoRows {
			return "", nil
		}
		log.Printf("ERROR: Failed retrieving table comment for %s: %v", tableName, err)
		return "", fmt.Errorf("failed to retrieve table comment for %s: %w", tableName, err)
	}
	return comment.String, nil
}

func (h postgresHandler) GenerateDeleteTableCommentSQL(ctx context.Context, db *database.DB, tableName string) (string, error) {
	if tableName == "" {
		return "", fmt.Errorf("table name cannot be empty for GenerateDeleteTableCommentSQL")
	}

	existingComment, err := h.GetTableComment(ctx, db, tableName)
	if err != nil {
		if err == sql.ErrNoRows {
			return "", nil
		}
		return "", fmt.Errorf("failed to get existing table comment for %s before delete: %w", tableName, err)
	}

	finalComment := database.MergeComments(existingComment, "", "")

	if finalComment == strings.TrimSpace(existingComment) {
		return "", nil
	}

	quotedComment := pq.QuoteLiteral(finalComment)
	return fmt.Sprintf(
		"COMMENT ON TABLE %s IS %s;",
		h.QuoteIdentifier(tableName),
		quotedComment,
	), nil
}

func (h postgresHandler) GetForeignKeys(db *database.DB, tableName string, columnName string) ([]database.ForeignKeyReference, error) {
	query := `
		SELECT 
		    ccu.table_name AS referenced_table,
		    ccu.column_name AS referenced_column,
		    tc.constraint_name
		FROM information_schema.table_constraints tc
		JOIN information_schema.key_column_usage kcu 
		    ON tc.constraint_name = kcu.constraint_name
		    AND tc.table_schema = kcu.table_schema
		JOIN information_schema.constraint_column_usage ccu 
		    ON ccu.constraint_name = tc.constraint_name
		    AND ccu.table_schema = tc.table_schema
		WHERE tc.constraint_type = 'FOREIGN KEY'
		    AND tc.table_name = $1
		    AND kcu.column_name = $2
		    AND tc.table_schema = current_schema()`

	rows, err := db.Pool.Query(query, tableName, columnName)
	if err != nil {
		return nil, fmt.Errorf("error querying foreign keys for table %s, column %s: %w", tableName, columnName, err)
	}
	defer rows.Close()

	var foreignKeys []database.ForeignKeyReference
	for rows.Next() {
		var fk database.ForeignKeyReference
		if err := rows.Scan(&fk.ReferencedTable, &fk.ReferencedColumn, &fk.ConstraintName); err != nil {
			return nil, fmt.Errorf("error scanning foreign key data: %w", err)
		}
		foreignKeys = append(foreignKeys, fk)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating foreign key rows: %w", err)
	}

	return foreignKeys, nil
}

func init() {
	database.RegisterDialectHandler("postgres", postgresHandler{})
	database.RegisterDialectHandler("cloudsqlpostgres", postgresHandler{})
}

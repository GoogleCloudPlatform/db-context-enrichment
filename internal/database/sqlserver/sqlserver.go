package sqlserver

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"net"
	"net/url"
	"strings"

	"cloud.google.com/go/cloudsqlconn"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/config"
	"github.com/GoogleCloudPlatform/db-context-enrichment/internal/database"
	mssql "github.com/denisenkom/go-mssqldb"
)

type sqlServerHandler struct{}

var _ database.DialectHandler = (*sqlServerHandler)(nil)

type csqlDialer struct {
	instanceDialer *cloudsqlconn.Dialer
	connName       string
	usePrivate     bool
}

func (c *csqlDialer) DialContext(ctx context.Context, network, addr string) (net.Conn, error) {
	var opts []cloudsqlconn.DialOption
	if c.usePrivate {
		opts = append(opts, cloudsqlconn.WithPrivateIP())
	}
	conn, err := c.instanceDialer.Dial(ctx, c.connName, opts...)
	if err != nil {
		log.Printf("ERROR: Cloud SQL dial failed for %s: %v", c.connName, err)
	}
	return conn, err
}

func (h sqlServerHandler) CreateCloudSQLPool(cfg config.DatabaseConfig) (*sql.DB, error) {
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
	usePrivateStr := mustGetenv("PRIVATE_IP", cfg)

	if dbUser == "" || dbName == "" || instanceConnectionName == "" {
		return nil, fmt.Errorf("missing required CloudSQL connection parameter (user, db, instance)")
	}

	d, err := cloudsqlconn.NewDialer(context.Background(), cloudsqlconn.WithLazyRefresh())
	if err != nil {
		return nil, fmt.Errorf("cloudsqlconn.NewDialer: %w", err)
	}

	query := url.Values{}
	query.Add("database", dbName)
	u := &url.URL{
		Scheme:   "sqlserver",
		User:     url.UserPassword(dbUser, dbPwd),
		Host:     "cloudsql-instance",
		RawQuery: query.Encode(),
	}

	connector, err := mssql.NewConnector(u.String())
	if err != nil {
		d.Close()
		return nil, fmt.Errorf("mssql.NewConnector failed: %w", err)
	}

	connector.Dialer = &csqlDialer{
		instanceDialer: d,
		connName:       instanceConnectionName,
		usePrivate:     usePrivateStr != "" && strings.ToLower(usePrivateStr) != "false" && usePrivateStr != "0",
	}

	dbPool := sql.OpenDB(connector)
	return dbPool, nil
}

func (h sqlServerHandler) CreateStandardPool(cfg config.DatabaseConfig) (*sql.DB, error) {
	port := cfg.Port
	if port == 0 {
		port = 1433
	}

	query := url.Values{}
	query.Add("database", cfg.DBName)

	u := &url.URL{
		Scheme:   "sqlserver",
		User:     url.UserPassword(cfg.User, cfg.Password),
		Host:     fmt.Sprintf("%s:%d", cfg.Host, port),
		RawQuery: query.Encode(),
	}

	connStr := u.String()
	dbPool, err := sql.Open("sqlserver", connStr)
	if err != nil {
		return nil, fmt.Errorf("sql.Open (standard sqlserver): %w", err)
	}
	return dbPool, nil
}

func (h sqlServerHandler) QuoteIdentifier(name string) string {
	name = strings.ReplaceAll(name, "]", "]]")
	return fmt.Sprintf("[%s]", name)
}

func (h sqlServerHandler) ListTables(db *database.DB) ([]string, error) {
	query := `
		  SELECT TABLE_NAME
		  FROM INFORMATION_SCHEMA.TABLES
		  WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_CATALOG = DB_NAME() AND TABLE_SCHEMA = 'dbo'
		  ORDER BY TABLE_NAME;
		  `
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

func (h sqlServerHandler) ListColumns(db *database.DB, tableName string) ([]database.ColumnInfo, error) {
	query := `
		  SELECT COLUMN_NAME, DATA_TYPE
		  FROM INFORMATION_SCHEMA.COLUMNS
		  WHERE TABLE_CATALOG = DB_NAME()
			AND TABLE_SCHEMA = 'dbo'
			AND TABLE_NAME = @p1
		  ORDER BY ORDINAL_POSITION;
		  `

	rows, err := db.Pool.Query(query, sql.Named("p1", tableName))
	if err != nil {
		return nil, fmt.Errorf("error querying columns for table %s: %w", tableName, err)
	}
	defer rows.Close()

	var columns []database.ColumnInfo
	for rows.Next() {
		var colInfo database.ColumnInfo
		if err := rows.Scan(&colInfo.Name, &colInfo.DataType); err != nil {
			return nil, fmt.Errorf("error scanning column details: %w", err)
		}
		columns = append(columns, colInfo)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating column rows: %w", err)
	}
	return columns, nil
}

func (h sqlServerHandler) GetColumnMetadata(db *database.DB, tableName string, columnName string) (map[string]interface{}, error) {
	schemaName := "dbo"
	quotedSchema := h.QuoteIdentifier(schemaName)
	quotedTable := h.QuoteIdentifier(tableName)
	quotedColumn := h.QuoteIdentifier(columnName)
	fullQuotedTable := fmt.Sprintf("%s.%s", quotedSchema, quotedTable)

	ctx := context.Background()

	distinctQuery := fmt.Sprintf("SELECT COUNT_BIG(DISTINCT %s) FROM %s", quotedColumn, fullQuotedTable)
	var distinctCount int64
	err := db.Pool.QueryRowContext(ctx, distinctQuery).Scan(&distinctCount)
	if err != nil {
		log.Printf("WARN: Failed to get distinct count for %s.%s.%s (type may not support DISTINCT): %v. Reporting -1.", schemaName, tableName, columnName, err)
		distinctCount = -1
	}

	nullQuery := fmt.Sprintf("SELECT COUNT_BIG(*) FROM %s WHERE %s IS NULL", fullQuotedTable, quotedColumn)
	var nullCount int64
	err = db.Pool.QueryRowContext(ctx, nullQuery).Scan(&nullCount)
	if err != nil {
		return nil, fmt.Errorf("failed to get null count for %s.%s: %w", tableName, columnName, err)
	}

	exampleQuery := fmt.Sprintf("SELECT TOP (@p1) DISTINCT CAST(%s AS NVARCHAR(MAX)) FROM %s WHERE %s IS NOT NULL",
		quotedColumn, fullQuotedTable, quotedColumn)
	rows, err := db.Pool.QueryContext(ctx, exampleQuery, sql.Named("p1", 3))
	if err != nil {
		log.Printf("ERROR executing example query [%s]: %v", exampleQuery, err)
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

func escapeSQLServerString(value string) string {
	return strings.ReplaceAll(value, "'", "''")
}

func escapeAndQuoteSQLServerString(value string) string {
	return fmt.Sprintf("N'%s'", escapeSQLServerString(value))
}

func (h sqlServerHandler) formatExampleValues(values []string) string {
	if len(values) == 0 {
		return ""
	}
	escaped := make([]string, len(values))
	for i, v := range values {
		escaped[i] = escapeSQLServerString(v)
	}
	return fmt.Sprintf("Examples: ['%s']", strings.Join(escaped, "', '"))
}

func (h sqlServerHandler) GenerateCommentSQL(db *database.DB, data *database.CommentData, enrichments map[string]bool) (string, error) {
	if data == nil || data.TableName == "" || data.ColumnName == "" {
		return "", fmt.Errorf("invalid input for GenerateCommentSQL")
	}
	schemaName := "dbo"

	formattedExamples := h.formatExampleValues(data.ExampleValues)
	newMetadataComment := database.GenerateMetadataCommentString(data, enrichments, formattedExamples)

	existingComment, _ := h.GetColumnComment(context.Background(), db, data.TableName, data.ColumnName)

	finalComment := database.MergeComments(existingComment, newMetadataComment, db.Config.UpdateExistingMode)

	propertyExists, checkErr := h.checkExtendedPropertyExists(context.Background(), db, schemaName, data.TableName, data.ColumnName)
	if checkErr != nil {
		return "", fmt.Errorf("failed to check existing property for %s.%s.%s: %w", schemaName, data.TableName, data.ColumnName, checkErr)
	}

	var sqlStmt string
	quotedSchema := escapeAndQuoteSQLServerString(schemaName)
	quotedTable := escapeAndQuoteSQLServerString(data.TableName)
	quotedColumn := escapeAndQuoteSQLServerString(data.ColumnName)
	quotedCommentValue := escapeAndQuoteSQLServerString(finalComment)

	if !propertyExists {
		if finalComment == "" {
			return "", nil
		}
		sqlStmt = fmt.Sprintf(
			`EXEC sp_addextendedproperty @name=N'MS_Description', @value=%s, @level0type=N'SCHEMA', @level0name=%s, @level1type=N'TABLE', @level1name=%s, @level2type=N'COLUMN', @level2name=%s;`,
			quotedCommentValue,
			quotedSchema,
			quotedTable,
			quotedColumn,
		)
	} else {
		sqlStmt = fmt.Sprintf(
			`EXEC sp_updateextendedproperty @name=N'MS_Description', @value=%s, @level0type=N'SCHEMA', @level0name=%s, @level1type=N'TABLE', @level1name=%s, @level2type=N'COLUMN', @level2name=%s;`,
			quotedCommentValue,
			quotedSchema,
			quotedTable,
			quotedColumn,
		)
	}
	return strings.TrimSpace(sqlStmt), nil
}

func (h sqlServerHandler) GenerateDeleteCommentSQL(ctx context.Context, db *database.DB, tableName string, columnName string) (string, error) {
	if tableName == "" || columnName == "" {
		return "", fmt.Errorf("table and column names cannot be empty for GenerateDeleteCommentSQL")
	}
	schemaName := "dbo"

	propertyExists, checkErr := h.checkExtendedPropertyExists(ctx, db, schemaName, tableName, columnName)
	if checkErr != nil {
		return "", fmt.Errorf("failed to check existing property for delete %s.%s.%s: %w", schemaName, tableName, columnName, checkErr)
	}
	if !propertyExists {
		return "", nil
	}

	existingComment, err := h.GetColumnComment(ctx, db, tableName, columnName)
	if err != nil {
		log.Printf("WARN: Property MS_Description exists for %s.%s.%s but failed to get value: %v", schemaName, tableName, columnName, err)
		existingComment = ""
	}

	finalComment := database.MergeComments(existingComment, "", "")

	if finalComment == strings.TrimSpace(existingComment) {
		return "", nil
	}

	quotedSchema := escapeAndQuoteSQLServerString(schemaName)
	quotedTable := escapeAndQuoteSQLServerString(tableName)
	quotedColumn := escapeAndQuoteSQLServerString(columnName)
	quotedCommentValue := escapeAndQuoteSQLServerString(finalComment)

	sqlStmt := fmt.Sprintf(
		`EXEC sp_updateextendedproperty @name=N'MS_Description', @value=%s, @level0type=N'SCHEMA', @level0name=%s, @level1type=N'TABLE', @level1name=%s, @level2type=N'COLUMN', @level2name=%s;`,
		quotedCommentValue,
		quotedSchema,
		quotedTable,
		quotedColumn,
	)
	return strings.TrimSpace(sqlStmt), nil
}

func (h sqlServerHandler) GetColumnComment(ctx context.Context, db *database.DB, tableName string, columnName string) (string, error) {
	schemaName := "dbo"
	query := `
		  SELECT CAST(p.value AS NVARCHAR(MAX))
		  FROM sys.extended_properties AS p
		  INNER JOIN sys.tables AS t ON p.major_id = t.object_id
		  INNER JOIN sys.columns AS c ON p.major_id = c.object_id AND p.minor_id = c.column_id
		  INNER JOIN sys.schemas AS s ON t.schema_id = s.schema_id
		  WHERE p.class = 1
			AND p.name = N'MS_Description'
			AND s.name = @p1
			AND t.name = @p2
			AND c.name = @p3;
	  `

	var comment sql.NullString
	err := db.Pool.QueryRowContext(ctx, query,
		sql.Named("p1", schemaName),
		sql.Named("p2", tableName),
		sql.Named("p3", columnName),
	).Scan(&comment)

	if err != nil {
		if err == sql.ErrNoRows {
			return "", nil
		}
		log.Printf("ERROR: Failed to retrieve column comment for %s.%s.%s: %v", schemaName, tableName, columnName, err)
		return "", fmt.Errorf("failed to retrieve column comment for %s.%s.%s: %w", schemaName, tableName, columnName, err)
	}

	if comment.Valid {
		return comment.String, nil
	}
	return "", nil
}

func (h sqlServerHandler) GenerateTableCommentSQL(db *database.DB, data *database.TableCommentData, enrichments map[string]bool) (string, error) {
	if data == nil || data.TableName == "" {
		return "", fmt.Errorf("table comment data cannot be nil or empty")
	}
	schemaName := "dbo"

	newMetadataComment := database.GenerateTableMetadataCommentString(data, enrichments)

	existingComment, _ := h.GetTableComment(context.Background(), db, data.TableName)

	finalComment := database.MergeComments(existingComment, newMetadataComment, db.Config.UpdateExistingMode)

	if finalComment == strings.TrimSpace(existingComment) {
		return "", nil
	}

	propertyExists, checkErr := h.checkExtendedPropertyExists(context.Background(), db, schemaName, data.TableName, "")
	if checkErr != nil {
		return "", fmt.Errorf("failed to check existing property for table %s.%s: %w", schemaName, data.TableName, checkErr)
	}

	var sqlStmt string
	quotedSchema := escapeAndQuoteSQLServerString(schemaName)
	quotedTable := escapeAndQuoteSQLServerString(data.TableName)
	quotedCommentValue := escapeAndQuoteSQLServerString(finalComment)

	if !propertyExists {
		if finalComment == "" {
			return "", nil
		}
		sqlStmt = fmt.Sprintf(
			`EXEC sp_addextendedproperty @name=N'MS_Description', @value=%s, @level0type=N'SCHEMA', @level0name=%s, @level1type=N'TABLE', @level1name=%s;`,
			quotedCommentValue, quotedSchema, quotedTable)
	} else {
		sqlStmt = fmt.Sprintf(
			`EXEC sp_updateextendedproperty @name=N'MS_Description', @value=%s, @level0type=N'SCHEMA', @level0name=%s, @level1type=N'TABLE', @level1name=%s;`,
			quotedCommentValue, quotedSchema, quotedTable)
	}
	return strings.TrimSpace(sqlStmt), nil
}

func (h sqlServerHandler) GetTableComment(ctx context.Context, db *database.DB, tableName string) (string, error) {
	schemaName := "dbo"
	query := `
		  SELECT CAST(p.value AS NVARCHAR(MAX))
		  FROM sys.extended_properties AS p
		  INNER JOIN sys.tables AS t ON p.major_id = t.object_id
		  INNER JOIN sys.schemas AS s ON t.schema_id = s.schema_id
		  WHERE p.class = 1
			AND p.minor_id = 0
			AND p.name = N'MS_Description'
			AND s.name = @p1
			AND t.name = @p2;
	  `
	var comment sql.NullString
	err := db.Pool.QueryRowContext(ctx, query,
		sql.Named("p1", schemaName),
		sql.Named("p2", tableName),
	).Scan(&comment)

	if err != nil {
		if err == sql.ErrNoRows {
			return "", nil
		}
		log.Printf("ERROR: Failed to retrieve table comment for %s.%s: %v", schemaName, tableName, err)
		return "", fmt.Errorf("failed to retrieve table comment for %s.%s: %w", schemaName, tableName, err)
	}

	if comment.Valid {
		return comment.String, nil
	}
	return "", nil
}

func (h sqlServerHandler) GenerateDeleteTableCommentSQL(ctx context.Context, db *database.DB, tableName string) (string, error) {
	if tableName == "" {
		return "", fmt.Errorf("table name cannot be empty for GenerateDeleteTableCommentSQL")
	}
	schemaName := "dbo"

	propertyExists, checkErr := h.checkExtendedPropertyExists(ctx, db, schemaName, tableName, "")
	if checkErr != nil {
		return "", fmt.Errorf("failed to check existing property for delete table %s.%s: %w", schemaName, tableName, checkErr)
	}
	if !propertyExists {
		return "", nil
	}

	existingComment, err := h.GetTableComment(ctx, db, tableName)
	if err != nil {
		log.Printf("WARN: Property MS_Description exists for table %s.%s but failed to get value: %v", schemaName, tableName, err)
		existingComment = ""
	}

	finalComment := database.MergeComments(existingComment, "", "")

	if finalComment == strings.TrimSpace(existingComment) {
		return "", nil
	}

	quotedSchema := escapeAndQuoteSQLServerString(schemaName)
	quotedTable := escapeAndQuoteSQLServerString(tableName)
	quotedCommentValue := escapeAndQuoteSQLServerString(finalComment)

	sqlStmt := fmt.Sprintf(
		`EXEC sp_updateextendedproperty @name=N'MS_Description', @value=%s, @level0type=N'SCHEMA', @level0name=%s, @level1type=N'TABLE', @level1name=%s;`,
		quotedCommentValue, quotedSchema, quotedTable)

	return strings.TrimSpace(sqlStmt), nil
}

func (h sqlServerHandler) checkExtendedPropertyExists(ctx context.Context, db *database.DB, schemaName, tableName, columnName string) (bool, error) {
	var query string
	params := []interface{}{sql.Named("p1", schemaName), sql.Named("p2", tableName)}

	if columnName == "" {
		query = `
			  SELECT 1
			  FROM sys.extended_properties AS p
			  INNER JOIN sys.tables AS t ON p.major_id = t.object_id
			  INNER JOIN sys.schemas AS s ON t.schema_id = s.schema_id
			  WHERE p.class = 1 AND p.minor_id = 0 AND p.name = N'MS_Description'
				AND s.name = @p1 AND t.name = @p2;
		  `
	} else {
		query = `
			  SELECT 1
			  FROM sys.extended_properties AS p
			  INNER JOIN sys.tables AS t ON p.major_id = t.object_id
			  INNER JOIN sys.columns AS c ON p.major_id = c.object_id AND p.minor_id = c.column_id
			  INNER JOIN sys.schemas AS s ON t.schema_id = s.schema_id
			  WHERE p.class = 1 AND p.name = N'MS_Description'
				AND s.name = @p1 AND t.name = @p2 AND c.name = @p3;
		  `
		params = append(params, sql.Named("p3", columnName))
	}

	var exists int
	err := db.Pool.QueryRowContext(ctx, query, params...).Scan(&exists)

	if err != nil {
		if err == sql.ErrNoRows {
			return false, nil
		}
		target := fmt.Sprintf("%s.%s", schemaName, tableName)
		if columnName != "" {
			target += "." + columnName
		}
		log.Printf("ERROR: Failed checking extended property existence for %s: %v", target, err)
		return false, fmt.Errorf("failed checking extended property existence for %s: %w", target, err)
	}
	return true, nil
}

func init() {
	database.RegisterDialectHandler("sqlserver", sqlServerHandler{})
	database.RegisterDialectHandler("cloudsqlsqlserver", sqlServerHandler{})
}

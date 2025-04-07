package mysql

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
	"github.com/go-sql-driver/mysql"
)

type mysqlHandler struct{}

var _ database.DialectHandler = (*mysqlHandler)(nil)

func (h mysqlHandler) CreateCloudSQLPool(cfg config.DatabaseConfig) (*sql.DB, error) {
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

	d, err := cloudsqlconn.NewDialer(context.Background())
	if err != nil {
		return nil, fmt.Errorf("cloudsqlconn.NewDialer: %w", err)
	}

	var opts []cloudsqlconn.DialOption
	if usePrivate != "" && strings.ToLower(usePrivate) != "false" && usePrivate != "0" {
		opts = append(opts, cloudsqlconn.WithPrivateIP())
	}

	network := fmt.Sprintf("cloudsql-%s", instanceConnectionName)

	mysql.RegisterDialContext(network,
		func(ctx context.Context, addr string) (net.Conn, error) {
			conn, dialErr := d.Dial(ctx, instanceConnectionName, opts...)
			if dialErr != nil {
				log.Printf("ERROR: Cloud SQL dial failed for %s: %v", instanceConnectionName, dialErr)
			}
			return conn, dialErr
		})

	mysqlCfg := mysql.Config{
		User:                 dbUser,
		Passwd:               dbPwd,
		Net:                  network,
		Addr:                 instanceConnectionName,
		DBName:               dbName,
		AllowNativePasswords: true,
		ParseTime:            true,
	}

	dbPool, err := sql.Open("mysql", mysqlCfg.FormatDSN())
	if err != nil {
		mysql.DeregisterDialContext(network)
		d.Close()
		return nil, fmt.Errorf("sql.Open failed for CloudSQL MySQL: %w", err)
	}
	return dbPool, nil
}

func (h mysqlHandler) CreateStandardPool(cfg config.DatabaseConfig) (*sql.DB, error) {
	mysqlCfg := mysql.Config{
		User:                 cfg.User,
		Passwd:               cfg.Password,
		Net:                  "tcp",
		Addr:                 fmt.Sprintf("%s:%d", cfg.Host, cfg.Port),
		DBName:               cfg.DBName,
		AllowNativePasswords: true,
		ParseTime:            true,
	}
	connStr := mysqlCfg.FormatDSN()

	dbPool, err := sql.Open("mysql", connStr)
	if err != nil {
		return nil, fmt.Errorf("sql.Open (standard mysql): %w", err)
	}
	return dbPool, nil
}

func (h mysqlHandler) QuoteIdentifier(name string) string {
	name = strings.ReplaceAll(name, "`", "``")
	return fmt.Sprintf("`%s`", name)
}

func (h mysqlHandler) ListTables(db *database.DB) ([]string, error) {
	query := "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME"

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

func (h mysqlHandler) ListColumns(db *database.DB, tableName string) ([]database.ColumnInfo, error) {
	query := `
		  SELECT COLUMN_NAME, COLUMN_TYPE
		  FROM information_schema.COLUMNS
		  WHERE TABLE_SCHEMA = DATABASE()
			AND TABLE_NAME = ?
		  ORDER BY ORDINAL_POSITION;`

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

func (h mysqlHandler) GetColumnMetadata(db *database.DB, tableName string, columnName string) (map[string]interface{}, error) {
	quotedTable := h.QuoteIdentifier(tableName)
	quotedColumn := h.QuoteIdentifier(columnName)
	ctx := context.Background()

	distinctQuery := fmt.Sprintf("SELECT COUNT(DISTINCT %s) FROM %s", quotedColumn, quotedTable)
	var distinctCount int64
	err := db.Pool.QueryRowContext(ctx, distinctQuery).Scan(&distinctCount)
	if err != nil {
		log.Printf("WARN: Failed to get distinct count for %s.%s (may require specific privileges or type): %v. Reporting -1.", tableName, columnName, err)
		distinctCount = -1
	}

	nullQuery := fmt.Sprintf("SELECT COUNT(*) FROM %s WHERE %s IS NULL", quotedTable, quotedColumn)
	var nullCount int64
	err = db.Pool.QueryRowContext(ctx, nullQuery).Scan(&nullCount)
	if err != nil {
		return nil, fmt.Errorf("failed to get null count for %s.%s: %w", tableName, columnName, err)
	}

	exampleQuery := fmt.Sprintf("SELECT DISTINCT CAST(%s AS CHAR) FROM %s WHERE %s IS NOT NULL LIMIT 3",
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

func escapeMySQLString(value string) string {
	value = strings.ReplaceAll(value, `\`, `\\`)
	value = strings.ReplaceAll(value, `'`, `''`)
	return value
}

func (h mysqlHandler) formatExampleValues(values []string) string {
	if len(values) == 0 {
		return ""
	}
	quoted := make([]string, len(values))
	for i, v := range values {
		quoted[i] = fmt.Sprintf("'%s'", escapeMySQLString(v))
	}
	return fmt.Sprintf("Examples: [%s]", strings.Join(quoted, ", "))
}

func (h mysqlHandler) GenerateCommentSQL(db *database.DB, data *database.CommentData, enrichments map[string]bool) (string, error) {
	if data == nil || data.TableName == "" || data.ColumnName == "" {
		return "", fmt.Errorf("invalid input for GenerateCommentSQL")
	}

	formattedExamples := h.formatExampleValues(data.ExampleValues)
	newMetadataComment := database.GenerateMetadataCommentString(data, enrichments, formattedExamples)

	existingComment, err := h.GetColumnComment(context.Background(), db, data.TableName, data.ColumnName)
	if err != nil && err != sql.ErrNoRows {
		log.Printf("WARN: Failed to get existing column comment for %s.%s: %v. Proceeding as if empty.", data.TableName, data.ColumnName, err)
		existingComment = ""
	}

	finalComment := database.MergeComments(existingComment, newMetadataComment, db.Config.UpdateExistingMode)

	columnDataType, err := h.getColumnDataType(context.Background(), db, data.TableName, data.ColumnName)
	if err != nil {
		return "", fmt.Errorf("failed to get column data type for %s.%s: %w", data.TableName, data.ColumnName, err)
	}
	if columnDataType == "" {
		return "", fmt.Errorf("could not determine data type for column %s.%s, cannot generate comment SQL", data.TableName, data.ColumnName)
	}

	quotedComment := fmt.Sprintf("'%s'", escapeMySQLString(finalComment))
	return fmt.Sprintf(
		"ALTER TABLE %s MODIFY COLUMN %s %s COMMENT %s;",
		h.QuoteIdentifier(data.TableName),
		h.QuoteIdentifier(data.ColumnName),
		columnDataType,
		quotedComment,
	), nil
}

func (h mysqlHandler) GenerateDeleteCommentSQL(ctx context.Context, db *database.DB, tableName string, columnName string) (string, error) {
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

	columnDataType, err := h.getColumnDataType(ctx, db, tableName, columnName)
	if err != nil {
		return "", fmt.Errorf("failed to get column data type for deleting comment on %s.%s: %w", tableName, columnName, err)
	}
	if columnDataType == "" {
		return "", fmt.Errorf("could not determine data type for column %s.%s, cannot generate delete comment SQL", tableName, columnName)
	}

	quotedComment := fmt.Sprintf("'%s'", escapeMySQLString(finalComment))
	return fmt.Sprintf(
		"ALTER TABLE %s MODIFY COLUMN %s %s COMMENT %s;",
		h.QuoteIdentifier(tableName),
		h.QuoteIdentifier(columnName),
		columnDataType,
		quotedComment,
	), nil
}

func (h mysqlHandler) GetColumnComment(ctx context.Context, db *database.DB, tableName string, columnName string) (string, error) {
	query := `
		  SELECT COLUMN_COMMENT
		  FROM information_schema.COLUMNS
		  WHERE TABLE_SCHEMA = DATABASE()
			AND TABLE_NAME = ?
			AND COLUMN_NAME = ?;
	  `

	var comment sql.NullString
	err := db.Pool.QueryRowContext(ctx, query, tableName, columnName).Scan(&comment)

	if err != nil {
		if err == sql.ErrNoRows {
			return "", nil
		}
		log.Printf("ERROR: Failed to retrieve column comment for %s.%s: %v", tableName, columnName, err)
		return "", fmt.Errorf("failed to retrieve column comment for %s.%s: %w", tableName, columnName, err)
	}

	if comment.Valid {
		return comment.String, nil
	}
	return "", nil
}

func (h mysqlHandler) getColumnDataType(ctx context.Context, db *database.DB, tableName string, columnName string) (string, error) {
	query := `
		  SELECT COLUMN_TYPE
		  FROM information_schema.COLUMNS
		  WHERE TABLE_SCHEMA = DATABASE()
			AND TABLE_NAME = ?
			AND COLUMN_NAME = ?;
	  `
	var columnType sql.NullString
	err := db.Pool.QueryRowContext(ctx, query, tableName, columnName).Scan(&columnType)
	if err != nil {
		if err == sql.ErrNoRows {
			return "", fmt.Errorf("column %s.%s not found when retrieving data type", tableName, columnName)
		}
		return "", fmt.Errorf("failed to retrieve column type for %s.%s: %w", tableName, columnName, err)
	}
	if !columnType.Valid || columnType.String == "" {
		return "", fmt.Errorf("retrieved null or empty column type for %s.%s", tableName, columnName)
	}
	return columnType.String, nil
}

func (h mysqlHandler) GenerateTableCommentSQL(db *database.DB, data *database.TableCommentData, enrichments map[string]bool) (string, error) {
	if data == nil || data.TableName == "" {
		return "", fmt.Errorf("table comment data cannot be nil or empty")
	}

	newMetadataComment := database.GenerateTableMetadataCommentString(data, enrichments)

	existingComment, err := h.GetTableComment(context.Background(), db, data.TableName)
	if err != nil && err != sql.ErrNoRows {
		log.Printf("WARN: Failed to get existing table comment for %s: %v. Proceeding as if empty.", data.TableName, err)
		existingComment = ""
	}

	finalComment := database.MergeComments(existingComment, newMetadataComment, db.Config.UpdateExistingMode)

	if finalComment == strings.TrimSpace(existingComment) {
		return "", nil
	}

	quotedComment := fmt.Sprintf("'%s'", escapeMySQLString(finalComment))
	return fmt.Sprintf(
		"ALTER TABLE %s COMMENT = %s;",
		h.QuoteIdentifier(data.TableName),
		quotedComment,
	), nil
}

func (h mysqlHandler) GetTableComment(ctx context.Context, db *database.DB, tableName string) (string, error) {
	query := `
		  SELECT TABLE_COMMENT
		  FROM information_schema.TABLES
		  WHERE TABLE_SCHEMA = DATABASE()
			AND TABLE_NAME = ?;
	  `

	var comment sql.NullString
	err := db.Pool.QueryRowContext(ctx, query, tableName).Scan(&comment)
	if err != nil {
		if err == sql.ErrNoRows {
			return "", nil
		}
		log.Printf("ERROR: Failed to retrieve table comment for %s: %v", tableName, err)
		return "", fmt.Errorf("failed to retrieve table comment for %s: %w", tableName, err)
	}

	if comment.Valid {
		return comment.String, nil
	}
	return "", nil
}

func (h mysqlHandler) GenerateDeleteTableCommentSQL(ctx context.Context, db *database.DB, tableName string) (string, error) {
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

	quotedComment := fmt.Sprintf("'%s'", escapeMySQLString(finalComment))
	return fmt.Sprintf(
		"ALTER TABLE %s COMMENT = %s;",
		h.QuoteIdentifier(tableName),
		quotedComment,
	), nil
}

func init() {
	database.RegisterDialectHandler("mysql", mysqlHandler{})
	database.RegisterDialectHandler("cloudsqlmysql", mysqlHandler{})
}

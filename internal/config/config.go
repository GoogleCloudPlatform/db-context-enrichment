package config

import (
	"fmt"
	"os"
	"strings"
)

// DatabaseConfig holds database connection configuration
type DatabaseConfig struct {
	Dialect                        string
	Host                           string
	Port                           int
	User                           string
	Password                       string
	DBName                         string
	SSLMode                        string
	CloudSQLInstanceConnectionName string
	UsePrivateIP                   bool
	UpdateExistingMode             string
}

// Validate checks the database configuration for required fields based on dialect.
func (dbc *DatabaseConfig) Validate() error {
	if dbc.Dialect == "" {
		return fmt.Errorf("database dialect is required (--dialect)")
	}
	supportedDialects := map[string]bool{
		"postgres":          true,
		"cloudsqlpostgres":  true,
		"mysql":             true,
		"cloudsqlmysql":     true,
		"sqlserver":         true,
		"cloudsqlsqlserver": true,
	}
	if !supportedDialects[dbc.Dialect] {
		return fmt.Errorf("unsupported dialect: %s", dbc.Dialect)
	}

	// Validate connection details based on dialect type
	isCloudSQL := strings.HasPrefix(dbc.Dialect, "cloudsql")

	if isCloudSQL {
		if dbc.CloudSQLInstanceConnectionName == "" {
			return fmt.Errorf("Cloud SQL instance connection name is required (--cloudsql-instance-connection-name) for dialect %s", dbc.Dialect)
		}
		if dbc.User == "" {
			return fmt.Errorf("database username is required (--username)")
		}
		if dbc.Password == "" {
			return fmt.Errorf("database password is required (--password)")
		}
		if dbc.DBName == "" {
			return fmt.Errorf("database name is required (--database)")
		}
	} else {
		// Standard connection
		if dbc.Host == "" {
			return fmt.Errorf("database host is required (--host) for dialect %s", dbc.Dialect)
		}
		if dbc.Port == 0 {
			return fmt.Errorf("database port is required (--port) for dialect %s", dbc.Dialect)
		}
		if dbc.User == "" {
			return fmt.Errorf("database username is required (--username)")
		}
		if dbc.Password == "" {
			return fmt.Errorf("database password is required (--password)")
		}
		if dbc.DBName == "" {
			return fmt.Errorf("database name is required (--database)")
		}
	}

	// Validate update_existing mode
	dbc.UpdateExistingMode = strings.ToLower(dbc.UpdateExistingMode)
	if dbc.UpdateExistingMode != "overwrite" && dbc.UpdateExistingMode != "append" {
		return fmt.Errorf("invalid value for --update_existing: '%s'. Must be 'overwrite' or 'append'", dbc.UpdateExistingMode)
	}

	return nil
}

// AppConfig holds all configuration for the application, populated from flags/env vars.
type AppConfig struct {
	Database        DatabaseConfig
	GeminiAPIKey    string
	DryRun          bool
	OutputFile      string
	InputFile       string
	TablesRaw       string
	EnrichmentsRaw  string
	ContextFilesRaw string
	Model           string
}

// NewAppConfig creates an AppConfig with default values.
func NewAppConfig() *AppConfig {
	return &AppConfig{
		// Default values set here. They will be overridden by flags.
		DryRun: true,
		Database: DatabaseConfig{
			SSLMode:            "disable",
			UpdateExistingMode: "overwrite",
		},
		Model: "gemini-1.5-pro-002",
	}
}

// LoadAndValidate populates the Gemini API key from environment if not set via flag,
// and then validates the entire configuration.
func (cfg *AppConfig) LoadAndValidate() error {
	if cfg.GeminiAPIKey == "" {
		cfg.GeminiAPIKey = os.Getenv("GEMINI_API_KEY")
	}
	// Validate Database config first
	if err := cfg.Database.Validate(); err != nil {
		return fmt.Errorf("database configuration error: %w", err)
	}
	return nil
}

// GetDefaultOutputFile returns the default output file path based on DB name and command.
func (cfg *AppConfig) GetDefaultOutputFile(commandName string) string {
	dbName := "output"
	if cfg.Database.DBName != "" {
		dbName = cfg.Database.DBName
	}

	switch commandName {
	case "get-comments":
		return fmt.Sprintf("%s_comments.txt", dbName)
	default:
		return fmt.Sprintf("%s_comments.sql", dbName)
	}
}

// GetDefaultInputFile returns the default input file path.
func (cfg *AppConfig) GetDefaultInputFile() string {
	dbName := "output"
	if cfg.Database.DBName != "" {
		dbName = cfg.Database.DBName
	}
	return fmt.Sprintf("%s_comments.sql", dbName)
}

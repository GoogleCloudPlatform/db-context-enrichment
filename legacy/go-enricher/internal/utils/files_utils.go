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
package utils

import (
	"bufio"
	"fmt"
	"os"
	"strings"
)

func ReadSQLStatementsFromFile(filePath string) ([]string, error) {
	content, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read file: %w", err)
	}

	sqlStatements := strings.Split(string(content), ";\n")
	var trimmedStatements []string
	for _, stmt := range sqlStatements {
		trimmedStmt := strings.TrimSpace(stmt)
		if trimmedStmt != "" {
			trimmedStatements = append(trimmedStatements, trimmedStmt)
		}
	}
	return trimmedStatements, nil
}

// ReadContextFiles reads the content of the specified context files and combines them into a single string.
func ReadContextFiles(filePaths string) (string, error) {
	if filePaths == "" {
		return "", nil // No context files provided
	}

	paths := strings.Split(filePaths, ",")
	var combinedContext strings.Builder
	for _, path := range paths {
		path = strings.TrimSpace(path)
		content, err := os.ReadFile(path)
		if err != nil {
			return "", fmt.Errorf("failed to read context file '%s': %w", path, err)
		}
		combinedContext.WriteString("\n-- Context from file: " + path + " --\n")
		combinedContext.WriteString(string(content))
	}
	return combinedContext.String(), nil
}

func GetDefaultOutputFilePath(dbName, commandName string) string {
	switch commandName {
	case "get-comments":
		return fmt.Sprintf("%s_comments.txt", dbName)
	default: // add-comments, delete-comments, etc.
		return fmt.Sprintf("%s_comments.sql", dbName)
	}
}

func ConfirmAction(actionDescription string) bool {
	reader := bufio.NewReader(os.Stdin)
	fmt.Printf("\n-------------------------------------------------------------\n")
	fmt.Printf("Generated %s:\n", actionDescription)
	fmt.Print("Do you want to apply these changes to the database? (yes/no): ")
	text, _ := reader.ReadString('\n')
	action := strings.TrimSpace(strings.ToLower(text))
	return action == "yes" || action == "y"
}

func ParseTablesFlag(tablesFlag string) (map[string][]string, error) {
	tableColumns := make(map[string][]string)
	if tablesFlag == "" {
		return tableColumns, nil
	}

	// strip any whitespace
	tablesFlag = strings.ReplaceAll(tablesFlag, " ", "")

	// Split by comma, but only if the comma is not within square brackets
	parts := SplitOutsideBrackets(tablesFlag)

	for _, part := range parts {
		part = strings.TrimSpace(part)

		// Check if there are columns specified
		bracketStart := strings.Index(part, "[")
		if bracketStart != -1 {
			bracketEnd := strings.Index(part, "]")
			if bracketEnd == -1 {
				return nil, fmt.Errorf("missing closing bracket in: %s", part)
			}

			tableName := strings.TrimSpace(part[:bracketStart])
			columnsStr := strings.TrimSpace(part[bracketStart+1 : bracketEnd])

			// Split columns by comma and trim spaces
			columns := strings.Split(columnsStr, ",")
			var trimmedColumns []string
			for _, col := range columns {
				trimmedColumns = append(trimmedColumns, strings.TrimSpace(col))
			}
			tableColumns[tableName] = trimmedColumns
		} else {
			// No columns specified, just table name
			tableColumns[part] = nil
		}
	}

	return tableColumns, nil
}

// SplitOutsideBrackets Helper function to split string by commas that are not within brackets
func SplitOutsideBrackets(s string) []string {
	var result []string
	var current strings.Builder
	inBrackets := false

	for _, char := range s {
		switch char {
		case '[':
			inBrackets = true
			current.WriteRune(char)
		case ']':
			inBrackets = false
			current.WriteRune(char)
		case ',':
			if inBrackets {
				current.WriteRune(char)
			} else {
				result = append(result, current.String())
				current.Reset()
			}
		default:
			current.WriteRune(char)
		}
	}

	// Add the last part
	if current.Len() > 0 {
		result = append(result, current.String())
	}

	return result
}

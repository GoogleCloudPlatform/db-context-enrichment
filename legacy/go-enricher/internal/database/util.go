package database

import (
	"fmt"
	"strings"
)

const (
	StartTag = "<gemini>"
	EndTag   = "</gemini>"
)

// isEnrichmentRequested checks if a specific enrichment is requested.
// If the enrichments map is empty, all are considered requested.
func isEnrichmentRequested(enrichment string, enrichments map[string]bool) bool {
	if len(enrichments) == 0 {
		return true
	}
	return enrichments[strings.ToLower(enrichment)]
}

// generateMetadataCommentString constructs the metadata portion of the column comment.
// It takes the pre-formatted example string as input.
func GenerateMetadataCommentString(data *CommentData, enrichments map[string]bool, formattedExamples string) string {
	if data == nil {
		return ""
	}

	var commentParts []string
	isReq := func(e string) bool { return isEnrichmentRequested(e, enrichments) }

	if isReq("examples") && formattedExamples != "" {
		commentParts = append(commentParts, formattedExamples)
	}
	if isReq("distinct_values") && data.DistinctCount >= 0 {
		commentParts = append(commentParts, fmt.Sprintf("Distinct Values: %d", data.DistinctCount))
	}
	if isReq("null_count") {
		commentParts = append(commentParts, fmt.Sprintf("Null Count: %d |", data.NullCount))
	}
	if isReq("description") && data.Description != "" {
		commentParts = append(commentParts, data.Description)
	}
	// Add foreign key information to comment
	if isReq("foreign_keys") && len(data.ForeignKeys) > 0 {
		var fkStrings []string
		for _, fk := range data.ForeignKeys {
			fkStrings = append(fkStrings, fmt.Sprintf(`\"%s\".\"%s\"`, fk.ReferencedTable, fk.ReferencedColumn))
		}
		commentParts = append(commentParts, fmt.Sprintf("Foreign Keys: [%s]", strings.Join(fkStrings, ", ")))
	}

	if len(commentParts) == 0 {
		return ""
	}
	return strings.Join(commentParts, " | ")
}

// generateTableMetadataCommentString constructs the metadata portion of the table comment.
func GenerateTableMetadataCommentString(data *TableCommentData, enrichments map[string]bool) string {
	if data == nil || data.Description == "" || !isEnrichmentRequested("description", enrichments) {
		return ""
	}
	return data.Description
}

// mergeComments combines an existing comment with new metadata, handling tags.
func MergeComments(existingComment string, newMetadataComment string, updateExistingMode string) string {
	trimmedExisting := strings.TrimSpace(existingComment)
	newMetadataComment = strings.TrimSpace(newMetadataComment)

	if newMetadataComment == "" {
		if trimmedExisting == StartTag+EndTag || trimmedExisting == StartTag+" "+EndTag {
			return ""
		}
		startIndex := strings.Index(existingComment, StartTag)
		endIndex := strings.LastIndex(existingComment, EndTag)
		if startIndex != -1 && endIndex != -1 && endIndex > startIndex {
			prefix := strings.TrimSpace(existingComment[:startIndex])
			suffix := strings.TrimSpace(existingComment[endIndex+len(EndTag):])
			if updateExistingMode == "append" {
				return trimmedExisting
			}
			if prefix != "" && suffix != "" {
				return prefix + " " + suffix
			}
			return strings.TrimSpace(prefix + suffix)
		}
		return trimmedExisting
	}

	startIndex := strings.Index(existingComment, StartTag)
	endIndex := strings.LastIndex(existingComment, EndTag)

	var finalComment string

	if startIndex == -1 || endIndex == -1 || endIndex <= startIndex {
		if trimmedExisting != "" {
			finalComment = trimmedExisting + " " + StartTag + newMetadataComment + EndTag
		} else {
			finalComment = StartTag + newMetadataComment + EndTag
		}
	} else {
		prefix := strings.TrimSpace(existingComment[:startIndex])
		suffix := strings.TrimSpace(existingComment[endIndex+len(EndTag):])

		if updateExistingMode == "append" {
			currentGeminiComment := strings.TrimSpace(existingComment[startIndex+len(StartTag) : endIndex])
			appendedMetadata := currentGeminiComment
			if appendedMetadata != "" && newMetadataComment != "" {
				appendedMetadata += " | " + newMetadataComment
			} else {
				appendedMetadata = newMetadataComment
			}
			finalComment = prefix
			if prefix != "" {
				finalComment += " "
			}
			finalComment += StartTag + appendedMetadata + EndTag
			if suffix != "" {
				finalComment += " " + suffix
			}
		} else { // Overwrite mode (default)
			finalComment = prefix
			if prefix != "" {
				finalComment += " "
			}
			finalComment += StartTag + newMetadataComment + EndTag
			if suffix != "" {
				finalComment += " " + suffix
			}
		}
	}

	return strings.TrimSpace(finalComment)
}

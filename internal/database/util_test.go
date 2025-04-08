package database

import (
	"strings"
	"testing"
)

func TestIsEnrichmentRequested(t *testing.T) {
	tests := []struct {
		name        string
		enrichment  string
		enrichments map[string]bool
		want        bool
	}{
		{"Empty map means all requested", "description", map[string]bool{}, true},
		{"Empty map means all requested", "examples", map[string]bool{}, true},
		{"Specific requested", "description", map[string]bool{"description": true, "examples": false}, true},
		{"Specific not requested", "examples", map[string]bool{"description": true}, false},
		{"Case insensitivity", "NULL_COUNT", map[string]bool{"null_count": true}, true},
		{"Not present in map", "foobar", map[string]bool{"description": true}, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := isEnrichmentRequested(tt.enrichment, tt.enrichments); got != tt.want {
				t.Errorf("isEnrichmentRequested(%q, %v) = %v, want %v", tt.enrichment, tt.enrichments, got, tt.want)
			}
		})
	}
}

func TestGenerateMetadataCommentString(t *testing.T) {
	tests := []struct {
		name              string
		data              *CommentData
		enrichments       map[string]bool
		formattedExamples string
		want              string
	}{
		{
			name:              "All enrichments, full data",
			data:              &CommentData{Description: "Desc", DistinctCount: 10, NullCount: 5},
			enrichments:       map[string]bool{}, // All
			formattedExamples: "Examples: ['a', 'b']",
			want:              "Desc | Examples: ['a', 'b'] | Distinct: 10 | Nulls: 5",
		},
		{
			name:              "Only description requested",
			data:              &CommentData{Description: "Desc", DistinctCount: 10, NullCount: 5},
			enrichments:       map[string]bool{"description": true},
			formattedExamples: "Examples: ['a', 'b']",
			want:              "Desc",
		},
		{
			name:              "Only examples and nulls requested",
			data:              &CommentData{Description: "Desc", DistinctCount: 10, NullCount: 5},
			enrichments:       map[string]bool{"examples": true, "null_count": true},
			formattedExamples: "Examples: ['a', 'b']",
			want:              "Examples: ['a', 'b'] | Nulls: 5",
		},
		{
			name:              "Distinct count is zero",
			data:              &CommentData{Description: "Desc", DistinctCount: 0, NullCount: 5},
			enrichments:       map[string]bool{},
			formattedExamples: "",
			want:              "Desc | Distinct: 0 | Nulls: 5",
		},
		{
			name:              "Distinct count is negative (error indicator)",
			data:              &CommentData{Description: "Desc", DistinctCount: -1, NullCount: 5},
			enrichments:       map[string]bool{},
			formattedExamples: "",
			want:              "Desc | Nulls: 5", // Distinct shouldn't be added if < 0
		},
		{
			name:              "No description provided",
			data:              &CommentData{Description: "", DistinctCount: 10, NullCount: 5},
			enrichments:       map[string]bool{},
			formattedExamples: "Ex",
			want:              "Ex | Distinct: 10 | Nulls: 5",
		},
		{
			name:              "No examples provided",
			data:              &CommentData{Description: "Desc", DistinctCount: 10, NullCount: 5},
			enrichments:       map[string]bool{},
			formattedExamples: "",
			want:              "Desc | Distinct: 10 | Nulls: 5",
		},
		{
			name:              "No relevant data provided",
			data:              &CommentData{Description: "", DistinctCount: -1, NullCount: 0},
			enrichments:       map[string]bool{},
			formattedExamples: "",
			want:              "Nulls: 0",
		},
		{
			name:              "No relevant data requested",
			data:              &CommentData{Description: "Desc", DistinctCount: 10, NullCount: 5},
			enrichments:       map[string]bool{"foobar": true},
			formattedExamples: "Ex",
			want:              "",
		},
		{
			name:              "Nil data",
			data:              nil,
			enrichments:       map[string]bool{},
			formattedExamples: "",
			want:              "",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := GenerateMetadataCommentString(tt.data, tt.enrichments, tt.formattedExamples); got != tt.want {
				t.Errorf("GenerateMetadataCommentString() = %q, want %q", got, tt.want)
			}
		})
	}
}

func TestGenerateTableMetadataCommentString(t *testing.T) {
	tests := []struct {
		name        string
		data        *TableCommentData
		enrichments map[string]bool
		want        string
	}{
		{
			name:        "Description requested and present",
			data:        &TableCommentData{TableName: "t1", Description: "Table Desc"},
			enrichments: map[string]bool{}, // All
			want:        "Table Desc",
		},
		{
			name:        "Description requested, but empty",
			data:        &TableCommentData{TableName: "t1", Description: ""},
			enrichments: map[string]bool{},
			want:        "",
		},
		{
			name:        "Description present, but not requested",
			data:        &TableCommentData{TableName: "t1", Description: "Table Desc"},
			enrichments: map[string]bool{"examples": true}, // Desc not requested
			want:        "",
		},
		{
			name:        "Nil data",
			data:        nil,
			enrichments: map[string]bool{},
			want:        "",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := GenerateTableMetadataCommentString(tt.data, tt.enrichments); got != tt.want {
				t.Errorf("GenerateTableMetadataCommentString() = %q, want %q", got, tt.want)
			}
		})
	}
}

func TestMergeComments(t *testing.T) {
	tests := []struct {
		name               string
		existingComment    string
		newMetadataComment string
		updateExistingMode string
		want               string
	}{
		// --- Adding new comments ---
		{"Add new metadata to empty existing", "", "New Data", "overwrite", "<gemini>New Data</gemini>"},
		{"Add new metadata to non-tagged existing", "User comment", "New Data", "overwrite", "User comment <gemini>New Data</gemini>"},
		{"Add new metadata to non-tagged existing with spaces", "  User comment  ", " New Data ", "overwrite", "User comment <gemini>New Data</gemini>"},

		// --- Overwriting existing tagged comments ---
		{"Overwrite existing tagged comment", "Old stuff <gemini>Old Data</gemini> More old stuff", "New Data", "overwrite", "Old stuff <gemini>New Data</gemini> More old stuff"},
		{"Overwrite existing tagged comment (no surrounding)", "<gemini>Old Data</gemini>", "New Data", "overwrite", "<gemini>New Data</gemini>"},
		{"Overwrite existing tagged comment with spaces", "  Old <gemini> Old Data </gemini> More  ", " New Data ", "overwrite", "Old <gemini>New Data</gemini> More"},

		// --- Appending to existing tagged comments ---
		{"Append to existing tagged comment", "Prefix <gemini>Old Data</gemini> Suffix", "New Data", "append", "Prefix <gemini>Old Data | New Data</gemini> Suffix"},
		{"Append to existing tagged comment (no surrounding)", "<gemini>Old Data</gemini>", "New Data", "append", "<gemini>Old Data | New Data</gemini>"},
		{"Append to existing tagged comment with spaces", " Prefix  <gemini> Old Data  </gemini>  Suffix ", " New Data ", "append", "Prefix <gemini>Old Data | New Data</gemini> Suffix"},
		{"Append empty metadata (should not add pipe)", "Prefix <gemini>Old Data</gemini> Suffix", "", "append", "Prefix <gemini>Old Data</gemini> Suffix"}, // Append empty = no change
		{"Append metadata to empty gemini tag", "Prefix <gemini></gemini> Suffix", "New Data", "append", "Prefix <gemini>New Data</gemini> Suffix"},
		{"Append metadata to spaced gemini tag", "Prefix <gemini>  </gemini> Suffix", "New Data", "append", "Prefix <gemini>New Data</gemini> Suffix"},

		// --- Removing tagged comments (by passing empty newMetadataComment) ---
		{"Remove tag from existing comment", "User comment <gemini>Some Data</gemini> More comment", "", "overwrite", "User comment More comment"},
		{"Remove tag only comment", "<gemini>Some Data</gemini>", "", "overwrite", ""},
		{"Remove tag only comment with spaces", "  <gemini> Some Data </gemini>  ", "", "overwrite", ""},
		{"Remove empty tag", "<gemini></gemini>", "", "overwrite", ""},
		{"Remove tag when it's the prefix", "<gemini>Some Data</gemini> User comment", "", "overwrite", "User comment"},
		{"Remove tag when it's the suffix", "User comment <gemini>Some Data</gemini>", "", "overwrite", "User comment"},

		// --- Edge cases ---
		{"Existing comment but no new metadata", "User comment", "", "overwrite", "User comment"}, // No change if no tags and no new data
		{"Empty existing, empty new", "", "", "overwrite", ""},
		{"Malformed tags (no end)", "X <gemini>A Y", "New", "overwrite", "X <gemini>A Y <gemini>New</gemini>"},                             // Appends new tag
		{"Malformed tags (no start)", "X A</gemini> Y", "New", "overwrite", "X A</gemini> Y <gemini>New</gemini>"},                         // Appends new tag
		{"Malformed tags (end before start)", "X </gemini>A<gemini> Y", "New", "overwrite", "X </gemini>A<gemini> Y <gemini>New</gemini>"}, // Appends new tag

	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Normalize whitespace in want for easier comparison
			normalizedWant := strings.Join(strings.Fields(tt.want), " ")
			got := MergeComments(tt.existingComment, tt.newMetadataComment, tt.updateExistingMode)
			normalizedGot := strings.Join(strings.Fields(got), " ")

			if normalizedGot != normalizedWant {
				t.Errorf("MergeComments(%q, %q, %q) = %q, want %q", tt.existingComment, tt.newMetadataComment, tt.updateExistingMode, got, tt.want)
			}
		})
	}
}

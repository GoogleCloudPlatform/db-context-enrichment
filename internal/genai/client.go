package genai

import (
	"context"
	"fmt"
	"log"
	"strings"

	"github.com/google/generative-ai-go/genai"
	"google.golang.org/api/option"
	"google.golang.org/grpc/status"
)

// geminiClient implements the LLMClient interface using the Google Gemini API.
type geminiClient struct {
	client *genai.Client
	cfg    Config
}

// LLMClient defines the interface for interacting with a generative AI model.
type LLMClient interface {
	// GenerateDescription generates a description for a database object (table or column).
	GenerateDescription(ctx context.Context, objectType, objectName, parentName, knowledgeContext string) (string, error)

	// GenerateSyntheticExamples analyzes original examples and potentially returns synthetic ones if PII is detected.
	GenerateSyntheticExamples(ctx context.Context, columnName, tableName, dataType string, originalExamples []string) (processedExamples []string, wasSynthesized bool, err error)

	// IsAPIKeyValid checks if the configured API key is functional.
	IsAPIKeyValid(ctx context.Context) error

	// Close cleans up any resources used by the client.
	Close() error
}

// Config holds configuration for the GenAI client.
type Config struct {
	APIKey string
	Model  string
}

// NewClient creates a new Gemini client.
func NewClient(ctx context.Context, cfg Config) (LLMClient, error) {
	if cfg.APIKey == "" {
		return nil, fmt.Errorf("cannot create Gemini client: API key is missing")
	}

	client, err := genai.NewClient(ctx, option.WithAPIKey(cfg.APIKey))
	if err != nil {
		return nil, fmt.Errorf("failed to create Gemini client: %w", err)
	}

	if cfg.Model == "" {
		cfg.Model = "gemini-1.5-flash-latest"
		log.Printf("INFO: Gemini model not specified, defaulting to %s", cfg.Model)
	}

	return &geminiClient{
		client: client,
		cfg:    cfg,
	}, nil
}

// Close cleans up the underlying Gemini client.
func (c *geminiClient) Close() error {
	if c.client != nil {
		return c.client.Close()
	}
	return nil
}

// IsAPIKeyValid checks if the Gemini API key is valid by listing models.
func (c *geminiClient) IsAPIKeyValid(ctx context.Context) error {
	if c.client == nil {
		return fmt.Errorf("gemini client not initialized (likely missing API key)")
	}

	modelIterator := c.client.ListModels(ctx)
	_, err := modelIterator.Next() // Attempt to list one model
	if err != nil {
		if st, ok := status.FromError(err); ok {
			if st.Code() == 16 /* UNAUTHENTICATED */ || st.Code() == 7 /* PERMISSION_DENIED */ {
				return fmt.Errorf("invalid Gemini API key or insufficient permissions: %w", err)
			}
		}
		return fmt.Errorf("failed to verify Gemini API key by listing models: %w", err)
	}
	return nil
}

// GenerateDescription generates a description using the Gemini API.
func (c *geminiClient) GenerateDescription(ctx context.Context, objectType, objectName, parentName, knowledgeContext string) (string, error) {
	if c.client == nil {
		return "", fmt.Errorf("gemini client not initialized")
	}
	if knowledgeContext == "" {
		return "", nil
	}

	var targetDescription string
	var prompt string

	switch strings.ToLower(objectType) {
	case "column":
		targetDescription = fmt.Sprintf("Column Name: %s in Table: %s", objectName, parentName)
		prompt = fmt.Sprintf(`
	Your task is to generate a brief and concise description for a database column based ONLY on the provided knowledge context.

	********** Knowledge Context **********
	%s
	********** End Knowledge Context **********

	**Instructions:**
	1. Analyze the Knowledge Context carefully.
	2. Determine if the context provides any relevant information SPECIFICALLY about the target column '%s' within the table '%s'.
	3. If relevant information is found, generate a concise description (max 50 words) summarizing that information. Output ONLY the description text within <result></result> tags.
	4. If NO relevant information about THIS SPECIFIC column/table combination is found in the context, output empty <result></result> tags. Do NOT invent descriptions or use general knowledge.

	Target: %s

	Begin analysis and provide description if applicable:
	`, knowledgeContext, objectName, parentName, targetDescription)

	case "table":
		targetDescription = fmt.Sprintf("Table: %s", objectName)
		prompt = fmt.Sprintf(`
	Your task is to generate a brief and concise description for a database table based ONLY on the provided knowledge context.

	********** Knowledge Context **********
	%s
	********** End Knowledge Context **********

	**Instructions:**
	1. Analyze the Knowledge Context carefully.
	2. Determine if the context provides any relevant information SPECIFICALLY about the target table '%s'.
	3. If relevant information is found, generate a concise description (max 50 words) summarizing that information. Output ONLY the description text within <result></result> tags.
	4. If NO relevant information about THIS SPECIFIC table is found in the context, output empty <result></result> tags. Do NOT invent descriptions or use general knowledge.

	Target: %s

	Begin analysis and provide description if applicable:
	`, knowledgeContext, objectName, targetDescription)

	default:
		return "", fmt.Errorf("unsupported object type for description generation: %s", objectType)
	}

	// --- Call Gemini API ---
	model := c.client.GenerativeModel(c.cfg.Model)
	model.SetTemperature(0.3)
	model.SetMaxOutputTokens(150)
	model.SetTopP(0.9)
	model.SetTopK(40)

	resp, err := model.GenerateContent(ctx, genai.Text(prompt))
	if err != nil {
		return "", fmt.Errorf("Gemini API call failed: %w", err)
	}

	description, err := extractTextBetweenTags(resp, "<result>", "</result>")
	if err != nil {
		log.Printf("WARN: Could not extract description from Gemini response for %s: %v. Response: %v", targetDescription, err, resp)
		return "", nil
	}

	log.Printf("INFO: Generated description for %s using model %s.", targetDescription, c.cfg.Model)
	return description, nil
}

// GenerateSyntheticExamples generates synthetic examples if PII is detected.
func (c *geminiClient) GenerateSyntheticExamples(ctx context.Context, columnName, tableName, dataType string, originalExamples []string) (processedExamples []string, wasSynthesized bool, err error) {
	if c.client == nil {
		return originalExamples, false, fmt.Errorf("gemini client not initialized")
	}
	if len(originalExamples) == 0 {
		return []string{}, false, nil
	}

	exampleValuesStr := strings.Join(originalExamples, ", ")

	prompt := fmt.Sprintf(`
	You are an expert in data privacy and database metadata. Analyze the following database column and its example values for Personally Identifiable Information (PII).

	**Column Information:**
	- Column Name: %s
	- Table Name: %s
	- Data Type: %s
	- Original Example Values: [%s]

	**Instructions:**
	1. **Analyze for PII:** Based ONLY on the column name, data type, and example values, determine if this column is LIKELY to contain PII (e.g., names, emails, phones, addresses, specific IDs). Be conservative; if unsure, assume it's NOT PII.
	2. **Decision & Output:**
	- **If LIKELY PII:** Generate %d synthetic, plausible-looking example values that match the likely *pattern* and *data type* (%s) of the original data but are clearly fake. Output these values as a comma-separated list enclosed ONLY in <synthetic_examples>...</synthetic_examples> tags.
	- **If NOT LIKELY PII (or unsure):** Return the original example values provided. Output these values as a comma-separated list enclosed ONLY in <original_examples>...</original_examples> tags.

	**Example Output (Synthetic):** <synthetic_examples>user1@example.com, user2@example.net, user3@example.org</synthetic_examples>
	**Example Output (Original):** <original_examples>Active, Inactive, Pending</original_examples>

	Provide your output based on the analysis:
	`, columnName, tableName, dataType, exampleValuesStr, len(originalExamples), dataType) // Request same number of examples

	model := c.client.GenerativeModel(c.cfg.Model)
	model.SetTemperature(0.5)
	model.SetMaxOutputTokens(500)
	model.SetTopP(0.9)
	model.SetTopK(40)

	resp, err := model.GenerateContent(ctx, genai.Text(prompt))
	if err != nil {
		return originalExamples, false, nil
	}

	fullResponseText, extractErr := getFirstTextPart(resp)
	if extractErr != nil {
		return originalExamples, false, nil
	}

	syntheticContent, foundSynthetic := extractContentBetween(fullResponseText, "<synthetic_examples>", "</synthetic_examples>")
	if foundSynthetic {
		examples := parseCommaSeparated(syntheticContent)
		if len(examples) > 0 {
			log.Printf("INFO: Gemini determined column '%s.%s' might be PII; generated %d synthetic examples.", tableName, columnName, len(examples))
			return examples, true, nil
		}
		return originalExamples, false, nil
	}

	// Try extracting original
	originalContent, foundOriginal := extractContentBetween(fullResponseText, "<original_examples>", "</original_examples>")
	if foundOriginal {
		examples := parseCommaSeparated(originalContent)
		if len(examples) > 0 {
			return originalExamples, false, nil
		}
		return originalExamples, false, nil
	}

	return originalExamples, false, nil
}

// getFirstTextPart extracts the first text part from a Gemini response.
func getFirstTextPart(resp *genai.GenerateContentResponse) (string, error) {
	if resp == nil || len(resp.Candidates) == 0 || resp.Candidates[0].Content == nil || len(resp.Candidates[0].Content.Parts) == 0 {
		finishReason := "unknown"
		safetyRatings := "none"
		if resp != nil && len(resp.Candidates) > 0 {
			finishReason = resp.Candidates[0].FinishReason.String()
			if resp.Candidates[0].SafetyRatings != nil {
				safetyRatings = fmt.Sprintf("%v", resp.Candidates[0].SafetyRatings)
			}
		}
		return "", fmt.Errorf("empty or incomplete response from Gemini API. FinishReason: %s, SafetyRatings: %s", finishReason, safetyRatings)
	}
	part := resp.Candidates[0].Content.Parts[0]
	text, ok := part.(genai.Text)
	if !ok {
		return "", fmt.Errorf("unexpected response part type: %T", part)
	}
	return string(text), nil
}

// extractTextBetweenTags extracts text between the first occurrence of startTag and endTag.
func extractTextBetweenTags(resp *genai.GenerateContentResponse, startTag, endTag string) (string, error) {
	fullText, err := getFirstTextPart(resp)
	if err != nil {
		return "", fmt.Errorf("failed to get text part: %w", err)
	}

	content, found := extractContentBetween(fullText, startTag, endTag)
	if !found {
		return "", fmt.Errorf("tags '%s' and '%s' not found in response", startTag, endTag)
	}
	return content, nil
}

// extractContentBetween extracts content between start and end tags from a string.
func extractContentBetween(text, startTag, endTag string) (string, bool) {
	startIndex := strings.Index(text, startTag)
	if startIndex == -1 {
		return "", false
	}
	startIndex += len(startTag)
	endIndex := strings.Index(text[startIndex:], endTag)
	if endIndex == -1 {
		return "", false
	}
	return strings.TrimSpace(text[startIndex : startIndex+endIndex]), true
}

// parseCommaSeparated parses a comma-separated string into a slice of trimmed strings.
func parseCommaSeparated(s string) []string {
	if s == "" {
		return []string{}
	}
	parts := strings.Split(s, ",")
	result := make([]string, 0, len(parts))
	for _, p := range parts {
		trimmed := strings.TrimSpace(p)
		if trimmed != "" {
			result = append(result, trimmed)
		}
	}
	return result
}

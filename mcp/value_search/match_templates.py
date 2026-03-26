from typing import Dict, Any, List
from enum import Enum


class Dialect(str, Enum):
    """Supported database dialects."""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    GOOGLE_SQL = "googlesql"


_MATCH_CONFIG: Dict[Dialect, Dict[str, Any]] = {
    Dialect.POSTGRESQL: {
        "min_version": "13",
        
        # Default templates
        "defaults": {
            "EXACT_MATCH_STRINGS": {
                "description": "Exact match for strings (Standard SQL).",
                "example": "Use when finding a specific state code (e.g., 'CA'), order ID, or exact product name where precise spelling is required.",
                "sql_template": (
                    "SELECT $value as value, '{table}.{column}' as columns, "
                    "'{concept_type}' as concept_type, 0 as distance, "
                    "'' as context FROM \"{table}\" T WHERE T.\"{column}\" = $value"
                ),
            },
            "TRIGRAM_STRING_MATCH": {
                "description": "Fuzzy text match using trigram similarity (Requires extension: pg_trgm).",
                "example": "Use when searching for names, addresses, or plain text where users might have typos, misspellings, or partial matches.",
                "sql_template": (
                    "WITH TrigramMetrics AS ("
                    "    SELECT T.\"{column}\" AS original_value, "
                    "    (T.\"{column}\" <-> $value::text) AS normalized_dist "
                    "    FROM \"{table}\" T "
                    "    WHERE T.\"{column}\" % $value::text"
                    ") "
                    "SELECT original_value AS value, '{table}.{column}' AS columns, "
                    "'{concept_type}' AS concept_type, normalized_dist AS distance, "
                    "''::text AS context FROM TrigramMetrics"
                ),
            },
            "SEMANTIC_SIMILARITY_GEMINI": {
                "description": "Semantic similarity search using Gemini text embeddings (Requires extensions: vector, google_ml_integration).",
                "example": "Use when searching for concepts, descriptions, themes, or abstract text where the exact words might differ but the underlying meaning is similar.",
                "sql_template": (
                    "WITH SemanticMetrics AS ("
                    "    SELECT T.\"{column}\" AS original_value, ("
                    "        (google_ml.embedding('gemini-embedding-001', $value)::vector <=> "
                    "         google_ml.embedding('gemini-embedding-001', T.\"{column}\")::vector) / 2.0"
                    "    ) AS normalized_dist "
                    "    FROM \"{table}\" T "
                    "    WHERE T.\"{column}\" IS NOT NULL"
                    ") "
                    "SELECT original_value AS value, '{table}.{column}' AS columns, "
                    "'{concept_type}' AS concept_type, normalized_dist AS distance, "
                    "''::text AS context FROM SemanticMetrics"
                ),
            }
        },
        "overrides": {}
    },
    Dialect.GOOGLE_SQL: {
        "min_version": "1",
        "defaults": {
            "EXACT_MATCH_STRINGS": {
                "description": "Exact match for strings in Spanner.",
                "example": "Use for exact IDs or state codes in Spanner.",
                "sql_template": (
                    "SELECT CAST($value AS STRING) AS value, '{column}' AS `columns`, "
                    "'{concept_type}' AS concept_type, 0 AS distance, "
                    "JSON '{{}}' AS context "
                    "FROM `{table}` AS T "
                    "WHERE CAST(T.`{column}` AS STRING) = CAST($value AS STRING) "
                )
            },
            "TRIGRAM_STRING_MATCH": {
                "description": "String similarity using Spanner Search Indexes.",
                "example": "Use for typos/misspellings in Spanner using SEARCH_NGRAMS.",
                "sql_template": (
                    "SELECT CAST(T.`{column}` AS STRING) AS value, '{column}' AS `columns`, "
                    "'{concept_type}' AS concept_type, "
                    "1 - SCORE_NGRAMS(T.`{column_tokens}`, CAST($value AS STRING)) AS distance, "
                    "JSON '{{}}' AS context "
                    "FROM `{table}` AS T "
                    "WHERE SEARCH_NGRAMS(T.`{column_tokens}`, CAST($value AS STRING)) "
                ),
            },
        },
        "overrides": {}
    },
    Dialect.MYSQL: {
        "min_version": "8",
        "defaults": {
            "EXACT_MATCH_STRINGS": {
                "description": "Exact match for strings in MySQL.",
                "example": "Use for exact matching in MySQL.",
                "sql_template": (
                    "SELECT $value AS value, '{column}' AS `columns`, "
                    "'{concept_type}' AS concept_type, 0 AS distance, "
                    "JSON_OBJECT() AS context "
                    "FROM `{table}` AS T WHERE T.`{column}` = $value"
                ),
            },
            "TRIGRAM_STRING_MATCH": {
                "description": "Trigram fuzzy match in MySQL using FULLTEXT index with score normalization.",
                "example": "Use for fuzzy matching in MySQL (requires FULLTEXT index with ngram).",
                "sql_template": (
                    "SELECT * FROM ("
                    "  WITH TrigramMetrics AS ("
                    "    SELECT T.`{column}` AS original_value, "
                    "    MATCH(T.`{column}`) AGAINST($value IN NATURAL LANGUAGE MODE) AS raw_score "
                    "    FROM `{table}` AS T "
                    "    WHERE MATCH(T.`{column}`) AGAINST($value IN NATURAL LANGUAGE MODE) > 0 "
                    "    ORDER BY raw_score DESC LIMIT 10"
                    "  ), "
                    "  NormalizationParams AS ("
                    "    SELECT MAX(raw_score) AS max_score "
                    "    FROM TrigramMetrics"
                    "  ) "
                    "  SELECT original_value AS value, '{column}' AS `columns`, "
                    "  '{concept_type}' AS concept_type, "
                    "  (CASE WHEN n.max_score > 0 THEN (1 - (m.raw_score / n.max_score)) ELSE 0 END) AS distance, "
                    "  JSON_OBJECT() AS context "
                    "  FROM TrigramMetrics m, NormalizationParams n"
                    ") AS wrapped_query "
                ),
            },
            "SEMANTIC_STRING_MATCH": {
                "description": "Semantic match in MySQL using Vertex AI embedding.",
                "example": "Use for semantic matching (requires mysql.ml_embedding).",
                "sql_template": (
                    "SELECT * FROM ("
                    "  WITH search_embedding AS ("
                    "    SELECT mysql.ml_embedding('text-embedding-005', $value) AS val"
                    "  ) "
                    "  SELECT T.`{column}` AS value, '{column}' AS `columns`, "
                    "  '{concept_type}' AS concept_type, "
                    "  COSINE_DISTANCE(T.`{column_embedding}`, search_embedding.val) AS distance, "
                    "  JSON_OBJECT() AS context "
                    "  FROM `{table}` AS T, search_embedding "
                    "  WHERE T.`{column_embedding}` IS NOT NULL"
                    ") AS wrapped_query "
                ),
            },
        },
        "overrides": {}
    }
}

def _is_version_supported(version: str, min_version: str) -> bool:
    """Helper to compare version strings (e.g. '13.2' >= '13')."""
    def parse(v: str):
        return tuple(map(int, v.split('.')))
    
    try:
        return parse(version) >= parse(min_version)
    except ValueError:
        return False


def get_match_template(
    dialect: str, function_name: str, version: str | None = None
) -> dict:
    """
    Retrieves a match template with a default-fallback strategy.

    Args:
        dialect: The database dialect string (e.g., 'postgresql').
        function_name: The name of the match function.
        version: The specific database version (optional).

    Returns:
        A dictionary containing the template definition.

    Raises:
        ValueError: 
            - If dialect is invalid.
            - If version is provided but unsupported.
            - If function_name is not found (lists available templates).
    """
    try:
        dialect_enum = Dialect(dialect.lower())
    except ValueError:
        supported = [d.value for d in Dialect]
        raise ValueError(
            f"Dialect '{dialect}' not supported. Supported dialects: {supported}"
        )

    engine_config = _MATCH_CONFIG.get(dialect_enum)
    if not engine_config:
        raise ValueError(f"Dialect '{dialect}' has no configuration registered.")

    defaults = engine_config.get("defaults", {})
    min_version = engine_config.get("min_version")
    overrides = engine_config.get("overrides", {})

    if version and min_version:
        version = str(version)
        if not _is_version_supported(version, min_version):
            raise ValueError(
                f"Version '{version}' is not supported for dialect '{dialect}'. "
                f"Minimum required version: {min_version}"
            )

    # Identify specific overrides for this version (if any)
    # Note: Overrides currently use exact version matches in the keys
    version_overrides = overrides.get(version, {}) if version else {}

    effective_templates = defaults | version_overrides
    template = effective_templates.get(function_name)

    if not template:
        supported_templates = list(defaults.keys())
        raise ValueError(
            f"Match function '{function_name}' not found. "
            f"Supported match templates: {supported_templates}"
        )

    return template

def get_available_functions(dialect: str, version: str | None = None) -> Dict[str, Dict[str, str]]:
    """
    Returns a dictionary of available match function names with their descriptions and examples for a given dialect.
    Validates both the dialect and the version (if provided).
    """
    try:
        dialect_enum = Dialect(dialect.lower())
    except ValueError:
        supported = [d.value for d in Dialect]
        raise ValueError(
            f"Dialect '{dialect}' not supported. Supported engine: {supported}"
        )

    engine_config = _MATCH_CONFIG.get(dialect_enum, {})
    
    if version:
        min_version = engine_config.get("min_version")
        version = str(version)
        if min_version and not _is_version_supported(version, min_version):
            raise ValueError(
                f"Version '{version}' is not supported for dialect '{dialect}'. "
                f"Minimum required version: {min_version}"
            )

    defaults = engine_config.get("defaults", {})
    version_overrides = engine_config.get("overrides", {}).get(version, {}) if version else {}
    effective_templates = defaults | version_overrides
    
    return {
        k: {
            "description": v.get("description", ""),
            "example": v.get("example", "")
        }
        for k, v in effective_templates.items()
    }
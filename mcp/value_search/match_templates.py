from typing import Dict, Any, Optional, List
from enum import Enum


class Dialect(str, Enum):
    """Supported database dialects."""
    POSTGRESQL = "postgresql"


_MATCH_CONFIG: Dict[Dialect, Dict[str, Any]] = {
    Dialect.POSTGRESQL: {
        "supported_versions": ["13", "14", "15", "16"],
        
        # Default templates
        "defaults": {
            "EXACT_MATCH_STRINGS": {
                "description": "Exact match (Standard SQL)",
                "sql_template": (
                    "SELECT $value as value, '{table}.{column}' as columns, "
                    "'{concept_type}' as concept_type, 0 as distance, "
                    "'' as context FROM {table} T WHERE T.{column} = $value LIMIT 1"
                ),
            },
            "FUZZY_MATCH_STRINGS": {
                "description": "Fuzzy match using standard levenshtein",
                "sql_template": (
                    "SELECT T.{column} as value, '{table}.{column}' as columns, "
                    "'{concept_type}' as concept_type, levenshtein(T.{column}, $value) as distance, "
                    "'' as context FROM {table} T ORDER BY distance LIMIT 10"
                ),
            },
        },
        
        # Specific overrides per version
        # Format:
        #   "version_string": {
        #       "FUNCTION_NAME": { ... complete template definition ... }
        #   }
        "overrides": {
            # Add override here. 
        }
    },
}


def get_match_template(
    dialect: str, function_name: str, version: Optional[str] = None
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
    supported_versions = engine_config.get("supported_versions", [])
    overrides = engine_config.get("overrides", {})

    if version:
        version = str(version)
        if version not in supported_versions:
            raise ValueError(
                f"Version '{version}' is not supported for dialect '{dialect}'. "
                f"Supported versions: {supported_versions}"
            )

    template = None

    if version and version in overrides:
        template = overrides[version].get(function_name)

    # Fallback to default if no override was found
    if not template:
        template = defaults.get(function_name)

    if not template:
        supported_templates = list(defaults.keys())
        raise ValueError(
            f"Match function '{function_name}' not found. "
            f"Supported match templates: {supported_templates}"
        )

    return template

def get_available_functions(dialect: str) -> List[str]:
    """
    Returns a list of available match function names for a given dialect.
    """
    try:
        dialect_enum = Dialect(dialect.lower())
    except ValueError:
        return []

    engine_config = _MATCH_CONFIG.get(dialect_enum, {})
    defaults = engine_config.get("defaults", {})
    
    # Return list of keys (function names)
    return list(defaults.keys())
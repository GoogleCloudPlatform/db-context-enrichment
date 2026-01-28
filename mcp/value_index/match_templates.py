from typing import Dict, Any, Optional
from enum import Enum


class Dialect(str, Enum):
    """Supported database dialects."""
    POSTGRESQL = "postgresql"

DEFAULT_VERSIONS: Dict[Dialect, str] = {
    Dialect.POSTGRESQL: "16",
}

MATCH_TEMPLATES: Dict[Dialect, Dict[str, Dict[str, Any]]] = {
    Dialect.POSTGRESQL: {
        "16": {
            "EXACT_MATCH_STRINGS": {
                "description": "Exact match (Standard SQL)",
                "sql_template": (
                    "SELECT $value as value, '{table}.{column}' as columns, "
                    "'{concept_type}' as concept_type, 0 as distance, "
                    "'' as context FROM {table} T WHERE T.{column} = $value LIMIT 1"
                ),
            },
            "FUZZY_MATCH_STRINGS": {
                "description": "Fuzzy match using standard levenshtein (requires fuzzystrmatch extension)",
                "sql_template": (
                    "SELECT T.{column} as value, '{table}.{column}' as columns, "
                    "'{concept_type}' as concept_type, levenshtein(T.{column}, $value) as distance, "
                    "'' as context FROM {table} T ORDER BY distance LIMIT 10"
                ),
            },
        }
    },
}


def get_match_template(
    dialect: str, function_name: str, version: Optional[str] = None
) -> dict:
    """
    Retrieves a specific match template using a strict version lookup strategy.

    Args:
        dialect: The database dialect string (e.g., 'postgresql').
        function_name: The name of the match function (e.g., 'EXACT_MATCH_STRINGS').
        version: The specific database version. If None/Empty, uses 'default'.

    Returns:
        A dictionary containing the template definition.

    Raises:
        ValueError: If dialect, version, or function is not found.
    """
    try:
        dialect_enum = Dialect(dialect.lower())
    except ValueError:
        supported = [d.value for d in Dialect]
        raise ValueError(
            f"Dialect '{dialect}' not supported. Supported dialects: {supported}"
        )

    engine_config = MATCH_TEMPLATES.get(dialect_enum)

    if not engine_config:
        raise ValueError(f"Dialect '{dialect}' has no templates registered.")
    
    # If version is None or empty string, treat as "default"
    if not version:
        version = "default"

    if version.lower() == "default":
        target_version_key = DEFAULT_VERSIONS.get(dialect_enum)
        if not target_version_key:
            raise ValueError(
                f"Configuration Error: No default version defined for dialect '{dialect}'."
            )
    else:
        target_version_key = version

    version_config = engine_config.get(target_version_key)

    if not version_config:
        available = list(engine_config.keys())
        raise ValueError(
            f"Version '{target_version_key}' not found for dialect '{dialect}'. "
            f"Available versions: {available}"
        )

    template = version_config.get(function_name)
    if not template:
        raise ValueError(
            f"Match function '{function_name}' not found for {dialect} "
            f"(version: {target_version_key})."
        )

    return template
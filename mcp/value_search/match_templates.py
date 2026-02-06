from typing import Dict, Any, List
from enum import Enum


class Dialect(str, Enum):
    """Supported database dialects."""
    POSTGRESQL = "postgresql"


_MATCH_CONFIG: Dict[Dialect, Dict[str, Any]] = {
    Dialect.POSTGRESQL: {
        "min_version": "13",
        
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

def get_available_functions(dialect: str, version: str | None = None) -> List[str]:
    """
    Returns a list of available match function names for a given dialect.
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
    return list(defaults.keys())
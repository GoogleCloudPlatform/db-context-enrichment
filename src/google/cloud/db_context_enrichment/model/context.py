from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _BaseContextModel(BaseModel):
    """Shared base for all ContextSet models.

    Accepts both snake_case field names and their camelCase aliases on
    validation — needed because the Context Store API returns camelCase for
    proto-known fields on download. Serialization stays snake_case by default
    (Pydantic's `by_alias` defaults to False), so upload output is unchanged.
    """

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class ParameterizedTemplate(_BaseContextModel):
    """Defines the parameterized version of a SQL query and intent."""

    parameterized_sql: str = Field(
        ..., description="The SQL query with placeholders (eg., )."
    )
    parameterized_intent: str = Field(
        ..., description="The natural language intent with placeholders."
    )


class Template(_BaseContextModel):
    """Represents a single, complete template."""

    nl_query: str = Field(
        ..., description="A natural language question about the data."
    )
    sql: str = Field(..., description="The corresponding, complete SQL query.")
    intent: str = Field(..., description="The user's specific intent.")
    manifest: str = Field(
        ..., description="A general description of what the template does."
    )
    parameterized: ParameterizedTemplate


class ParameterizedFacet(_BaseContextModel):
    """Defines the parameterized version of a SQL facet and intent."""

    parameterized_sql_snippet: str = Field(
        ...,
        description="The SQL facet with placeholders (eg., ).",
        # "fragment" is deprecated, keep alias for backward compatibility.
        # camelCase form is listed explicitly because validation_alias
        # overrides the model-level alias_generator.
        validation_alias=AliasChoices(
            "parameterized_sql_snippet",
            "parameterizedSqlSnippet",
            "parameterized_fragment",
        ),
    )
    parameterized_intent: str = Field(
        ..., description="The natural language intent with placeholders."
    )


class Facet(_BaseContextModel):
    """Represents a single, complete facet."""

    sql_snippet: str = Field(
        ...,
        description="The corresponding, complete SQL facet.",
        # "fragment" is deprecated, keep alias for backward compatibility.
        # camelCase form is listed explicitly because validation_alias
        # overrides the model-level alias_generator.
        validation_alias=AliasChoices("sql_snippet", "sqlSnippet", "fragment"),
    )
    intent: str = Field(..., description="The user's specific intent.")
    manifest: str = Field(
        ..., description="A general description of what the facet does."
    )
    parameterized: ParameterizedFacet


class ValueSearch(_BaseContextModel):
    """Represents a single, complete value search."""

    query: str = Field(..., description="The parameterized SQL query (using $value).")
    concept_type: str = Field(
        ..., description="The semantic type (e.g., 'City', 'Product ID')."
    )
    description: str | None = Field(None, description="Optional description.")


class ContextSet(_BaseContextModel):
    """A set of templates, facets and value searches."""

    templates: list[Template] | None = Field(
        None, description="A list of complete templates."
    )
    facets: list[Facet] | None = Field(
        None,
        description="A list of SQL facets.",
        # "fragments" is deprecated, keep alias for backward compatibility.
        # No camelCase entry needed — to_camel("facets") == "facets".
        validation_alias=AliasChoices("facets", "fragments"),
    )
    value_searches: list[ValueSearch] | None = Field(
        None,
        description="A list of value searches.",
    )

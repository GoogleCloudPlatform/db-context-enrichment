from pydantic import AliasChoices, BaseModel, Field
from typing import List


class ParameterizedTemplate(BaseModel):
    """Defines the parameterized version of a SQL query and intent."""

    parameterized_sql: str = Field(
        ..., description="The SQL query with placeholders (eg., )."
    )
    parameterized_intent: str = Field(
        ..., description="The natural language intent with placeholders."
    )


class Template(BaseModel):
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


class ParameterizedFacet(BaseModel):
    """Defines the parameterized version of a SQL facet and intent."""

    parameterized_sql_snippet: str = Field(
        ...,
        description="The SQL facet with placeholders (eg., ).",
        validation_alias=AliasChoices(
            "parameterized_sql_snippet", "parameterized_fragment"
        ),
    )
    parameterized_intent: str = Field(
        ..., description="The natural language intent with placeholders."
    )


class Facet(BaseModel):
    """Represents a single, complete facet."""

    sql_snippet: str = Field(
        ...,
        description="The corresponding, complete SQL facet.",
        validation_alias=AliasChoices("sql_snippet", "fragment"),
    )
    intent: str = Field(..., description="The user's specific intent.")
    manifest: str = Field(
        ..., description="A general description of what the facet does."
    )
    parameterized: ParameterizedFacet


class ContextSet(BaseModel):
    """A set of templates and facets."""

    templates: List[Template] | None = Field(
        None, description="A list of complete templates."
    )
    facets: List[Facet] | None = Field(
        None,
        description="A list of SQL facets.",
        validation_alias=AliasChoices("facets", "fragments"),
    )

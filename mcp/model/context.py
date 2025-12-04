from pydantic import BaseModel, Field
from typing import List, Optional


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


class ParameterizedFragment(BaseModel):
    """Defines the parameterized version of a SQL fragment and intent."""

    parameterized_fragment: str = Field(
        ..., description="The SQL fragment with placeholders (eg., )."
    )
    parameterized_intent: str = Field(
        ..., description="The natural language intent with placeholders."
    )


class Fragment(BaseModel):
    """Represents a single, complete fragment."""

    fragment: str = Field(..., description="The corresponding, complete SQL fragment.")
    intent: str = Field(..., description="The user's specific intent.")
    manifest: str = Field(
        ..., description="A general description of what the fragment does."
    )
    parameterized: ParameterizedFragment


class ContextSet(BaseModel):
    """A set of templates and fragments."""

    templates: Optional[List[Template]] = Field(None, description="A list of complete templates.")
    fragments: Optional[List[Fragment]] = Field(None, description="A list of SQL fragments.")


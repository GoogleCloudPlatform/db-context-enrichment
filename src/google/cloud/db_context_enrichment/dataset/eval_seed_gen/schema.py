import textwrap
from typing import Any
import json

from pydantic import BaseModel, Field

from .generator_base import GeneratorBase


def truncate_length(s: str, max_length: int) -> str:
  """Truncate the string to the maximum length."""
  if not isinstance(s, str):
    return s
  if len(s) > max_length:
    return s[: max_length - 3] + "..."
  return s


class Column(BaseModel):
  name: str
  data_type: str
  is_primary_key: bool
  is_foreign_key: bool


class SchemaDDL(BaseModel):
  """Schema for a database table."""

  ddl: str = ''
  schema_name: str = ''
  table_name: str = ''
  full_table_name: str = ''
  columns: list[Column] = []
  constraints: list[dict[str, Any]] = []
  indexes: list[dict[str, Any]] = []
  error: str = ''

  def get_table_name(self) -> str:
    """Returns the table name."""
    if self.schema_name and self.schema_name != 'public':
      return f'{self.schema_name}.{self.table_name}'
    return self.table_name
  

class TableProfile(BaseModel):
  """Schema profile for a database table."""

  table_name: str
  ddl: str
  columns: list[str]
  sample_data: list[dict[str, Any]]
  sample_values_per_column: dict[str, list[Any]]

  def to_string(self):
    profile = []
    profile.append(f"--- Table: {self.table_name} ---")
    profile.append(f"DDL:\n{self.ddl}")
    profile.append("\n")

    # remove columns with one unique value or less
    filtered_columns = []
    for column in self.columns:
      if self.sample_values_per_column:
        values = self.sample_values_per_column.get(column, [])
        if len(values) > 1:
          filtered_columns.append(column)
      else:
        filtered_columns.append(column)

    if self.sample_data:
      profile.append(f"Sample Data (Columns: {', '.join(filtered_columns)}):")
      for row in self.sample_data:
        new_row = {
            k: truncate_length(v, 32 * 5)
            for k, v in row.items()
            if k in filtered_columns
        }
        profile.append(str(new_row))
      profile.append("\n")

    if self.sample_values_per_column:
      for column, values in self.sample_values_per_column.items():
        if column not in filtered_columns:
          continue
        values = [truncate_length(v, 32 * 5) for v in values]
        profile.append(f'Sample values for column "{column}": {values}')
    return "\n".join(profile)
  

class SchemaProfile(BaseModel):
  """Schema profile for a database."""

  table_profiles: list[TableProfile]
  general_context: str | None = None

  def to_string(self):
    profile = []
    for table_profile in self.table_profiles:
      profile.append(table_profile.to_string())
      profile.append("\n")
    if self.general_context:
      profile.append("--- General Context ---")
      profile.append(truncate_length(self.general_context, 768 * 5))
    return "\n".join(profile)
  

def generate_ddls_from_json_schema(schema_json_string: str) -> list[SchemaDDL]:
  try:
    schema_data_list = json.loads(schema_json_string)
  except json.JSONDecodeError as e:
    return SchemaDDL(error=f'Error decoding JSON: {e}')
  assert isinstance(schema_data_list, list)
  ddls = []
  for schema_data in schema_data_list:
    ddl = generate_ddl_from_dict(schema_data)
    if ddl.error:
      raise ValueError(f'Error generating DDL: {ddl.error}')
    ddls.append(ddl)
  return ddls


def generate_ddl_from_dict(schema_data: dict[str, Any]) -> SchemaDDL:
  """Converts a JSON schema definition string into DDL statements.

  Args:
      schema_json_string: A JSON string representing the database object schema.

  Returns:
      A SchemaDdl object containing the generated DDL statements.
  """

  if 'object_details' not in schema_data:
    return SchemaDDL(error="Error: 'object_details' not found in JSON schema.")

  details = schema_data['object_details']
  schema_name = schema_data.get('schema_name', 'public')
  table_name = details.get('object_name')

  if not table_name:
    return SchemaDDL(error='Error: "object_name" not found in object_details.')

  full_table_name = f'{schema_name}.{table_name}'

  ddl_statements = []

  # 1. CREATE TABLE statement
  columns = details.get('columns', [])
  if not columns:
    return SchemaDDL(
        error='Error: No columns defined for table {full_table_name}.'
    )

  column_defs = []
  for col in columns:
    col_name = col.get('column_name')
    data_type = col.get('data_type')
    if not col_name or not data_type:
      return SchemaDDL(
          error=(
              'Error: Column name or data_type missing in column definition:'
              f' {col}'
          )
      )

    parts = [f'"{col_name}"', data_type]
    if col.get('is_not_nullable', False):
      parts.append('NOT NULL')
    if col.get('column_default') is not None:
      parts.append(f"DEFAULT {col['column_default']}")
    column_defs.append(' '.join(parts))

  create_table_sql = f'CREATE TABLE {full_table_name} (\n  '
  create_table_sql += ',\n  '.join(column_defs)
  create_table_sql += '\n);'
  ddl_statements.append(create_table_sql)
  ddl_statements.append('')

  # 2. Add Constraints
  constraints = details.get('constraints', [])
  pk_constraints = [
      c for c in constraints if c.get('constraint_type') == 'PRIMARY KEY'
  ]
  fk_constraints = [
      c for c in constraints if c.get('constraint_type') == 'FOREIGN KEY'
  ]
  other_constraints = [
      c
      for c in constraints
      if c.get('constraint_type') not in ['PRIMARY KEY', 'FOREIGN KEY']
  ]

  def add_constraint_sql(constraint):
    constraint_name = constraint.get('constraint_name')
    constraint_def = constraint.get('constraint_definition')
    if constraint_name and constraint_def:
      return (
          f'ALTER TABLE {full_table_name} ADD CONSTRAINT "{constraint_name}"'
          f' {constraint_def};'
      )
    return None
  
  primary_keys = set()
  foreign_keys = set()

  # Add Primary Key and other non-FK constraints
  for c in pk_constraints:
    sql = add_constraint_sql(c)
    if sql:
      ddl_statements.append(sql)
      constraint_definition = c.get('constraint_definition')
      pk_candidates = []
      for col in columns:
        column_name = col.get('column_name')
        if column_name in constraint_definition:
          pk_candidates.append(column_name)
      if pk_candidates:
        selected_pk = list(sorted(pk_candidates, key=len, reverse=True))[0]
        primary_keys.add(selected_pk)


  for c in other_constraints:
    sql = add_constraint_sql(c)
    if sql:
      ddl_statements.append(sql)

  if pk_constraints or other_constraints:
    ddl_statements.append('')

  # Add Foreign Key constraints last
  for c in fk_constraints:
    sql = add_constraint_sql(c)
    if sql:
      ddl_statements.append(sql)
      constraint_definition = c.get('constraint_definition')
      fk_candidates = []
      for col in columns:
        column_name = col.get('column_name')
        if column_name in constraint_definition:
          fk_candidates.append(column_name)
      if fk_candidates:
        selected_fk = list(sorted(fk_candidates, key=len, reverse=True))[0]
        foreign_keys.add(selected_fk)

  if fk_constraints:
    ddl_statements.append('')

  # 3. Add Indexes
  indexes = details.get('indexes', [])
  for index in indexes:
    index_def = index.get('index_definition')
    # Primary key constraints typically create their own unique index.
    # Avoid duplicating index creation if it's for the primary key.
    if not index.get('is_primary', False) and index_def:
      # Ensure the index definition also uses quoted table name if needed
      # Assuming index_definition is already correctly formatted.
      ddl_statements.append(index_def + ';')

  ddl = '\n'.join(ddl_statements)
  return SchemaDDL(
      ddl=ddl,
      schema_name=schema_name,
      table_name=table_name,
      full_table_name=full_table_name,
      columns=[Column(
        name=col.get('column_name'),
        data_type=col.get('data_type'),
        is_primary_key=col.get('column_name') in primary_keys,
        is_foreign_key=col.get('column_name') in foreign_keys,
      ) for col in columns],
      constraints=constraints,
      indexes=indexes,
  )

class TableSelector(GeneratorBase):
  async def select_tables(
      self,
      *,
      tables: list[SchemaDDL],
      top_k: int = 8
  ) -> list[str]:
    
    class SelectedTables(BaseModel):
      table_names: list[str] = Field(description="List of selected table names, Each table name in the form of schema_name.table_name")

    profile = []
    for table in tables:
      profile.append(f"--- Table: {table.full_table_name} ---")
      profile.append(f"DDL:\n{table.ddl}")
      profile.append("\n")
    schema_profile = '\n'.join(profile)
    
    review_prompt = textwrap.dedent(f"""
    You are experienced Database Analyst. You are given the schema of a database, and ask the pick at most {top_k} tables that
    the end-user will most likely interact with.
    
    Below are some guidelines for picking the relevant tables (P0, P1, P2 refers to priority, which P0 being highest priority):
    - P0: central tables in the schema.
    - P1: tables whose primary keys are most frequently referenced in other tables's foreign keys. 
    - P2: tables which appear to be relevant for answering user questions in the application domain.

    Guildelines:
    - When the two tables relevant, it means the two table are linked by reference or in the same application domain or under the same schema.
    - You must not pick tables about schema information or table schema unless they are relevant to the application domain.
    - After you pick the top 1 table, the other tables that you select must either have the same schema as the top 1 table or relevant to the top 1 table.
    - Ensure that the tables selected are relevant to each other.
    
    You should return the full table names (in the form of schema_name.table_name).
    You should return AT MOST {top_k} tables.
    
    Database schema:
    {schema_profile}
    """)

    report = await self.generate_content(
        prompt=review_prompt,
        response_schema=SelectedTables,
        temperature=0.1,
    )
    assert report is not None
    assert isinstance(report, SelectedTables)
    return report.table_names



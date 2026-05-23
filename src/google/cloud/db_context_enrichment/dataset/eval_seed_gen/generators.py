import random
import textwrap

from pydantic import BaseModel, Field
from .generator_base import GeneratorBase


class GeneratedQuery(BaseModel):
  """A generated SQL query or question."""

  text: str
  gen_id: str


class GeneratedSQLPool(BaseModel):
  """A list of generated SQL queries."""

  sqls: list[str] = Field(
      description="A list of distinct SQL queries based on the schema."
  )


class TranslatedQuestion(BaseModel):
  question: str = Field(
      description=(
          "A natural, realistic, unambigious business question that the SQL query answers."
      )
  )

class QuestionReviewReport(BaseModel):
  """The Reviewer Agent's assessment of a NL2SQL pair."""

  is_golden: bool = Field(
      description=(
          "True if the question is perfectly aligned with the original SQL"
          " intent."
      )
  )
  red_flags: list[str] = Field(
      description="List of issues: ambiguity, logical errors."
  )
  ambiguity_score: float = Field(
      description="0.0 (Clear) to 1.0 (Highly Ambiguous)."
  )
  intent_mismatch: bool = Field(
      description=(
          "True if the NL question doesn't match the original SQL intent."
      )
  )
  improvement_suggestion: str = Field(
      description="Specific advice for the Repair Agent."
  )
  summary: str = Field(
    description="Concise and short summary of the assessment."
  )


class SQLCandidateGenerator(GeneratorBase):
  """SQL generator for NL2SQL Eval Dataset Generation."""

  async def generate_candidates(
      self, schema_profile: str, dialect: str, complexity: str, count: int
  ) -> list[GeneratedQuery]:
    """Architect Agent: Generates candidate SQL queries (SQL2NL strategy)."""
    strategy_id = random.randint(1, 4)
    if strategy_id == 1:
      sqls = await self._generate_candidates_1(
        schema_profile=schema_profile, 
        dialect=dialect,
        complexity=complexity,
        count=count)
    elif strategy_id == 2:
      sqls = await self._generate_candidates_2(
        schema_profile=schema_profile, 
        dialect=dialect,
        complexity=complexity,
        count=count
      )
    elif strategy_id == 3:
      sqls = await self.generate_candidates_3(
        schema_profile=schema_profile, 
        dialect=dialect,
        complexity=complexity,
        count=count
      )
    else:
      sqls = await self.generate_candidates_4(
        schema_profile=schema_profile, 
        dialect=dialect,
        complexity=complexity,
        count=count
      )

    sqls = [sql for sql in sqls if sql and 20 <= len(sql) <= 300]

    sqls = list(set(sqls))
    
    return [GeneratedQuery(text=sql, gen_id=str(strategy_id)) for sql in sqls]
    
  async def _generate_candidates_1(
      self, *, schema_profile: str, dialect: str, complexity: str, count: int
  ) -> list[str]:
    prompt = textwrap.dedent(f"""
      You are an expert Database Architect. Given the following {dialect} database schema and sample data, 
      generate {count} {complexity}, diverse, highly realistic analytical SQL queries. 
      
      Include a mix of:
      - Simple SELECTs and aggregates
      - Multi-table JOINs
      - Subqueries and CTEs
      - Window functions (if applicable)
      
      Ensure the queries are syntactically valid for {dialect} and are likely to return data based on the samples.
      Ensure the queries are concise and each query is less than 300 characters.

      Below is the definition on SQL query complexity:
      - easy: Involves single-table selections and basic relational filtering.
      - medium: Requires multi-table joins, foundational data aggregations.
      - hard: Demands deeply nested subqueries, complex window functions, or strict edge-case syntax constraints.
      
      Database Profile:
      {schema_profile}
      """)

    candidates = await self.generate_content(
        prompt=prompt,
        response_schema=GeneratedSQLPool,
        temperature=0.7,
    )
    return candidates.sqls if candidates else []
  
  async def _generate_candidates_2(
      self,
      *,
      schema_profile: str,
      dialect: str,
      complexity: str,
      count: int
  ) -> list[str]:
    """Architect Agent: Generates candidate SQL queries (SQL2NL strategy)."""
    sql_gen_prompt = textwrap.dedent(f"""
    Generate {count} {complexity}, diverse, highly realistic, {dialect} SQL queries. 
    Inject real-world messiness: Use CTEs, window functions, or regex/string extraction if appropriate.
    Ensure each query returns actual data from the samples provided.
    Ensure the queries are concise and each query is less than 300 characters.

    Below is the definition on SQL query complexity:
    - easy: Involves single-table selections and basic relational filtering.
    - medium: Requires multi-table joins, foundational data aggregations.
    - hard: Demands deeply nested subqueries, complex window functions, or strict edge-case syntax constraints.
    
    Database Profile:
    {schema_profile}
    """)
    candidates = await self.generate_content(
        prompt=sql_gen_prompt,
        response_schema=GeneratedSQLPool,
        temperature=0.7,
    )
    return candidates.sqls if candidates else []

  async def generate_candidates_3(
      self, 
      *,
      schema_profile: str, 
      dialect: str,
      complexity: str,
      count: int
  ) -> list[str]:
    """Generates a candidate NL2SQL pair using the RepairedPair schema."""
    prompt = textwrap.dedent(f"""
      Generate {count} {complexity}, diverse, highly realistic, {dialect} SQL queries. 
      Think step-by-step: 
      - First generate {count} distinct, realistic business intents that users of this database might have. 
      - For each intent, generate a corresponding SQL query that would answer that intent.

      Ensure the queries are syntactically valid for {dialect} and are likely to return data based on the samples.
      Ensure the queries are concise and each query is less than 300 characters.

      Below is the definition on SQL query complexity:
      - easy: Involves single-table selections and basic relational filtering.
      - medium: Requires multi-table joins, foundational data aggregations.
      - hard: Demands deeply nested subqueries, complex window functions, or strict edge-case syntax constraints.
      
      Database Profile: 
      {schema_profile}
      """)
    candidates = await self.generate_content(
        prompt=prompt,
        response_schema=GeneratedSQLPool,
        temperature=0.7,
    )
    return candidates.sqls if candidates else []
  
  async def generate_candidates_4(
      self, 
      *,
      schema_profile: str, 
      dialect: str,
      complexity: str,
      count: int
  ) -> list[str]:


    dev_prompt = textwrap.dedent(f"""
    Generate {count} {complexity}, diverse, highly realistic, {dialect} SQL queries. 
    Think step-by-step:
    - First, plan {count} {complexity} {dialect} SQL pattern for this database describing the tables, joins and the analytical goal. Focus on messy real-world scenarios.
    - Next, generate {count} {complexity}, diverse, highly realistic, {dialect} queries, one for each SQL design.
    Ensure it return non empty results when executed. Use exact table and column names from the context.
    Ensure the queries are concise and each query is less than 300 characters.
    Ensure you use exact table and column names from the context.

    Below is the definition on SQL query complexity:
    - easy: Involves single-table selections and basic relational filtering.
    - medium: Requires multi-table joins, foundational data aggregations.
    - hard: Demands deeply nested subqueries, complex window functions, or strict edge-case syntax constraints.
    
    Database Profile:
    {schema_profile}
    """)
    candidates = await self.generate_content(
        prompt=dev_prompt, response_schema=GeneratedSQLPool, temperature=0.7
    )
    return candidates.sqls if candidates else []
  

class QuestionGenerator(GeneratorBase):
  """SQL2NL generator for NL2SQL Eval Dataset Generation."""

  async def translate_sql_nl(
      self,
      *,
      schema_profile: str,
      sql: str
  ) -> GeneratedQuery:
    strategy_id = random.randint(1, 2)
    if strategy_id == 1:
      nlq = await self.translate_sql_nl_1(
        schema_profile=schema_profile, 
        sql=sql
      )
    else:
      nlq = await self.translate_sql_nl_2(
        schema_profile=schema_profile, 
        sql=sql
      )
    return GeneratedQuery(text=nlq, gen_id=str(strategy_id))


  async def translate_sql_nl_1(
      self,
      *,
      schema_profile: str,
      sql: str
  ) -> str | None:
    """Translator Agent: Translates valid SQL into a business question."""
    prompt = textwrap.dedent(f"""
      You are a Data Analyst. Look at the following SQL query, the database profile.
      Translate this SQL query into a clear, natural-sounding business question that a CEO or Manager would ask.
      Ensure that the translated question is concise and not vague and not ambiguous.
      Avoid using technical jargon or SQL keywords in the question. 
      The question should be something that a non-technical business stakeholder might ask.
      
      SQL Query:
      {sql}
      
      Database Profile:
      {schema_profile}
      """)

    result = await self.generate_content(
        prompt=prompt,
        response_schema=TranslatedQuestion,
        temperature=0.4,
    )
    return result.question if result else None
  
  async def translate_sql_nl_2(
      self,
      *,
      schema_profile: str,
      sql: str
  ) -> str | None:
    styles = [
            "formal",
            "colloquial",
            "imperative",
            "interrogative",
            "descriptive",
            "concise",
            "vague",
            "metaphorical",
            "conversational",
        ]
    selected_style = random.choice(styles)
    nl_prompt = textwrap.dedent(f"""
    You are a Data Analyst. Look at the following SQL query, the database profile.
    Translate this SQL into a '{selected_style}' natural language question that is not ambiguous.
    Ensure that the translated question is concise and not vague and not ambiguous.
    Avoid using technical jargon or SQL keywords in the question. 
    The question should be something that a non-technical business stakeholder might ask.
    
    SQL Query:
    {sql}
    
    Database Profile:
    {schema_profile}
    """)
    question_data = await self.generate_content(
        prompt=nl_prompt,
        response_schema=TranslatedQuestion,
        temperature=0.8,
    )
    return question_data.question if question_data else None
  

class QuestionReviewer(GeneratorBase):
  """Question reviewer agent for NL2SQL Eval Dataset Generation."""

  async def review_question(
      self,
      *,
      question: str,
      sql: str,
  ) -> QuestionReviewReport | None:
    review_prompt = textwrap.dedent(f"""
    You are the ReViSQL Reviewer Agent. Evaluate this NL2SQL question for inclusion in a Golden Dataset.
    
    NL Question: {question}
    SQL Query: {sql}
    
    Check for:
    1. Ambiguity: Is the NL question too vague?
    2. Logical Correctness: Does the NL question accurately reflect the SQL intent?
    3. Filter Correctness: Does the NL question accurately reflect the filter condition of SQL query?
    4. Join Correctness: Does the NL question accurately reflect the join condition of SQL query?
    5. Output Correctness: Does the NL question accurately reflect the output of SQL query?
    """)

    report = await self.generate_content(
        prompt=review_prompt,
        response_schema=QuestionReviewReport,
        temperature=0.1,
    )
    return report if report else None


class QuestionRefiner(GeneratorBase):
  async def refine_question(
      self,
      *,
      question: str,
      sql: str,
      question_report: QuestionReviewReport | str,
  ) -> str | None:
    """Refiner agent in the Verifier/Refiner Agent Loop.

    Args:
      schema_profile: The database schema and sample data.
      question: The business question to verify.
      sql: The original SQL query that produced the business question.
      sql_dialect: The dialect of the SQL query.

    Returns:
      return verified and refined question
    """

    if isinstance(question_report, QuestionReviewReport):
      question_report = question_report.model_dump_json()


    refine_prompt = textwrap.dedent(f"""
    The current business question is ambiguous and led to an incorrect SQL query.
    
    SQL Query:
    {sql}
    
    Current Ambiguous or Incorrect Question:
    {question}
    
    Reviewer Report:
    {question_report}
    
    Please rewrite the Business Question to be perfectly precise, unambiguous, and aligned with the Intended SQL query.
    Explicitly mention necessary filters or specific columns if needed to avoid ambiguity.
    """)

    refined = await self.generate_content(
        prompt=refine_prompt,
        response_schema=TranslatedQuestion,
        temperature=0.3,
    )
    return refined.question if refined else None


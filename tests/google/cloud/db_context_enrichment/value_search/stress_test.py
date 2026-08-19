import pytest
import string
import random
from google.cloud.db_context_enrichment.value_search.match_templates import get_match_template

def random_string(length=10, alphabet=None):
    if alphabet is None:
        # Include normal letters, digits, and special characters
        alphabet = string.ascii_letters + string.digits + " `'\"/\\{}[]()-+*&^%$#@!~|;:<>,.?"
    return "".join(random.choice(alphabet) for _ in range(length))

def test_stress_btql_template_formatting():
    template = get_match_template(
        dialect="bigtable",
        function_name="EXACT_MATCH_STRINGS"
    )
    sql_template = template["sql_template"]

    # Seed for reproducibility
    random.seed(42)

    for i in range(1000):
        # Generate random inputs of different sizes
        t_len = random.randint(1, 50)
        c_len = random.randint(1, 50)
        ct_len = random.randint(1, 50)

        table = random_string(t_len)
        column = random_string(c_len)
        concept = random_string(ct_len)

        format_args = {
            "table_ident": table,
            "column_ident": column,
            "column_lit": column,
            "concept_type": concept,
        }

        # Verify formatting behaves safely without raising exception
        try:
            formatted_sql = sql_template.format(**format_args)
        except Exception as e:
            pytest.fail(f"Formatting failed on iteration {i} with args {format_args}: {e}")

        # Property checks on generated SQL
        assert "CAST($value AS STRING)" in formatted_sql
        assert f"'{column}' AS `columns`" in formatted_sql
        assert f"'{concept}' AS concept_type" in formatted_sql
        assert "0 AS distance" in formatted_sql
        assert "'' AS context" in formatted_sql
        assert f"FROM `{table}` AS T" in formatted_sql

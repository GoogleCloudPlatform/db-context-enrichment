from google.cloud.db_context_enrichment.common import config


def test_get_model_name():
    assert config.get_model_name() == "gemini-3.1-flash-lite"

from common import config

def test_get_model_name():
    assert config.get_model_name() == "gemini-2.5-flash"

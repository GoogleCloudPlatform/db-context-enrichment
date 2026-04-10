MODEL_NAME = "gemini-2.5-pro"

def get_model_name() -> str:
    """Returns the configured model name.
    
    Centralized in this file to make it easy to update.
    Requires rebuilding the binary to take effect.
    """
    return MODEL_NAME

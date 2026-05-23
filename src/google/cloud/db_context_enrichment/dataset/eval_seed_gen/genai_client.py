"""GenAI client for NL2SQL Eval Dataset Generator."""

import os
import asyncio

from google import genai
from google.genai import types
from google.genai.errors import APIError
import pydantic

BaseModel = pydantic.BaseModel

RETRYABLE_STATUS_CODES = [408, 429, 500, 502, 503, 504]
RETRYABLE_ATTEMPTS = 3 # can be set to 5 but we want to reduce it for faster failure in case of issues

class GenAiClient:
  """GenAI client for NL2SQL Eval Dataset Generator."""

  def __init__(self, timeout_secs: int = 60):
    # Ensure API key is set in environment, or set it here for local testing
    api_key = os.environ.get("GEMINI_API_KEY", "")
    self.timeout_secs = timeout_secs
    assert api_key, "GEMINI_API_KEY is not set in environment variables."
    # http_options=types.HttpOptions(
    #     retry_options=types.HttpRetryOptions(
    #         initial_delay=1.0,
    #         attempts=RETRYABLE_ATTEMPTS,
    #         http_status_codes=RETRYABLE_STATUS_CODES,
    #     ),
    #     timeout=120 * 1000,
    # )
    self._client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
          retry_options=types.HttpRetryOptions(
              attempts=1  # 1 attempt means 0 retries
          ),
          timeout=timeout_secs * 1000,
        )
    )

  @staticmethod
  def is_retryable_genai_error(exception):
    """Return True if it's a rate limit (429) or server error (503)."""
    if isinstance(exception, APIError):
      return exception.code in RETRYABLE_STATUS_CODES
    return False

  async def generate_content_async(
      self,
      *,
      prompt: str,
      model: str,
      response_schema: types.SchemaUnion | None = None,
      response_mime_type: str = "application/json",
      temperature: float = 0.3,
  ) -> types.GenerateContentResponse | None:
    """Generates content using the GenAI model asynchronously."""
    try:
      result = await asyncio.wait_for(self._client.aio.models.generate_content(
          model=model,
          contents=prompt,
          config=types.GenerateContentConfig(
              response_mime_type=response_mime_type,
              response_schema=response_schema,
              temperature=temperature,
          ),
      ), timeout=self.timeout_secs)
      return result
    except Exception as e:
      return None
    

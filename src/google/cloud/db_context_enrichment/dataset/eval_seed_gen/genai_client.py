"""GenAI client for NL2SQL Eval Dataset Generator."""

import asyncio
import logging

import pydantic
from google.genai import types
from google.genai.errors import APIError

from google import genai

BaseModel = pydantic.BaseModel


class GenAiClient:
    """GenAI client for NL2SQL Eval Dataset Generator."""

    def __init__(self, timeout_secs: int = 60):
        self.timeout_secs = timeout_secs
        self._client = genai.Client(
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(
                    attempts=1  # 1 attempt as we need genai to fail fast when throttling happens
                ),
                timeout=timeout_secs * 1000,
            )
        )

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
            result = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type=response_mime_type,
                        response_schema=response_schema,
                        temperature=temperature,
                    ),
                ),
                timeout=self.timeout_secs,
            )
            return result
        except (TimeoutError, APIError) as e:
            logging.warning(
                f"generate_content is not able to complete due to timeout or api error: {e}"
            )
            return None
        except Exception as e:
            logging.warning(f"generate_content was not able to complete due to: {e}")
            return None

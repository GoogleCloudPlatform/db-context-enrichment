from google.genai import types

from .genai_client import GenAiClient


class GeneratorBase:
    """Base class for generators in NL2SQL Eval Dataset Generation."""

    pass

    def __init__(
        self,
        genai_client: GenAiClient,
        generator_model_id: str = "gemini-3-flash-preview",
    ):
        super().__init__()
        self._genai_client = genai_client
        self._generator_model_id = generator_model_id

    async def generate_content(
        self,
        prompt: str,
        response_schema: types.SchemaUnion | None = None,
        response_mime_type: str = "application/json",
        model: str | None = None,
        temperature: float = 0.3,
    ) -> str | types.SchemaUnion | None:
        """Generates content using the GenAI model."""
        if model is None:
            model = self._generator_model_id
        resp = await self._genai_client.generate_content_async(
            prompt=prompt,
            response_schema=response_schema,
            response_mime_type=response_mime_type,
            model=model,
            temperature=temperature,
        )
        if resp is None:
            return None
        if response_schema is not None:
            return response_schema.model_validate_json(resp.text)
        return resp.text

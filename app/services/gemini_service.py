from fastapi import HTTPException
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.core.config import GEMINI_API_KEY, GEMINI_MODEL
from app.schemas.job_application_schema import ParsedResume


class GeminiService:
    def __init__(self, api_key: str | None = GEMINI_API_KEY, model: str = GEMINI_MODEL):
        self.api_key = api_key
        self.model = model

    async def extract_resume_details(self, resume_text: str) -> ParsedResume:
        if not self.api_key:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured")
        if not resume_text.strip():
            raise HTTPException(status_code=400, detail="Resume text is empty")

        return await run_in_threadpool(self._extract_resume_details_sync, resume_text)

    def _extract_resume_details_sync(self, resume_text: str) -> ParsedResume:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise HTTPException(status_code=500, detail="google-genai dependency is not installed") from exc

        client = genai.Client(api_key=self.api_key)
        prompt = self._build_resume_prompt(resume_text)

        try:
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ParsedResume,
                    temperature=0,
                ),
            )
            return ParsedResume.model_validate_json(response.text)
        except ValidationError as exc:
            raise HTTPException(status_code=502, detail="Gemini returned invalid resume JSON") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Gemini resume extraction failed") from exc

    def _build_resume_prompt(self, resume_text: str) -> str:
        return f"""
Extract candidate details from this resume text.

Rules:
- Return only details directly supported by the resume text.
- Do not invent missing fields.
- Use null for missing scalar fields.
- Use empty arrays for missing list fields.
- Keep dates as written in the resume text when exact dates are unclear.
- total_experience_years may be an estimate only when the work history supports it.

Resume text:
{resume_text}
""".strip()

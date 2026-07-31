import json
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.core.config import GEMINI_API_KEY, GEMINI_MODEL
from app.schemas.job_application_schema import CandidateRankingResult, ParsedResume


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

    async def rank_candidate_for_job(self, job: Any, application: Any) -> CandidateRankingResult:
        if not self.api_key:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured")

        prompt = self._build_candidate_ranking_prompt(job, application)
        return await run_in_threadpool(self._rank_candidate_for_job_sync, prompt)

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
            if response.text is None:
                raise HTTPException(status_code=502, detail="Gemini returned an empty response")
            return ParsedResume.model_validate_json(response.text)
        except ValidationError as exc:
            raise HTTPException(status_code=502, detail="Gemini returned invalid resume JSON") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Gemini resume extraction failed") from exc

    def _rank_candidate_for_job_sync(self, prompt: str) -> CandidateRankingResult:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise HTTPException(status_code=500, detail="google-genai dependency is not installed") from exc

        client = genai.Client(api_key=self.api_key)

        try:
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=CandidateRankingResult,
                    temperature=0,
                ),
            )
            if response.text is None:
                raise HTTPException(status_code=502, detail="Gemini returned an empty response")
            return CandidateRankingResult.model_validate_json(response.text)
        except ValidationError as exc:
            raise HTTPException(status_code=502, detail="Gemini returned invalid ranking JSON") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Gemini candidate ranking failed") from exc

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

    def _build_candidate_ranking_prompt(self, job: Any, application: Any) -> str:
        payload = {
            "job": {
                "title": job.title,
                "description": job.description,
                "department": job.department,
                "location": job.location,
                "employment_type": self._enum_value(job.employment_type),
                "workplace_type": self._enum_value(job.workplace_type),
                "experience_level": job.experience_level,
                "requirements": job.requirements,
                "responsibilities": job.responsibilities,
            },
            "candidate": {
                "name": application.candidate_name,
                "location": application.candidate_location,
                "summary": application.summary,
                "cover_letter": application.cover_letter,
                "linkedin_url": application.linkedin_url,
                "portfolio_url": application.portfolio_url,
                "resume_text": application.resume_text,
                "parsed_resume": application.parsed_resume,
            },
        }

        return f"""
Rank this candidate for the job.

Rules:
- Return only JSON matching the response schema.
- Score fit from 0 to 100.
- recommendation must be one of: strong_match, possible_match, not_recommended.
- Base the ranking only on the supplied job and candidate data.
- Do not infer protected traits or use protected traits in the evaluation.
- Prefer job requirements, responsibilities, relevant skills, work history, and experience level.
- Keep rationale under 40 words.
- Provide at most 5 strengths and at most 5 gaps.
- If evidence is missing, reflect that as a gap instead of inventing facts.

Data:
{json.dumps(payload, default=str)}
""".strip()

    def _enum_value(self, value: Any) -> Any:
        return getattr(value, "value", value)

import json
from datetime import UTC, date, datetime
from typing import Any, TypeVar

from fastapi import HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.core.config import XKIRO_API_KEY, XKIRO_BASE_URL, XKIRO_MODEL
from app.schemas.job_application_schema import CandidateRankingResult, ParsedResume

StructuredResult = TypeVar("StructuredResult", bound=BaseModel)


class XkiroService:
    def __init__(
        self,
        api_key: str | None = XKIRO_API_KEY,
        model: str = XKIRO_MODEL,
        base_url: str = XKIRO_BASE_URL,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def extract_resume_details(self, resume_text: str) -> ParsedResume:
        if not resume_text.strip():
            raise HTTPException(status_code=400, detail="Resume text is empty")

        prompt = self._build_resume_prompt(resume_text)
        return await self._structured_completion(
            prompt,
            ParsedResume,
            "resume extraction",
        )

    async def rank_candidate_for_job(
        self,
        job: Any,
        application: Any,
    ) -> CandidateRankingResult:
        prompt = self._build_candidate_ranking_prompt(job, application)
        return await self._structured_completion(
            prompt,
            CandidateRankingResult,
            "candidate ranking",
        )

    async def _structured_completion(
        self,
        prompt: str,
        schema: type[StructuredResult],
        operation: str,
    ) -> StructuredResult:
        client = self._client()
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Xkiro {operation} request failed",
            ) from exc
        finally:
            await client.close()

        if not response.choices or not response.choices[0].message.content:
            raise HTTPException(
                status_code=502,
                detail=f"Xkiro returned an empty {operation} response",
            )

        content = self._strip_json_fence(response.choices[0].message.content)
        try:
            return schema.model_validate_json(content)
        except ValidationError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Xkiro returned invalid {operation} JSON",
            ) from exc

    def _client(self) -> AsyncOpenAI:
        if not self.api_key:
            raise HTTPException(status_code=503, detail="XKIRO_API_KEY is not configured")
        return AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def _build_resume_prompt(self, resume_text: str) -> str:
        schema = json.dumps(ParsedResume.model_json_schema(), separators=(",", ":"))
        reference_date = datetime.now(UTC).date()
        return f"""
Extract candidate details from this resume text.

Rules:
- Return only one JSON object matching the supplied JSON schema.
- Return only details directly supported by the resume text.
- Do not invent missing fields.
- Use null for missing scalar fields.
- Use empty arrays for missing list fields.
- Keep dates as written in the resume text when exact dates are unclear.
- Calculate total_experience_years from all non-overlapping work-experience date ranges.
- Never count education dates toward professional experience.
- Treat Present, Current, Ongoing, and Now as {reference_date.isoformat()}.

JSON schema:
{schema}

Resume text:
{resume_text}
""".strip()

    def _build_candidate_ranking_prompt(
        self,
        job: Any,
        application: Any,
        as_of: date | None = None,
    ) -> str:
        reference_date = as_of or datetime.now(UTC).date()
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
        schema = json.dumps(
            CandidateRankingResult.model_json_schema(),
            separators=(",", ":"),
        )

        return f"""
Rank this candidate for the job.

Current date: {reference_date.isoformat()}.

Rules:
- Return only one JSON object matching the supplied JSON schema.
- Return all five rubric component scores. The final score is their sum and is normalized by the server.
- Award required skills 0-40, relevant work experience 0-30, education 0-10, responsibilities/domain fit 0-15, and application evidence quality 0-5.
- For relevant experience: meeting or exceeding a stated minimum earns 30; about 75% earns 22; about 50% earns 15; scale lower evidence proportionally.
- recommendation thresholds are: strong_match at 80-100, possible_match at 50-79, and not_recommended below 50.
- Base the ranking only on the supplied job and candidate data.
- Do not infer protected traits or use protected traits in the evaluation.
- Prefer job requirements, responsibilities, relevant skills, work history, and experience level.
- Recalculate professional experience from all non-overlapping work_experience date ranges; never use education dates as work experience.
- Use parsed_resume.total_experience_years as the authoritative normalized total when it is present.
- Do not label education as ongoing unless the resume explicitly says Present, Current, or Ongoing, or its end date is after the current date.
- A current-year education end date alone is ambiguous and must not be treated as proof that the degree is incomplete.
- When two otherwise equivalent candidates differ only by additional relevant experience, that additional evidence must not lower the score.
- Keep rationale under 40 words.
- Provide at most 5 strengths and at most 5 gaps.
- If evidence is missing, reflect that as a gap instead of inventing facts.

JSON schema:
{schema}

Data:
{json.dumps(payload, default=str)}
""".strip()

    @staticmethod
    def _strip_json_fence(content: str) -> str:
        stripped = content.strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    @staticmethod
    def _enum_value(value: Any) -> Any:
        return getattr(value, "value", value)

from datetime import date
from types import SimpleNamespace

import pytest

from app.schemas.job_application_schema import (
    CandidateRankingResult,
    ParsedResume,
    ResumeWorkExperience,
)
from app.services.job_application_service import JobApplicationService
from app.services.resume_service import ResumeService
from app.services.xkiro_service import XkiroService
from main import app


def test_combined_work_history_replaces_stale_experience_total():
    parsed_resume = ParsedResume(
        total_experience_years=0.5,
        work_experience=[
            ResumeWorkExperience(
                company="First Company",
                title="Developer",
                start_date="2024-01-01",
                end_date="2024-07-01",
            ),
            ResumeWorkExperience(
                company="Second Company",
                title="Developer",
                start_date="2024-08-01",
                end_date="2025-07-01",
            ),
        ],
    )

    normalized = ResumeService().normalize_parsed_resume(
        parsed_resume,
        as_of=date(2026, 9, 13),
    )

    assert normalized.total_experience_years == 1.4


def test_ranking_prompt_anchors_dates_and_ambiguous_education_status():
    job = SimpleNamespace(
        title="Software Engineer",
        description="Build APIs",
        department="Engineering",
        location="Lahore",
        employment_type="full_time",
        workplace_type="hybrid",
        experience_level="1+ years",
        requirements="Python",
        responsibilities="Build APIs",
    )
    application = SimpleNamespace(
        candidate_name="Zain Ashraf",
        candidate_location="Lahore",
        summary=None,
        cover_letter=None,
        linkedin_url=None,
        portfolio_url=None,
        resume_text="BS 2024 - 2026",
        parsed_resume={
            "total_experience_years": 1.4,
            "education": [
                {
                    "degree": "BS",
                    "start_date": "2024",
                    "end_date": "2026",
                }
            ],
        },
    )

    prompt = XkiroService(api_key="test")._build_candidate_ranking_prompt(
        job,
        application,
        as_of=date(2026, 9, 13),
    )

    assert "2026-09-13" in prompt
    assert "Do not label education as ongoing" in prompt
    assert "must not lower the score" in prompt


def test_authenticated_rerank_route_is_registered():
    matching_routes = [
        route
        for route in app.routes
        if route.path == "/api/jobs/{job_id}/applications/rerank"
    ]

    assert len(matching_routes) == 1
    assert "POST" in matching_routes[0].methods


def test_ranking_total_and_recommendation_are_derived_from_fixed_rubric():
    ranking = CandidateRankingResult(
        score=10,
        skills_score=30,
        experience_score=20,
        education_score=10,
        role_fit_score=10,
        evidence_quality_score=5,
        recommendation="not_recommended",
        rationale="Relevant evidence",
    )

    assert ranking.score == 75
    assert ranking.recommendation == "possible_match"


@pytest.mark.asyncio
async def test_rerank_normalizes_stored_resume_before_calling_provider():
    class RankingProvider:
        async def rank_candidate_for_job(self, _job, application):
            assert application.parsed_resume["total_experience_years"] == 1.4
            return CandidateRankingResult(
                score=75,
                skills_score=30,
                experience_score=20,
                education_score=10,
                role_fit_score=10,
                evidence_quality_score=5,
                recommendation="possible_match",
                rationale="Relevant experience",
            )

    application = SimpleNamespace(
        parsed_resume={
            "total_experience_years": 0.5,
            "work_experience": [
                {
                    "company": "First Company",
                    "title": "Developer",
                    "start_date": "2024-01-01",
                    "end_date": "2024-07-01",
                },
                {
                    "company": "Second Company",
                    "title": "Developer",
                    "start_date": "2024-08-01",
                    "end_date": "2025-07-01",
                },
            ],
        },
        ranking_status=None,
        ranking_error=None,
        ranking_score=None,
        ranking_recommendation=None,
        ranking_rationale=None,
        ranking_strengths=None,
        ranking_gaps=None,
        ranked_at=None,
    )
    service = JobApplicationService(
        db=SimpleNamespace(),
        resume_service=ResumeService(),
        xkiro_service=RankingProvider(),
    )

    await service._rank_application(SimpleNamespace(), application)

    assert application.ranking_score == 75

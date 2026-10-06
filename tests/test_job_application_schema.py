from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.schemas.job_application_schema import JobApplicationResponse


def test_job_application_response_exposes_candidate_contact_fields():
    application = SimpleNamespace(
        id=uuid4(),
        job_id=uuid4(),
        organization_id=uuid4(),
        candidate_name="Ayesha Khan",
        candidate_email="ayesha@example.com",
        candidate_phone="+92 300 1234567",
        candidate_location="Lahore",
        linkedin_url="https://www.linkedin.com/in/ayesha",
        portfolio_url="https://ayesha.example.com",
        summary="Backend engineer",
        parsed_resume=None,
        cover_letter=None,
        status="submitted",
        ranking_score=None,
        ranking_recommendation=None,
        ranking_rationale=None,
        ranking_strengths=None,
        ranking_gaps=None,
        ranking_status="pending",
        ranking_error=None,
        ranked_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    response = JobApplicationResponse.model_validate(application)

    assert response.candidate_name == "Ayesha Khan"
    assert str(response.candidate_email) == "ayesha@example.com"
    assert response.candidate_phone == "+92 300 1234567"
    assert response.candidate_location == "Lahore"

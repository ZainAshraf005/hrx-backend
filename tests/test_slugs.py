from datetime import UTC, datetime
from types import SimpleNamespace

from app.core.slug import SLUG_MAX_LENGTH, slug_with_suffix, slugify
from app.schemas.job_schema import PublicJobResponse


def test_slugify_creates_url_safe_hyphenated_slugs():
    assert slugify("Zain Mania") == "zain-mania"
    assert slugify("  Senior Software Engineer!  ") == "senior-software-engineer"
    assert slugify("Développeur Python") == "developpeur-python"


def test_slug_suffix_respects_database_length_limit():
    value = slug_with_suffix("a" * SLUG_MAX_LENGTH, 12)

    assert len(value) == SLUG_MAX_LENGTH
    assert value.endswith("-12")


def test_public_job_response_does_not_expose_internal_ids():
    now = datetime.now(UTC)
    job = SimpleNamespace(
        id="internal-job-id",
        organization_id="internal-organization-id",
        slug="senior-software-engineer",
        title="Senior Software Engineer",
        description="Build reliable systems.",
        department="Engineering",
        location="Lahore",
        employment_type="full_time",
        workplace_type="hybrid",
        salary_min=None,
        salary_max=None,
        salary_currency="USD",
        salary_period="yearly",
        experience_level="Senior",
        requirements=None,
        responsibilities=None,
        benefits=None,
        published_at=now,
        created_at=now,
        updated_at=now,
        organization=SimpleNamespace(
            id="internal-organization-id",
            name="Zain Mania",
            slug="zain-mania",
            website=None,
        ),
    )

    response = PublicJobResponse.model_validate(job).model_dump(mode="json")

    assert response["slug"] == "senior-software-engineer"
    assert response["organization"]["slug"] == "zain-mania"
    assert "id" not in response
    assert "organization_id" not in response
    assert "id" not in response["organization"]

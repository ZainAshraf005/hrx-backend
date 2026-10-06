import re
from calendar import monthrange
from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.config import RESUME_ALLOWED_EXTENSIONS, RESUME_MAX_UPLOAD_BYTES
from app.schemas.job_application_schema import ParsedResume

RESUME_READ_CHUNK_BYTES = 1024 * 1024
CHARACTER_SPACED_PATTERN = re.compile(r"[A-Za-z0-9](?:\s+[A-Za-z0-9]){2,}")
CHARACTER_SPACED_SEPARATOR_PLACEHOLDERS = {
    "__RESUME_PIPE_SEPARATOR__": "|",
    "__RESUME_EM_DASH_SEPARATOR__": "\u2014",
    "__RESUME_EN_DASH_SEPARATOR__": "\u2013",
}


class ResumeService:
    def normalize_parsed_resume(
        self,
        parsed_resume: ParsedResume,
        as_of: date | None = None,
    ) -> ParsedResume:
        reference_date = as_of or datetime.now(UTC).date()
        intervals: list[tuple[date, date]] = []

        for experience in parsed_resume.work_experience:
            start = self._parse_resume_date(
                experience.start_date,
                reference_date,
                is_end=False,
            )
            end = self._parse_resume_date(
                experience.end_date,
                reference_date,
                is_end=True,
            )
            if start is None or end is None or start > end:
                continue
            intervals.append((start, min(end, reference_date)))

        if not intervals:
            return parsed_resume

        intervals.sort(key=lambda item: item[0])
        merged: list[tuple[date, date]] = []
        for start, end in intervals:
            if not merged or start > merged[-1][1]:
                merged.append((start, end))
                continue
            previous_start, previous_end = merged[-1]
            merged[-1] = (previous_start, max(previous_end, end))

        total_days = sum((end - start).days for start, end in merged)
        total_years = round(total_days / 365.2425, 1)
        return parsed_resume.model_copy(
            update={"total_experience_years": total_years}
        )

    async def extract_text(self, resume: UploadFile) -> str:
        extension = self._validate_resume_file(resume)
        file_bytes = await self._read_limited(resume)

        if extension == "pdf":
            text = await run_in_threadpool(self._extract_pdf_text, file_bytes)
        elif extension == "docx":
            text = await run_in_threadpool(self._extract_docx_text, file_bytes)
        else:
            raise HTTPException(status_code=400, detail="Unsupported resume file type")

        text = self._normalize_text(text)
        if not text:
            raise HTTPException(status_code=400, detail="Could not extract text from resume")
        return text

    def _validate_resume_file(self, resume: UploadFile) -> str:
        if not resume.filename:
            raise HTTPException(status_code=400, detail="Resume filename is required")

        extension = self._get_extension(resume.filename)
        if extension not in RESUME_ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Unsupported resume file type")
        return extension

    async def _read_limited(self, resume: UploadFile) -> bytes:
        chunks = []
        total_size = 0

        while True:
            chunk = await resume.read(RESUME_READ_CHUNK_BYTES)
            if not chunk:
                break

            total_size += len(chunk)
            if total_size > RESUME_MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Resume file is too large")

            chunks.append(chunk)

        return b"".join(chunks)

    def _get_extension(self, filename: str | None) -> str:
        return Path(filename or "").suffix.lstrip(".").lower()

    def _extract_pdf_text(self, file_bytes: bytes) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise HTTPException(status_code=500, detail="pypdf dependency is not installed") from exc

        try:
            reader = PdfReader(BytesIO(file_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Could not read PDF resume") from exc

    def _extract_docx_text(self, file_bytes: bytes) -> str:
        try:
            from docx import Document
        except ImportError as exc:
            raise HTTPException(status_code=500, detail="python-docx dependency is not installed") from exc

        try:
            document = Document(BytesIO(file_bytes))
            return "\n".join(paragraph.text for paragraph in document.paragraphs)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Could not read DOCX resume") from exc

    def _normalize_text(self, text: str) -> str:
        lines = [self._normalize_line(line.strip()) for line in text.splitlines()]
        return "\n".join(line for line in lines if line)

    def _normalize_line(self, line: str) -> str:
        if not CHARACTER_SPACED_PATTERN.search(line):
            return re.sub(r"[ \t]+", " ", line)

        line = re.sub(r"\s+\|\s+", "  __RESUME_PIPE_SEPARATOR__  ", line)
        line = re.sub(r"\s+\u2014\s+", "  __RESUME_EM_DASH_SEPARATOR__  ", line)
        line = re.sub(r"\s+\u2013\s+", "  __RESUME_EN_DASH_SEPARATOR__  ", line)

        parts = re.split(r"\s{2,}", line)
        normalized = " ".join("".join(part.split()) for part in parts if part.strip())
        for placeholder, separator in CHARACTER_SPACED_SEPARATOR_PLACEHOLDERS.items():
            normalized = normalized.replace(placeholder, separator)
        return normalized

    def _parse_resume_date(
        self,
        value: str | None,
        as_of: date,
        *,
        is_end: bool,
    ) -> date | None:
        if not value or not value.strip():
            return None

        normalized = value.strip().lower().replace(",", " ")
        normalized = re.sub(r"\s+", " ", normalized)
        if normalized in {"present", "current", "ongoing", "now"}:
            return as_of

        for date_format in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return (
                    datetime.strptime(normalized, date_format)
                    .replace(tzinfo=UTC)
                    .date()
                )
            except ValueError:
                continue

        for date_format in ("%b %Y", "%B %Y", "%m/%Y", "%Y-%m"):
            try:
                parsed = (
                    datetime.strptime(normalized, date_format)
                    .replace(tzinfo=UTC)
                    .date()
                )
                if is_end:
                    return parsed.replace(
                        day=monthrange(parsed.year, parsed.month)[1]
                    )
                return parsed.replace(day=1)
            except ValueError:
                continue

        if re.fullmatch(r"\d{4}", normalized):
            year = int(normalized)
            return date(year, 12, 31) if is_end else date(year, 1, 1)

        return None

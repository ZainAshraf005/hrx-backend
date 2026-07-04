from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.config import RESUME_ALLOWED_EXTENSIONS, RESUME_MAX_UPLOAD_BYTES


RESUME_READ_CHUNK_BYTES = 1024 * 1024


class ResumeService:
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
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line)

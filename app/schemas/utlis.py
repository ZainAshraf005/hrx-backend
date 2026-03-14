from pydantic import BaseModel


class Response(BaseModel):
    message: str | None = None
    success: bool

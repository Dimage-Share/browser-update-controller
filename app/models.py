from pydantic import BaseModel
from typing import Optional


class ReportIn(BaseModel):
    browser: str
    hostname: str
    os: str
    ring: str
    version: str
    status: str
    details: Optional[str] = ""

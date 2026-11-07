import re
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional, List, Dict, Any

EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

class WidgetCreate(BaseModel):
    type: Literal["signup", "contact", "cta"] = "contact"
    title: str = Field(..., min_length=2, max_length=100)
    description: str = Field(..., min_length=2, max_length=255)
    button_text: str = Field(default="Submit", min_length=1, max_length=50)
    allowed_origin: Optional[str] = Field(default="*")

class WidgetResponse(BaseModel):
    id: str
    tenant_id: str
    type: str
    title: str
    description: str
    button_text: str
    allowed_origin: str
    embed_snippet: str
    created_at: str

class WidgetConfigResponse(BaseModel):
    id: str
    type: str
    title: str
    description: str
    button_text: str

class SubmissionCreate(BaseModel):
    widget_id: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., min_length=5, max_length=255)
    name: Optional[str] = Field(default="", max_length=100)
    message: Optional[str] = Field(default="", max_length=2000)
    # Honeypot field: Humans leave this empty. Bots automatically fill it.
    hp_company_field: Optional[str] = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        v = v.strip()
        if not re.match(EMAIL_REGEX, v):
            raise ValueError("Invalid email format. Must be a valid email address.")
        return v.lower()

class SubmissionResponse(BaseModel):
    id: str
    widget_id: str
    email: str
    status: Literal["received", "stored", "spam_rejected"]
    country: Optional[str] = None
    city: Optional[str] = None
    created_at: str

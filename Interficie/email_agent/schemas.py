from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class EmailRequest(BaseModel):
    booking_id: str = Field(min_length=1)
    guest_email: str = Field(min_length=3)
    guest_name: str = Field(default="Huesped")
    hotel: str = Field(min_length=1)
    arrival: str = Field(min_length=1)
    risk_level: Literal["ALTO", "CRITICO"]
    cancel_prob: float = Field(ge=0, le=1)
    profile: str = Field(min_length=1)
    actions: list[str] = Field(default_factory=list)
    causes: list[str] = Field(default_factory=list)

    @field_validator("guest_email")
    @classmethod
    def validate_guest_email(cls, value: str) -> str:
        email = value.strip()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("guest_email must be a valid email address")
        return email

    @field_validator("guest_name")
    @classmethod
    def validate_guest_name(cls, value: str) -> str:
        name = value.strip()
        return name or "Huesped"


class BookingConfirmationEmailRequest(BaseModel):
    booking_id: str = Field(min_length=1)
    guest_email: str = Field(min_length=3)
    guest_name: str = Field(default="Huesped")
    hotel: str = Field(min_length=1)
    arrival: str = Field(min_length=1)
    total_nights: int = Field(ge=1)
    total_guests: int = Field(ge=1)
    room_type: str = Field(min_length=1)
    meal: str = Field(min_length=1)
    deposit_type: str = Field(default="Unknown")
    spend_total: float = Field(ge=0)

    @field_validator("guest_email")
    @classmethod
    def validate_guest_email(cls, value: str) -> str:
        email = value.strip()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("guest_email must be a valid email address")
        return email

    @field_validator("guest_name")
    @classmethod
    def validate_guest_name(cls, value: str) -> str:
        name = value.strip()
        return name or "Huesped"


class EmailDraft(BaseModel):
    subject: str = Field(min_length=1)
    contents: str = Field(min_length=1)


class EmailSendResult(BaseModel):
    status: Literal["sent"]
    subject: str
    to: str

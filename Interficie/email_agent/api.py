from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from email_agent.schemas import BookingConfirmationEmailRequest, EmailRequest, EmailSendResult
from email_agent.service import process_booking_confirmation_email, process_high_risk_email

STATIC_DIR = Path(__file__).resolve().parents[1]

app = FastAPI(title="IDSS High-Risk Email Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/high-risk-email", response_model=EmailSendResult)
def send_high_risk_email(payload: EmailRequest):
    try:
        return process_high_risk_email(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Email agent failed: {exc}") from exc


@app.post("/api/booking-confirmation-email", response_model=EmailSendResult)
def send_booking_confirmation_email(payload: BookingConfirmationEmailRequest):
    try:
        return process_booking_confirmation_email(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Email agent failed: {exc}") from exc


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="dashboard")

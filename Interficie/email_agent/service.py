from __future__ import annotations

from email_agent.llms import get_email_draft_llm
from email_agent.mail_sender import SMTPMailSender
from email_agent.schemas import BookingConfirmationEmailRequest, EmailDraft, EmailRequest, EmailSendResult


def build_prompt(request: EmailRequest) -> list[tuple[str, str]]:
    actions = "\n".join(f"- {action}" for action in request.actions[:5]) or "- Confirmar la reserva"
    causes = "\n".join(f"- {cause}" for cause in request.causes[:5]) or "- Riesgo alto calculado por el IDSS"
    probability = round(request.cancel_prob * 100, 1)
    return [
        (
            "system",
            (
                "You compose plaintext hotel guest emails in Spanish. "
                "Return only a valid JSON object with subject and contents. "
                "Be concise, professional and helpful. Do not mention internal models, "
                "risk scoring, XGBoost, probability values, or cancellation risk labels. "
                "Never include placeholder text, bracketed fields, or generic contact fields. "
                "Always close the email with exactly this fixed signature block: "
                "Atentamente,\nEquipo de Reservas\nGrand Meridian Hotel\n"
                "reservas@grandmeridian.example\n+34 900 000 000"
            ),
        ),
        (
            "human",
            (
                f"Reserva: {request.booking_id}\n"
                f"Nombre del huesped: {request.guest_name}\n"
                f"Hotel: {request.hotel}\n"
                f"Llegada: {request.arrival}\n"
                f"Perfil operativo interno: {request.profile}\n"
                f"Nivel interno: {request.risk_level} ({probability}%)\n"
                f"Senales internas:\n{causes}\n"
                f"Acciones recomendadas:\n{actions}\n\n"
                "Redacta un email al huesped para confirmar la reserva, reducir dudas "
                "y facilitar cambio de fechas antes que cancelacion si lo necesita. "
                f"Saluda por su nombre como '{request.guest_name}'. "
                "La firma debe ser fija y literal:\n"
                "Atentamente,\n"
                "Equipo de Reservas\n"
                "Grand Meridian Hotel\n"
                "reservas@grandmeridian.example\n"
                "+34 900 000 000"
            ),
        ),
    ]


def compose_high_risk_email(request: EmailRequest, llm=None) -> EmailDraft:
    draft_llm = llm or get_email_draft_llm()
    return draft_llm.invoke(build_prompt(request))


def process_high_risk_email(request: EmailRequest, llm=None, sender=None) -> EmailSendResult:
    draft = compose_high_risk_email(request, llm=llm)
    mail_sender = sender or SMTPMailSender.from_env()
    mail_sender.send(
        to_email=request.guest_email,
        subject=draft.subject,
        content=draft.contents,
    )
    return EmailSendResult(status="sent", subject=draft.subject, to=request.guest_email)


def build_booking_confirmation_email(request: BookingConfirmationEmailRequest) -> EmailDraft:
    subject = f"Confirmacion de su reserva {request.booking_id}"
    contents = (
        f"Hola {request.guest_name},\n\n"
        "Su reserva ha sido registrada correctamente. Estos son los datos principales:\n"
        f"- Localizador: {request.booking_id}\n"
        f"- Hotel: {request.hotel}\n"
        f"- Llegada: {request.arrival}\n"
        f"- Estancia: {request.total_nights} noche(s), {request.total_guests} huesped(es)\n"
        f"- Habitacion: tipo {request.room_type}\n"
        f"- Regimen: {request.meal}\n"
        f"- Tipo de deposito: {request.deposit_type}\n"
        f"- Importe estimado: {request.spend_total:.2f} EUR\n\n"
        "El equipo del hotel revisara la reserva y se pondra en contacto con usted si necesita algun dato adicional.\n\n"
        "Atentamente,\n"
        "Equipo de Reservas\n"
        "Grand Meridian Hotel\n"
        "reservas@grandmeridian.example\n"
        "+34 900 000 000"
    )
    return EmailDraft(subject=subject, contents=contents)


def process_booking_confirmation_email(request: BookingConfirmationEmailRequest, sender=None) -> EmailSendResult:
    draft = build_booking_confirmation_email(request)
    mail_sender = sender or SMTPMailSender.from_env()
    mail_sender.send(
        to_email=request.guest_email,
        subject=draft.subject,
        content=draft.contents,
    )
    return EmailSendResult(status="sent", subject=draft.subject, to=request.guest_email)

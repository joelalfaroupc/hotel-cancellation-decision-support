import os
import smtplib
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


INTERFICIE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTERFICIE_DIR))


class EmailAgentValidationTests(unittest.TestCase):
    def test_rejects_medium_risk_email_request(self):
        from email_agent.schemas import EmailRequest

        with self.assertRaises(ValueError):
            EmailRequest(
                booking_id="SIM-001",
                guest_email="guest@example.com",
                hotel="City Hotel",
                arrival="15 July 2026",
                risk_level="MEDIO",
                cancel_prob=0.52,
                profile="Viajero Estandar",
                actions=["Enviar email preventivo"],
                causes=["Riesgo medio calculado por XGBoost"],
            )

    def test_rejects_invalid_guest_email(self):
        from email_agent.schemas import EmailRequest

        with self.assertRaises(ValueError):
            EmailRequest(
                booking_id="SIM-002",
                guest_email="not-an-email",
                hotel="City Hotel",
                arrival="15 July 2026",
                risk_level="ALTO",
                cancel_prob=0.81,
                profile="Viajero Estandar",
                actions=["Enviar email preventivo"],
                causes=["Probabilidad alta"],
            )


class EmailAgentServiceTests(unittest.TestCase):
    def test_composes_email_with_injected_llm(self):
        from email_agent.schemas import EmailDraft, EmailRequest
        from email_agent.service import build_prompt, compose_high_risk_email

        request = EmailRequest(
            booking_id="SIM-003",
            guest_email="guest@example.com",
            guest_name="Maria Garcia",
            hotel="Resort Hotel",
            arrival="22 August 2026",
            risk_level="CRITICO",
            cancel_prob=0.91,
            profile="Turista Familiar",
            actions=["Confirmar llegada por email"],
            causes=["Probabilidad de cancelacion critica calculada por XGBoost"],
        )
        llm = Mock()
        llm.invoke.return_value = EmailDraft(
            subject="Confirmacion de su reserva SIM-003",
            contents="Le escribimos para confirmar su llegada y ayudarle con su estancia.",
        )

        draft = compose_high_risk_email(request, llm=llm)

        self.assertIn("SIM-003", draft.subject)
        self.assertIn("confirmar", draft.contents.lower())
        prompt_text = "\n".join(content for _, content in build_prompt(request))
        self.assertIn("Nombre del huesped: Maria Garcia", prompt_text)
        self.assertIn("Atentamente,", prompt_text)
        self.assertIn("Grand Meridian Hotel", prompt_text)
        self.assertNotIn("[Su Nombre]", prompt_text)
        self.assertNotIn("[Telefono de contacto]", prompt_text)
        self.assertNotIn("[Correo electronico de contacto]", prompt_text)
        llm.invoke.assert_called_once()

    def test_process_request_sends_generated_email(self):
        from email_agent.schemas import EmailDraft, EmailRequest
        from email_agent.service import process_high_risk_email

        request = EmailRequest(
            booking_id="SIM-004",
            guest_email="guest@example.com",
            guest_name="Alex Martin",
            hotel="City Hotel",
            arrival="3 December 2026",
            risk_level="ALTO",
            cancel_prob=0.78,
            profile="Planificador Anticipado",
            actions=["Enviar email de confirmacion reforzada"],
            causes=["Reserva con mucha antelacion"],
        )
        llm = Mock()
        llm.invoke.return_value = EmailDraft(
            subject="Queremos confirmar su reserva",
            contents="Nos gustaria confirmar que mantiene su reserva.",
        )
        sender = Mock()

        result = process_high_risk_email(request, llm=llm, sender=sender)

        sender.send.assert_called_once_with(
            to_email="guest@example.com",
            subject="Queremos confirmar su reserva",
            content="Nos gustaria confirmar que mantiene su reserva.",
        )
        self.assertEqual(result.status, "sent")
        self.assertEqual(result.to, "guest@example.com")


class MailSenderTests(unittest.TestCase):
    def test_sender_requires_credentials(self):
        from email_agent.mail_sender import SMTPMailSender

        previous = {
            key: os.environ.get(key)
            for key in ["EMAIL_ADDRESS", "EMAIL_PASSWORD", "EMAIL_HOST", "EMAIL_PORT"]
        }
        for key in previous:
            os.environ.pop(key, None)
        try:
            with self.assertRaises(RuntimeError):
                SMTPMailSender.from_env()
        finally:
            for key, value in previous.items():
                if value is not None:
                    os.environ[key] = value

    def test_sender_loads_credentials_from_local_env_file(self):
        import tempfile

        from email_agent import mail_sender
        from email_agent.mail_sender import SMTPMailSender

        previous = {
            key: os.environ.get(key)
            for key in ["EMAIL_ADDRESS", "EMAIL_PASSWORD", "EMAIL_HOST", "EMAIL_PORT"]
        }
        for key in previous:
            os.environ.pop(key, None)

        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "EMAIL_ADDRESS=hotel@example.com\n"
                "EMAIL_PASSWORD=app-password\n"
                "EMAIL_HOST=smtp.example.com\n"
                "EMAIL_PORT=2465\n",
                encoding="utf-8",
            )
            original_candidates = mail_sender.ENV_FILE_CANDIDATES
            try:
                mail_sender.ENV_FILE_CANDIDATES = (env_file,)
                sender = SMTPMailSender.from_env()
            finally:
                mail_sender.ENV_FILE_CANDIDATES = original_candidates
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

        self.assertEqual(sender.email_address, "hotel@example.com")
        self.assertEqual(sender.email_password, "app-password")
        self.assertEqual(sender.email_host, "smtp.example.com")
        self.assertEqual(sender.email_port, 2465)

    def test_sender_reports_gmail_app_password_error(self):
        from email_agent.mail_sender import SMTPMailSender

        sender = SMTPMailSender(
            email_address="hotel@example.com",
            email_password="regular-password",
        )
        smtp = Mock()
        smtp.__enter__ = Mock(return_value=smtp)
        smtp.__exit__ = Mock(return_value=None)
        smtp.login.side_effect = smtplib.SMTPAuthenticationError(
            534,
            b"5.7.9 Application-specific password required",
        )

        with patch("email_agent.mail_sender.smtplib.SMTP_SSL", return_value=smtp):
            with self.assertRaisesRegex(RuntimeError, "app password"):
                sender.send(
                    to_email="guest@example.com",
                    subject="Subject",
                    content="Body",
                )


class EmailAgentApiTests(unittest.TestCase):
    def test_api_sends_high_risk_email(self):
        from fastapi.testclient import TestClient

        from email_agent import api
        from email_agent.schemas import EmailSendResult

        original = api.process_high_risk_email
        try:
            api.process_high_risk_email = Mock(
                return_value=EmailSendResult(
                    status="sent",
                    subject="Confirmacion de reserva",
                    to="guest@example.com",
                )
            )
            client = TestClient(api.app)
            response = client.post(
                "/api/high-risk-email",
                json={
                    "booking_id": "SIM-005",
                    "guest_email": "guest@example.com",
                    "guest_name": "Laura Perez",
                    "hotel": "City Hotel",
                    "arrival": "7 July 2026",
                    "risk_level": "ALTO",
                    "cancel_prob": 0.82,
                    "profile": "Viajero Estandar",
                    "actions": ["Enviar email claro"],
                    "causes": ["Probabilidad alta"],
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "sent")
            api.process_high_risk_email.assert_called_once()
        finally:
            api.process_high_risk_email = original


if __name__ == "__main__":
    unittest.main()

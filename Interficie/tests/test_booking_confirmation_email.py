import sys
import unittest
from pathlib import Path
from unittest.mock import Mock


INTERFICIE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTERFICIE_DIR))


class BookingConfirmationEmailTests(unittest.TestCase):
    def test_confirmation_request_accepts_any_risk_and_validates_email(self):
        from email_agent.schemas import BookingConfirmationEmailRequest

        request = BookingConfirmationEmailRequest(
            booking_id="WEB-123",
            guest_email=" guest@example.com ",
            guest_name="Laura Perez",
            hotel="City Hotel",
            arrival="21 June 2026",
            total_nights=2,
            total_guests=3,
            room_type="A",
            meal="BB",
            deposit_type="Refundable",
            spend_total=184,
        )

        self.assertEqual(request.guest_email, "guest@example.com")
        self.assertEqual(request.deposit_type, "Refundable")

    def test_process_confirmation_email_sends_plain_confirmation_without_llm(self):
        from email_agent.schemas import BookingConfirmationEmailRequest
        from email_agent.service import process_booking_confirmation_email

        request = BookingConfirmationEmailRequest(
            booking_id="WEB-456",
            guest_email="laura@example.com",
            guest_name="Laura Perez",
            hotel="Resort Hotel",
            arrival="15 August 2026",
            total_nights=4,
            total_guests=2,
            room_type="F",
            meal="HB",
            deposit_type="No Deposit",
            spend_total=644,
        )
        sender = Mock()

        result = process_booking_confirmation_email(request, sender=sender)

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.to, "laura@example.com")
        sender.send.assert_called_once()
        kwargs = sender.send.call_args.kwargs
        self.assertEqual(kwargs["to_email"], "laura@example.com")
        self.assertIn("WEB-456", kwargs["subject"])
        self.assertIn("Laura Perez", kwargs["content"])
        self.assertIn("15 August 2026", kwargs["content"])
        self.assertIn("No Deposit", kwargs["content"])
        self.assertNotIn("cancelacion", kwargs["content"].lower())
        self.assertNotIn("xgboost", kwargs["content"].lower())

    def test_api_sends_booking_confirmation_email(self):
        from fastapi.testclient import TestClient

        from email_agent import api
        from email_agent.schemas import EmailSendResult

        original = api.process_booking_confirmation_email
        try:
            api.process_booking_confirmation_email = Mock(
                return_value=EmailSendResult(
                    status="sent",
                    subject="Confirmacion de su reserva WEB-789",
                    to="guest@example.com",
                )
            )
            client = TestClient(api.app)
            response = client.post(
                "/api/booking-confirmation-email",
                json={
                    "booking_id": "WEB-789",
                    "guest_email": "guest@example.com",
                    "guest_name": "Guest Example",
                    "hotel": "City Hotel",
                    "arrival": "21 June 2026",
                    "total_nights": 1,
                    "total_guests": 2,
                    "room_type": "A",
                    "meal": "SC",
                    "deposit_type": "No Deposit",
                    "spend_total": 92,
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "sent")
            api.process_booking_confirmation_email.assert_called_once()
        finally:
            api.process_booking_confirmation_email = original


if __name__ == "__main__":
    unittest.main()

from unittest import IsolatedAsyncioTestCase
from fastapi.testclient import TestClient
import paystubs_service as ps
from unittest.mock import Mock, patch
import pandas as pd
from io import BytesIO
from dotenv import load_dotenv
import os
from fastapi.exceptions import HTTPException

load_dotenv()
USER = os.getenv("USER")
PASSWORD = os.getenv("PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL")
PASSWORD_EMAIL = os.getenv("PASSWORD_EMAIL")


class TestPaystubsService(IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(self):
        self._client = TestClient(ps.app, base_url="http://0.0.0.0:8080")
        self._sample_data = {
            "full_name": "Shadel Arvelo",
            "email": "shadela@example.com",
            "position": "Engineer",
            "health_discount_amount": 100.0,
            "social_discount_amount": 80.0,
            "taxes_discount_amount": 50.0,
            "other_discount_amount": 20.0,
            "gross_salary": 2000.0,
            "gross_payment": 1800.0,
            "net_payment": 1550.0,
            "period": "2024-01-01",
        }

    @patch.object(ps, "send_email")
    async def test_send_paystubs(self, mock_send_email: Mock):
        mock_send_email.return_value = True
        with open("./tests/simulated_paystubs_test.csv", "rb") as f:
            json_form = {"csv": ("paystubs_test.csv", f, "text/csv")}
            response = self._client.post(
                "/send_paystub/",
                files=json_form,
                params={
                    "credentials": f"{USER}:{PASSWORD}",
                    "company": "atdev",
                    "country": "do",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Paystubs sent successfully")

    async def test_send_paystubs_incorrect_credentials(self):
        with open("./tests/simulated_paystubs_test.csv", "rb") as f:
            json_form = {"csv": ("paystubs_test.csv", f, "text/csv")}
            response = self._client.post(
                "/send_paystub/",
                files=json_form,
                params={
                    "credentials": f"{USER}+{PASSWORD}",
                    "company": "atdev",
                    "country": "do",
                },
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"], "Invalid 'credentials' format. Use 'user:pwd'."
        )

    @patch.object(ps, "validate_request")
    async def test_send_paystubs_incorrect_country(self, mock_validate_request: Mock):
        mock_validate_request.return_value = True
        with open("./tests/simulated_paystubs_test.csv", "rb") as f:
            json_form = {"csv": ("paystubs_test.csv", f, "text/csv")}
            response = self._client.post(
                "/send_paystub/",
                files=json_form,
                params={
                    "credentials": f"{USER}:{PASSWORD}",
                    "company": "atdev",
                    "country": "spn",
                },
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"], "Invalid country code ('do', 'usa')"
        )

    @patch.object(ps, "validate_request")
    @patch.object(ps, "send_email")
    async def test_send_paystubs_failure(
        self, mock_send_email, mock_validate_request: Mock
    ):
        mock_validate_request.return_value = True
        mock_send_email.side_effect = Exception("SMTP failure")

        csv = BytesIO()
        df = pd.DataFrame([self._sample_data])
        df.to_csv(csv, index=False)

        files = {"csv": ("paystubs.csv", csv, "text/csv")}

        response = self._client.post(
            "/send_paystub/",
            params={
                "credentials": f"{USER}:{PASSWORD}",
                "company": "atdev",
                "country": "do",
            },
            files=files,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Error sending to", response.json()["detail"])

    async def test_date_normalizer_valid(self):
        self.assertEqual(ps.date_normalizer("01/01/2024"), "2024-01-01")

    async def test_validate_request_404(self):
        with self.assertRaises(HTTPException):
            credentials = ps.Client(username="Juana", password="123456")
            ps.validate_request(credentials)

    async def test_validate_request_400(self):
        with self.assertRaises(HTTPException):
            credentials = ps.Client(username=USER, password="123456")
            ps.validate_request(credentials)

    @patch.object(ps, "validate_request")
    @patch.object(ps, "date_normalizer")
    async def test_date_parsing_error(
        self, mock_date_normalizer: Mock, mock_validate_request: Mock
    ):
        mock_date_normalizer.side_effect = Exception("Error")
        mock_validate_request.return_value = True

        csv = BytesIO()
        df = pd.DataFrame([self._sample_data])
        df.to_csv(csv, index=False)

        files = {"csv": ("paystubs.csv", csv, "text/csv")}

        response = self._client.post(
            "/send_paystub/",
            params={
                "credentials": f"{USER}:{PASSWORD}",
                "company": "atdev",
                "country": "do",
            },
            files=files,
        )
        self.assertEqual(response.status_code, 400)

    @patch.object(ps, "validate_request")
    async def test_invalid_csv(self, mock_validate_request: Mock):
        mock_validate_request.return_value = True
        csv = BytesIO()
        df = pd.DataFrame([self._sample_data.update({"taxes_discount_amount": False})])
        df.to_csv(csv, index=False)

        files = {"csv": ("paystubs.csv", csv, "text/csv")}
        response = self._client.post(
            "/send_paystub/",
            params={
                "credentials": f"{USER}:{PASSWORD}",
                "company": "atdev",
                "country": "do",
            },
            files=files,
        )
        self.assertEqual(response.status_code, 400)

    async def test_invalid_date_format(self):
        with self.assertRaises(ValueError):
            ps.date_normalizer("20-20-20")

    @patch("smtplib.SMTP")
    async def test_send_email(self, mock_smtp_class):
        mock_smtp_instance = Mock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp_instance

        df = pd.DataFrame([self._sample_data])
        for index, row in df.iterrows():
            pdf_bytes = ps.csv_to_pdf("shadel inc", row, "do")
            ps.send_email("testing@test.com", pdf_bytes, "test.csv")

        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once()
        mock_smtp_instance.send_message.assert_called_once()

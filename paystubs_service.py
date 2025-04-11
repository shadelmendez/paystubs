import io
import logging
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os
from pydantic import BaseModel, EmailStr
import bcrypt
from datetime import date, datetime
import pandas as pd
from pandantic import Pandantic
from fpdf import FPDF
import smtplib
from email.message import EmailMessage
from labels import LABELS


# load credentials from env file
load_dotenv()
USER = os.getenv("USER")
PASSWORD = os.getenv("PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL")
PASSWORD_EMAIL = os.getenv("PASSWORD_EMAIL")
app = FastAPI()

# configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# models
class Client(BaseModel):
    username: str
    password: str

    def check_pwd(self, pwd):
        return bcrypt.checkpw(pwd.encode("utf-8"), self.password.encode("utf-8"))


class PayrollData(BaseModel):
    full_name: str
    email: EmailStr
    position: str
    health_discount_amount: float
    social_discount_amount: float
    taxes_discount_amount: float
    other_discount_amount: float
    gross_salary: float
    gross_payment: float
    net_payment: float
    period: date  # for example:”yyyy-mm-dd”*


# simulate db
hashed_pwd = bcrypt.hashpw(PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
client_db = Client(username=USER, password=hashed_pwd)


def validate_request(credentials: Client):
    """
    Ensures all requests come from authorized clients ('credentials' object)
    - `username`: client's username
    - `password`: client's password
    """
    if not credentials.username or credentials.username != client_db.username:
        raise HTTPException(404, "User not found")

    if not client_db.check_pwd(credentials.password):
        raise HTTPException(400, "Incorrect password")
    else:
        return True


def date_normalizer(raw_date: str) -> str:
    """
    Normalizes the `period` column from the CSV file.
    - `raw_date`: The date string to normalize.
    """
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]

    for f in formats:
        try:
            return datetime.strptime(raw_date, f).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {raw_date}")


def draw_cell(
    fpdf,
    col,
    row,
    colspan=1,
    rowspan=1,
    text="",
    rows=25,
    cols=6,
):
    """
    Draws a text cell within a grid layout on a PDF page using virtual `rows` and `cols`.
    - `fpdf`: The `FPDF` object to draw on.
    - `col`: Starting column position.
    - `row`: Starting row position.
    - `colspan`: Number of columns to span.
    - `rowspan`: Number of rows to span.
    - `text`: Text content to display inside the cell.
    - `rows`: Total number of virtual rows dividing the page height.
    - `cols`: Total number of virtual columns dividing the page width.
    """
    left_margin = fpdf.l_margin
    top_margin = fpdf.t_margin

    page_width = fpdf.w - 2 * left_margin
    page_height = fpdf.h - 2 * top_margin

    col_width = page_width / cols
    row_height = page_height / rows

    x = left_margin + (col - 1) * col_width
    y = top_margin + (row - 1) * row_height
    w = col_width * colspan
    h = row_height * rowspan

    fpdf.set_xy(x, y)
    fpdf.multi_cell(w, h, text, border=False)


def csv_to_pdf(company, csv_data, country):
    """Function to convert CSV file data to PDF.
    - `company`: Client's company
    - `csv_data`: The CSV file data
    - `country`: Client's country
    """
    fpdf = FPDF()

    fpdf.add_page()
    labels = LABELS.get(country.lower(), LABELS["do"])
    # add image
    fpdf.image(
        "./img/atdev.png" if company.lower() == "atdev" else "./img/default.png",
        10,
        10,
        w=40,
    )

    # headers
    fpdf.set_font("Arial", style="B", size=12)
    draw_cell(fpdf, col=3, row=1, colspan=2, text=labels["title"])
    draw_cell(fpdf, col=6, row=4, colspan=2, text=labels["discounts"])
    draw_cell(fpdf, col=2, row=5, colspan=2, text=labels["gross_salary"])
    draw_cell(fpdf, col=2, row=6, colspan=2, text=labels["gross_payment"])
    draw_cell(fpdf, col=2, row=7, colspan=2, text=labels["net_payment"])
    draw_cell(fpdf, col=4, row=5, colspan=2, text=labels["sfs"])
    draw_cell(fpdf, col=4, row=6, colspan=2, text=labels["afp"])
    draw_cell(fpdf, col=4, row=7, colspan=2, text=labels["isr"])
    draw_cell(fpdf, col=4, row=8, colspan=2, text=labels["other"])
    draw_cell(fpdf, col=4, row=9, colspan=2, text=labels["total"])

    # rows
    fpdf.set_font("Arial", size=12)
    draw_cell(fpdf, col=5, row=1, text=csv_data["period"])
    draw_cell(fpdf, col=3, row=2, colspan=3, text=csv_data["full_name"])
    draw_cell(
        fpdf, col=3, row=3, text=csv_data["position"]
    )  # i didn't see a 'title' col so 'position' it is
    draw_cell(fpdf, col=3, row=5, text=str(csv_data["gross_salary"]))
    draw_cell(fpdf, col=3, row=6, text=str(csv_data["gross_payment"]))
    draw_cell(fpdf, col=3, row=7, text=str(csv_data["net_payment"]))
    draw_cell(
        fpdf,
        col=6,
        row=5,
        text=str(csv_data["social_discount_amount"]),
    )
    draw_cell(fpdf, col=6, row=6, text=str(csv_data["health_discount_amount"]))
    draw_cell(fpdf, col=6, row=7, text=str(csv_data["taxes_discount_amount"]))
    draw_cell(fpdf, col=6, row=8, text=str(csv_data["other_discount_amount"]))
    draw_cell(
        fpdf,
        col=6,
        row=9,
        text=str(
            round(
                sum(
                    [
                        csv_data["social_discount_amount"],
                        csv_data["health_discount_amount"],
                        csv_data["taxes_discount_amount"],
                        csv_data["other_discount_amount"],
                    ]
                ),
                2,
            )
        ),
    )

    buffer = io.BytesIO()
    fpdf.output(buffer)
    return buffer.getvalue()


def send_email(email, pdf_bytes, filename):
    """
    Sends an email with a PDF file attached using SMTP.
    - `email`: Recipient's email address.
    - `pdf_bytes`: PDF file content in bytes.
    - `filename`: Filename to assign to the attached PDF.
    """
    msg = EmailMessage()
    msg["Subject"] = "Your Paystub"
    msg["From"] = FROM_EMAIL
    msg["To"] = email
    msg.set_content("Here is your paystub attached.")

    msg.add_attachment(
        pdf_bytes, maintype="application", subtype="pdf", filename=filename
    )

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(FROM_EMAIL, PASSWORD_EMAIL)
        smtp.send_message(msg)


# routes
@app.post("/send_paystub/")
async def send_paystub(
    credentials: str, company: str, country: str = "DO", csv: UploadFile = File(...)
):
    try:
        username, password = credentials.split(":")
        credentials_obj = Client(username=username, password=password)
    except Exception:
        raise HTTPException(400, "Invalid 'credentials' format. Use 'user:pwd'.")

    validate_request(credentials_obj)

    if country.lower() not in ("do", "usa"):
        raise HTTPException(400, "Invalid country code ('do', 'usa')")

    content = await csv.read()
    df = pd.read_csv(io.StringIO(content.decode("utf-8")))

    if "period" in df.columns:
        try:
            df["period"] = df["period"].apply(date_normalizer)
        except Exception as e:
            raise HTTPException(400, f"Date parsing error: {e}")

    try:
        validator = Pandantic(schema=PayrollData)
        validator.validate(dataframe=df, errors="raise")
    except ValueError as e:
        raise HTTPException(400, f"Invalid CSV: {e}")

    sent_emails = []

    for index, row in df.iterrows():
        try:
            paystubs = csv_to_pdf(company, row, country)
            send_email(
                email=row["email"],
                pdf_bytes=paystubs,
                filename=f'paystub_{row["full_name"].replace(" ", "_")}.pdf',
            )
            sent_emails.append(row["email"])
        except Exception as e:
            logger.error(f"Error sending to {row['email']}: {e}")
            raise HTTPException(400, f"Error sending to {row['email']}")

    return JSONResponse(
        content={
            "message": "Paystubs sent successfully",
            "sent_to": sent_emails,
            "timestamp": datetime.now().isoformat(),
        },
        status_code=200,
    )

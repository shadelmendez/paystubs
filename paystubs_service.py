import io
import logging
from fastapi import FastAPI, HTTPException, Request, File, UploadFile
from dotenv import load_dotenv
import os
from pydantic import BaseModel, EmailStr
import bcrypt
from datetime import date, datetime
import pandas as pd
from pandantic import Pandantic


# load credentials from env file
load_dotenv()
USER = os.getenv("USER")
PASSWORD = os.getenv("PASSWORD")

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
    """Normalize the 'period' column form the csv file."""
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]

    for f in formats:
        try:
            return datetime.strptime(raw_date, f).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {raw_date}")


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

    if not validate_request(credentials_obj):
        raise HTTPException(401, "Unauhtorized Request.")

    if country.lower() not in ("do", "usa"):
        raise HTTPException(400, "Invalid country code ('do', 'usa')")

    content = await csv.read()
    df = pd.read_csv(io.StringIO(content.decode("utf-8")))

    # As we don't know wich date format is being used it is necessary to 'normalize it'
    if "period" in df.columns:
        try:
            df["period"] = df["period"].apply(date_normalizer)
        except Exception as e:
            raise HTTPException(400, f"Error: {e}")

    try:
        validator = Pandantic(schema=PayrollData)
        validator.validate(dataframe=df, errors="raise")
    except ValueError as e:
        raise HTTPException(400, f"Invalid CSV: {e}")

    return {"message": "todo bien"}

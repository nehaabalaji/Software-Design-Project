# Database configuration, read from environment variables (see .env.example).
# Each teammate runs their own local MySQL with these same defaults, so no
# shared server or secrets need to be checked into git.

import os

from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_USER = os.environ.get("DB_USER", "queuesmart")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "queuesmart_dev_pw")
DB_NAME = os.environ.get("DB_NAME", "queuesmart_dev")

SQLALCHEMY_DATABASE_URI = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)

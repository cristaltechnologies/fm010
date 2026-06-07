"""
db/connection.py
Database connection — replaces ISAM file open/close (selmfa.cp / selptx.cp)
"""
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

_conn = None

def get_conn():
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            dbname=os.getenv("DB_NAME", "mydb"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )
    return _conn

def close_conn():
    global _conn
    if _conn and not _conn.closed:
        _conn.close()
        _conn = None

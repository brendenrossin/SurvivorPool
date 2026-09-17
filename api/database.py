import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Handle SQLite URLs properly
if DATABASE_URL.startswith("sqlite:"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # pool_pre_ping: Railway's Postgres proxy drops connections that have been
    # idle, and the pool has no idea - it hands one out and the first statement
    # on it raises OperationalError. The dashboard's cache TTLs are 60s while
    # the cron jobs sit idle for far longer, so both ends hit this. Pre-ping
    # spends one cheap round trip per checkout to find out before the caller
    # does, and transparently replaces a dead connection.
    #
    # pool_recycle is the other half: pre-ping catches an already-dead
    # connection, while recycling retires one before it is old enough to be
    # killed, so the failure is avoided rather than detected. 30 minutes sits
    # comfortably under typical proxy and server idle timeouts.
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database with schema from migrations.sql"""
    with open("db/migrations.sql", "r") as f:
        sql_commands = f.read()

    with engine.begin() as conn:
        # Split by semicolon and execute each command
        for command in sql_commands.split(';'):
            command = command.strip()
            if command:
                conn.execute(text(command))

    print("Database initialized successfully")
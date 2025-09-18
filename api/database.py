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
    engine = create_engine(DATABASE_URL)
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
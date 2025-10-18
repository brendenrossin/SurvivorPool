#!/usr/bin/env python3
"""
Comprehensive startup logging to diagnose 502 errors
"""

import sys
import traceback
import logging
from datetime import datetime
import os

def setup_detailed_logging():
    """Setup detailed logging for debugging startup issues"""

    # Create logs directory
    os.makedirs("logs", exist_ok=True)

    # Guard against duplicate handlers (prevents memory leak)
    logger = logging.getLogger("SurvivorPool")
    if not logger.handlers:
        # Configure logging only if not already configured
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            handlers=[
                logging.FileHandler('logs/startup.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
    logger.info("=" * 60)
    logger.info("🚀 SURVIVOR POOL STARTUP SEQUENCE")
    logger.info(f"📅 Timestamp: {datetime.now()}")
    logger.info(f"🐍 Python version: {sys.version}")
    logger.info(f"📁 Working directory: {os.getcwd()}")
    logger.info(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'unknown')}")

    return logger

def log_environment_check(logger):
    """Log all environment variables and system info"""
    logger.info("🔍 ENVIRONMENT CHECK")

    required_vars = [
        'DATABASE_URL',
        'NFL_SEASON',
        'SCORES_PROVIDER',
        'GOOGLE_SHEETS_SPREADSHEET_ID',
        'GOOGLE_SERVICE_ACCOUNT_JSON_BASE64'
    ]

    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive data
            if 'PASSWORD' in var or 'SECRET' in var or 'JSON' in var:
                masked = value[:10] + "..." if len(value) > 10 else "***"
                logger.info(f"   ✅ {var}: {masked}")
            else:
                logger.info(f"   ✅ {var}: {value}")
        else:
            logger.warning(f"   ❌ {var}: NOT SET")

def log_import_check(logger):
    """Test all critical imports"""
    logger.info("📦 IMPORT CHECK")

    imports_to_test = [
        ('streamlit', 'streamlit'),
        ('plotly', 'plotly.express'),
        ('pandas', 'pandas'),
        ('requests', 'requests'),
        ('sqlalchemy', 'sqlalchemy'),
        ('psycopg2', 'psycopg2'),
        ('google.oauth2', 'google.oauth2.service_account'),
        ('dotenv', 'dotenv')
    ]

    for name, module in imports_to_test:
        try:
            __import__(module)
            logger.info(f"   ✅ {name}: OK")
        except ImportError as e:
            logger.error(f"   ❌ {name}: FAILED - {e}")

def log_database_check(logger):
    """Test database connection"""
    logger.info("💾 DATABASE CHECK")

    try:
        from api.database import SessionLocal, engine
        from sqlalchemy import text

        # Test basic connection
        db = SessionLocal()
        result = db.execute(text("SELECT 1 as test")).fetchone()
        db.close()

        logger.info(f"   ✅ Database connection: OK (result: {result})")

        # Test table existence
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"   ✅ Tables found: {tables}")

        return True

    except Exception as e:
        logger.error(f"   ❌ Database connection: FAILED - {e}")
        logger.error(f"   📋 Traceback: {traceback.format_exc()}")
        return False

def log_api_check(logger):
    """Test external APIs (without making actual calls)"""
    logger.info("🌐 API CONFIGURATION CHECK")

    try:
        from api.score_providers import get_score_provider
        provider = get_score_provider("espn")
        logger.info(f"   ✅ ESPN provider initialized: {provider.__class__.__name__}")

        from api.sheets import GoogleSheetsClient
        sheets_client = GoogleSheetsClient()
        logger.info(f"   ✅ Google Sheets client initialized")

        return True

    except Exception as e:
        logger.error(f"   ❌ API initialization: FAILED - {e}")
        logger.error(f"   📋 Traceback: {traceback.format_exc()}")
        return False

def comprehensive_startup_check():
    """Run all startup checks and return success status"""
    try:
        logger = setup_detailed_logging()

        # Environment check
        log_environment_check(logger)

        # Import check
        log_import_check(logger)

        # Database check
        db_ok = log_database_check(logger)

        # API check
        api_ok = log_api_check(logger)

        # Overall status
        if db_ok and api_ok:
            logger.info("🎉 ALL STARTUP CHECKS PASSED")
            return True
        else:
            logger.error("💥 STARTUP CHECKS FAILED")
            return False

    except Exception as e:
        print(f"💥 CRITICAL STARTUP ERROR: {e}")
        print(f"📋 Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = comprehensive_startup_check()
    sys.exit(0 if success else 1)
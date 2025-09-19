#!/usr/bin/env python3
"""
MINIMAL TEST - Figure out what's breaking the app startup
"""

import streamlit as st
import sys
import os
import traceback
from datetime import datetime

# BASIC TEST PAGE
st.set_page_config(page_title="TEST", page_icon="🧪")

st.title("🧪 MINIMAL TEST PAGE")
st.write(f"✅ Streamlit is working!")
st.write(f"🕐 Current time: {datetime.now()}")
st.write(f"🐍 Python version: {sys.version}")
st.write(f"📁 Working directory: {os.getcwd()}")

# Test environment variables
st.subheader("🔧 Environment Variables")
env_vars = [
    'DATABASE_URL',
    'NFL_SEASON',
    'GOOGLE_SHEETS_SPREADSHEET_ID',
    'GOOGLE_SERVICE_ACCOUNT_JSON_BASE64'
]

for var in env_vars:
    value = os.getenv(var)
    if value:
        if 'JSON' in var or 'URL' in var:
            masked = value[:20] + "..." if len(value) > 20 else "***"
            st.write(f"✅ {var}: {masked}")
        else:
            st.write(f"✅ {var}: {value}")
    else:
        st.write(f"❌ {var}: NOT SET")

# Test basic imports
st.subheader("📦 Import Test")
imports_to_test = [
    ('pandas', 'pandas'),
    ('plotly', 'plotly.express'),
    ('requests', 'requests'),
    ('sqlalchemy', 'sqlalchemy'),
    ('psycopg2', 'psycopg2'),
    ('google.oauth2', 'google.oauth2.service_account'),
]

for name, module in imports_to_test:
    try:
        __import__(module)
        st.write(f"✅ {name}: OK")
    except ImportError as e:
        st.write(f"❌ {name}: FAILED - {e}")

# Test database connection
st.subheader("💾 Database Test")
try:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from api.database import SessionLocal

    db = SessionLocal()
    result = db.execute("SELECT 1 as test").fetchone()
    db.close()

    st.write(f"✅ Database connection: OK (result: {result})")
except Exception as e:
    st.write(f"❌ Database connection: FAILED")
    st.write(f"Error: {e}")
    st.code(traceback.format_exc())

# Test Google Sheets
st.subheader("📊 Google Sheets Test")
try:
    from api.sheets import GoogleSheetsClient

    client = GoogleSheetsClient()
    st.write("✅ Google Sheets client created")

    # Try to fetch data
    raw_data = client.get_picks_data()
    st.write(f"✅ Raw data fetched: {len(raw_data)} rows")

    # Show first few rows
    if raw_data:
        st.write("**First 3 rows:**")
        for i, row in enumerate(raw_data[:3]):
            st.write(f"Row {i+1}: {row}")

except Exception as e:
    st.write(f"❌ Google Sheets: FAILED")
    st.write(f"Error: {e}")
    st.code(traceback.format_exc())

st.success("🎉 Test page loaded successfully!")
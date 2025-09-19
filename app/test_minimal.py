"""
Minimal Streamlit test to verify Railway deployment
"""

import streamlit as st
import os

st.title("🏈 Survivor Pool Test")
st.write("If you can see this, Streamlit is working in Railway!")
st.success("✅ Basic Streamlit deployment successful")

# Test basic functionality
if st.button("Test Button"):
    st.balloons()
    st.write("🎉 Interactive features working!")

st.write(f"Current working directory: {os.getcwd()}")
st.write("Environment variables:")
st.write({
    "PORT": os.getenv("PORT", "Not set"),
    "DATABASE_URL": "Set" if os.getenv("DATABASE_URL") else "Not set",
    "ENVIRONMENT": os.getenv("ENVIRONMENT", "Not set")
})
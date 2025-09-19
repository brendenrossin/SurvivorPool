export PORT=8532
export DATABASE_URL="postgresql://postgres:***REMOVED***@postgres.railway.internal:5432/railway"
python init_db_railway.py && streamlit run app/main.py --server.port=${PORT} --server.address=0.0.0.0

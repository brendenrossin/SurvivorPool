export PORT=8532
# DATABASE_URL should be set in your .env file or environment
# Example: export DATABASE_URL="postgresql://postgres:password@localhost:5432/survivorpool"
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable is not set"
    echo "Please set DATABASE_URL in your .env file or export it before running this script"
    exit 1
fi
python init_db_railway.py && streamlit run app/main.py --server.port=${PORT} --server.address=0.0.0.0

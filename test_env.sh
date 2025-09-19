export PORT=8531
echo "" | streamlit run app/main.py --server.port=${PORT} --server.address=0.0.0.0

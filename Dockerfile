# Dockerfile for Railway deployment - FORCE REBUILD
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Make start script executable
RUN chmod +x start.sh

# Expose port (Railway typically uses port 8080)
EXPOSE 8080

# Health check (we'll use a simple check since PORT varies)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/_stcore/health || exit 1

# Run the real Streamlit app
CMD ["./start.sh"]
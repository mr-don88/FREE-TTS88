FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p static/css static/js templates uploads outputs temp database

# Create default HTML templates
RUN mkdir -p templates/components templates/errors templates/admin

# Create a simple index.html if not exists
RUN if [ ! -f "templates/index.html" ]; then \
    echo '<!DOCTYPE html><html><head><title>TTSFree</title></head><body><h1>TTSFree is starting...</h1></body></html>' > templates/index.html; \
    fi

# Create static files
RUN if [ ! -f "static/css/style.css" ]; then \
    echo 'body { font-family: Arial, sans-serif; }' > static/css/style.css; \
    fi

# Create a simple main.js if not exists
RUN if [ ! -f "static/js/main.js" ]; then \
    echo '// TTSFree main.js' > static/js/main.js; \
    fi

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV HOST=0.0.0.0

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

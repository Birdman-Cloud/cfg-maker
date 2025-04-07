# Dockerfile

FROM python:3.11-slim

# Install dependencies including Graphviz AND PostgreSQL development libraries
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        graphviz \
        gcc \
        g++ \
        libpq-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
    
# Set work directory
WORKDIR /app

# Copy files
COPY . .

# Install Python dependencies
# (Consider updating psycopg2-binary version as well, though libpq-dev is the main fix)
RUN pip install --upgrade pip && pip install -r requirements.txt

# Set environment variable to ensure Graphviz's `dot` is in PATH
ENV PATH="/usr/bin:/usr/local/bin:$PATH"

# For debugging: print dot path
RUN which dot
RUN which pg_config # Add this to verify libpq-dev installed correctly

# Expose port (Render typically uses 10000, but 8000 is fine if mapped)
EXPOSE 8000

# Start the app
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000"]
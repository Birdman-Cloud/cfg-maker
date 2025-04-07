# Dockerfile

FROM python:3.11-slim

# Install dependencies including Graphviz AND PostgreSQL development libraries
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        graphviz \
        gcc \
        g++ \
        libpq-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy all project files
COPY . .

# Install Python dependencies from the updated requirements file
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Set environment variable to ensure Graphviz's `dot` is in PATH
ENV PATH="/usr/bin:/usr/local/bin:$PATH"

# For debugging build: print paths
RUN which python
RUN which pip
RUN which dot
RUN which gunicorn

# Expose port (Gunicorn binds to 8000)
EXPOSE 8000

# Start the app using Gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000"]
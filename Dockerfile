FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    DJANGO_RUNNING_IN_DOCKER=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
# Note: libgdk-pixbuf removed as it's not available in newer Debian and is optional for WeasyPrint
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libgirepository1.0-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    shared-mime-info \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create necessary directories
RUN mkdir -p /app/data/new_files /app/data/processed /app/staticfiles

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Expose port
EXPOSE 8000

# Default command (can be overridden by docker-compose)
CMD ["sh", "-c", "python manage.py makemigrations --noinput && \
                python manage.py migrate && \
                python manage.py runserver 0.0.0.0:8000"]
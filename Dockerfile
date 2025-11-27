FROM python:3.12-slim-bookworm

# Install system dependencies for python-ldap, psycopg2, pyvips, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    # LDAP support
    libldap2-dev \
    libsasl2-dev \
    # PostgreSQL
    libpq-dev \
    # Image processing (pyvips)
    libvips-dev \
    # ICU (pyicu)
    libicu-dev \
    pkg-config \
    # Build tools
    gcc \
    g++ \
    # nginx and supervisor
    nginx \
    supervisor \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Copy nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy supervisor config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Railway uses PORT env var
ENV PORT=8080
EXPOSE 8080

# Run supervisor to manage all processes
CMD ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

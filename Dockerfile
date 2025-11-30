# ==============================================================================
# Stage 1: Builder - compile dependencies with full toolchain
# ==============================================================================
FROM python:3.12-bookworm AS builder

# Install build dependencies
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
    # XML/SAML support (xmlsec)
    libxml2-dev \
    libxmlsec1-dev \
    libxmlsec1-openssl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create virtualenv and install dependencies
# Using pre-built wheels where available (no --no-binary flag)
COPY requirements.txt .
RUN python -m venv /app/.venv && \
    /app/.venv/bin/pip install --upgrade pip && \
    /app/.venv/bin/pip install --no-cache-dir -r requirements.txt && \
    /app/.venv/bin/pip install virtualenv

# ==============================================================================
# Stage 2: Runtime - slim image with only runtime dependencies
# ==============================================================================
FROM python:3.12-slim-bookworm

# Install ONLY runtime libraries (no -dev packages needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # LDAP runtime
    libldap-2.5-0 \
    libsasl2-2 \
    # PostgreSQL runtime
    libpq5 \
    # Image processing runtime
    libvips42 \
    # ICU runtime
    libicu72 \
    # nginx and supervisor
    nginx \
    supervisor \
    # File type detection (python-magic)
    libmagic1 \
    # XML/SAML runtime
    libxml2 \
    libxmlsec1 \
    libxmlsec1-openssl \
    && rm -rf /var/lib/apt/lists/*

# Create zulip user (required by Zulip's assert_not_running_as_root)
RUN groupadd -r zulip && useradd -r -g zulip zulip

# Set working directory
WORKDIR /app

# Copy pre-built virtualenv from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Set ownership to zulip user
RUN chown -R zulip:zulip /app

# Create necessary directories with proper permissions
RUN mkdir -p /var/log/zulip /home/zulip /app/static_collected && chown -R zulip:zulip /var/log/zulip /home/zulip /app/static_collected

# NOTE: collectstatic runs at container startup (supervisord) since it needs env vars

# Copy nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy supervisor config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Fix nginx permissions
RUN touch /var/run/nginx.pid && \
    chown -R zulip:zulip /var/run/nginx.pid /var/log/nginx /var/lib/nginx

# Railway uses PORT env var
ENV PORT=8080
EXPOSE 8080

# Run entrypoint script (creates secrets file, then starts supervisord)
CMD ["/app/entrypoint.sh"]

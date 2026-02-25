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
# Force lxml and xmlsec to compile from source so they use the same system libxml2
# (pre-built wheels embed static libxml2 which conflicts with system xmlsec)
COPY requirements.txt .
RUN python -m venv /app/.venv && \
    /app/.venv/bin/pip install --upgrade pip && \
    /app/.venv/bin/pip install --no-cache-dir --no-binary=lxml,xmlsec -r requirements.txt && \
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

# Generate emoji_api.json (lightweight — uses only Python, no node_modules)
# The full build_emoji script needs node_modules, but emoji_api.json only needs
# EMOJI_NAME_MAPS which is pure Python data.
RUN cd /app && /app/.venv/bin/python -c "\
import sys, os, json; \
sys.path.insert(0, '.'); \
from tools.setup.emoji.emoji_names import EMOJI_NAME_MAPS; \
from tools.setup.emoji.emoji_setup_utils import generate_codepoint_to_names_map; \
data = {'code_to_names': generate_codepoint_to_names_map(EMOJI_NAME_MAPS)}; \
os.makedirs('static/generated/emoji', exist_ok=True); \
open('static/generated/emoji/emoji_api.json', 'w').write(json.dumps(data, separators=(',', ':'))); \
print(f'Generated emoji_api.json ({os.path.getsize(\"static/generated/emoji/emoji_api.json\")} bytes)')"

# Set ownership to zulip user
RUN chown -R zulip:zulip /app

# Create necessary directories with proper permissions
# /app/var must be owned by zulip for cache.py to create remote_cache_prefix file
RUN mkdir -p /var/log/zulip /home/zulip /app/static_collected /app/var && \
    chown -R zulip:zulip /var/log/zulip /home/zulip /app/static_collected /app/var

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

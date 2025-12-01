#!/bin/bash
set -e

echo "=== entrypoint.sh starting ==="
echo "SECRET_KEY length: ${#SECRET_KEY}"

# Validate SECRET_KEY is set
if [ -z "$SECRET_KEY" ]; then
    echo "ERROR: SECRET_KEY environment variable is not set!"
    echo "Available environment variables:"
    env | grep -v SECRET | head -20
    exit 1
fi

# Create Zulip config directory
mkdir -p /etc/zulip

# Create Zulip config file (required for PRODUCTION mode)
# Without this, Zulip runs in DEVELOPMENT mode with DEBUG=True
cat > /etc/zulip/zulip.conf << EOF
[machine]
deploy_type = production
EOF

# Write secrets file from environment variables
# Zulip expects an INI-style file with [secrets] section
# Include nodl-specific secrets for JWT authentication
cat > /etc/zulip/zulip-secrets.conf << EOF
[secrets]
secret_key = ${SECRET_KEY}
rabbitmq_password = ${RABBITMQ_PASSWORD}
supabase_jwt_secret = ${SUPABASE_JWT_SECRET}
chat_service_key = ${CHAT_SERVICE_KEY}
EOF

# Set permissions
chmod 640 /etc/zulip/zulip-secrets.conf
chown zulip:zulip /etc/zulip/zulip-secrets.conf

echo "=== Secrets file created ==="
echo "File contents (first 2 lines):"
head -2 /etc/zulip/zulip-secrets.conf

# Create zulip schema if it doesn't exist (required before migrations)
# Zulip's setup scripts normally do this, but Railway has a fresh PostgreSQL
# Using Python/psycopg2 since psql client is not installed in the container
echo "=== Creating zulip schema ==="
/app/.venv/bin/python -c "
import os, psycopg2
conn = psycopg2.connect(
    host=os.environ['POSTGRES_HOST'],
    port=os.environ.get('POSTGRES_PORT', '5432'),
    user=os.environ['POSTGRES_USER'],
    password=os.environ['POSTGRES_PASSWORD'],
    dbname=os.environ['POSTGRES_DB']
)
conn.autocommit = True
cur = conn.cursor()
cur.execute('CREATE SCHEMA IF NOT EXISTS zulip')
cur.close()
conn.close()
print('zulip schema created/verified')
"

# Run database migrations (must run as zulip user, not root)
echo "=== Running database migrations ==="
cd /app
su zulip -c '/app/.venv/bin/python manage.py migrate --noinput'

echo "=== Starting supervisord ==="

# Start supervisord
exec supervisord -n -c /etc/supervisor/conf.d/supervisord.conf

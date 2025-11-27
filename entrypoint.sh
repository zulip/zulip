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

# Create Zulip secrets directory
mkdir -p /etc/zulip

# Write secrets file from environment variables
# Zulip expects an INI-style file with [secrets] section
cat > /etc/zulip/zulip-secrets.conf << EOF
[secrets]
secret_key = ${SECRET_KEY}
EOF

# Set permissions
chmod 640 /etc/zulip/zulip-secrets.conf
chown zulip:zulip /etc/zulip/zulip-secrets.conf

echo "=== Secrets file created ==="
echo "File contents (first 2 lines):"
head -2 /etc/zulip/zulip-secrets.conf

echo "=== Starting supervisord ==="

# Start supervisord
exec supervisord -n -c /etc/supervisor/conf.d/supervisord.conf

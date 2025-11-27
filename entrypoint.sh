#!/bin/bash
set -e

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

echo "Zulip secrets file created at /etc/zulip/zulip-secrets.conf"

# Start supervisord
exec supervisord -n -c /etc/supervisor/conf.d/supervisord.conf

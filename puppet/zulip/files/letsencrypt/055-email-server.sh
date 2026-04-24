#!/usr/bin/env bash
set -euo pipefail

supervisorctl restart zulip-email-server

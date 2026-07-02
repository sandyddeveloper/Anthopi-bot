#!/usr/bin/env bash
set -euo pipefail

echo "Starting deployment for Anthopi-bot..."
python manage.py collectstatic --noinput
python manage.py migrate
exec gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000}

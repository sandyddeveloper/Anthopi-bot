#!/bin/sh
set -e

echo "==> Running database migrations ..."
python manage.py migrate --noinput

echo "==> Ensuring super admin exists ..."
python manage.py create_superadmin

echo "==> Collecting static files ..."
python manage.py collectstatic --noinput 2>/dev/null || true

echo "==> Starting Gunicorn ..."
exec gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000}

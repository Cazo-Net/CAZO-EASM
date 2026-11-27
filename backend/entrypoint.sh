#!/bin/sh
# Container entrypoint. Usage: sh entrypoint.sh <mode>
#   api          migrate the database, then serve the API (gunicorn + uvicorn workers)
#   scan-worker  run queued scans, scheduled scans and periodic jobs
#   migrate      only bring the database schema up to date
#   worker|beat  legacy Celery worker / beat (only if SCAN_EXECUTION_MODE=celery)
set -e

run_migrations() {
    if [ "${SKIP_MIGRATIONS:-false}" = "true" ]; then
        echo "SKIP_MIGRATIONS=true: not touching the database schema."
        return
    fi
    echo "Bringing the database schema up to date..."
    # Fails loudly: a broken migration must stop the deploy, not be ignored.
    python -m app.db_migrate
}

case "$1" in
    api)
        run_migrations
        echo "Starting API server..."
        exec gunicorn app.main:app \
            -k uvicorn.workers.UvicornWorker \
            --bind "0.0.0.0:${PORT:-8000}" \
            --workers "${WEB_CONCURRENCY:-2}" \
            --timeout "${WEB_TIMEOUT:-120}" \
            --graceful-timeout "${WEB_GRACEFUL_TIMEOUT:-30}" \
            --access-logfile - \
            --error-logfile -
        ;;
    scan-worker)
        if [ "${RUN_MIGRATIONS_ON_WORKER:-false}" = "true" ]; then
            run_migrations
        fi
        echo "Starting scan worker..."
        exec python -m app.workers.scan_worker
        ;;
    worker)
        echo "Starting Celery worker..."
        exec celery -A app.celery_app.celery_app worker \
            --loglevel="${CELERY_LOGLEVEL:-info}" \
            --concurrency="${CELERY_CONCURRENCY:-4}"
        ;;
    beat)
        echo "Starting Celery beat..."
        exec celery -A app.celery_app.celery_app beat --loglevel=info
        ;;
    migrate)
        run_migrations
        ;;
    *)
        exec "$@"
        ;;
esac

#!/bin/sh
set -e

run_migrations() {
    echo "Running database migrations..."
    if [ "${USE_SQLITE}" = "true" ] || [ "${USE_SQLITE}" = "True" ]; then
        echo "USE_SQLITE enabled; skipping Alembic (dev bootstrap via create_all)."
    else
        alembic upgrade head
    fi
}

case "$1" in
    api)
        run_migrations
        echo "Starting API server..."
        exec gunicorn app.main:app \
            -k uvicorn.workers.UvicornWorker \
            --bind 0.0.0.0:8000 \
            --workers "${WEB_CONCURRENCY:-4}" \
            --timeout "${WEB_TIMEOUT:-120}" \
            --access-logfile - \
            --error-logfile -
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

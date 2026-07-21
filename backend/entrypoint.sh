#!/bin/sh
set -e

run_migrations() {
    echo "Running database schema bootstrap..."

    # The application creates the full base schema idempotently via
    # Base.metadata.create_all at startup (app.database.init_db). This is the
    # reliable, single source of truth for table creation across environments.
    echo "Ensuring base schema exists (create_all)..."
    python -c "from app.database import init_db; init_db(); print('Schema bootstrap complete.')"

    # Alembic migrations are applied best-effort on top for additive changes.
    # They must not abort startup if the schema already matches.
    echo "Applying Alembic migrations (best-effort)..."
    alembic upgrade head || echo "WARNING: alembic upgrade head reported issues; relying on create_all bootstrap."
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

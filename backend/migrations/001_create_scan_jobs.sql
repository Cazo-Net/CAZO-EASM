-- Migration: Create scan_jobs table for the database-backed job queue.
-- Run this against the shared Postgres database.

CREATE TABLE IF NOT EXISTS scan_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    domain TEXT NOT NULL,
    scan_type TEXT NOT NULL DEFAULT 'full',
    scan_options JSONB DEFAULT '{}',
    org_id UUID NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    attempt INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 2,
    worker_id TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Partial index for fast polling: only index pending jobs
CREATE INDEX IF NOT EXISTS idx_scan_jobs_status_pending
    ON scan_jobs (priority DESC, created_at ASC)
    WHERE status = 'pending';

-- Index for the reaper: find stuck running jobs
CREATE INDEX IF NOT EXISTS idx_scan_jobs_status_running
    ON scan_jobs (status, started_at)
    WHERE status = 'running';

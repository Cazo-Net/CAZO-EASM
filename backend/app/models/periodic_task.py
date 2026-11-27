"""State for periodic background jobs run by scan workers.

Each periodic job (scheduled-scan tick, SSL expiry check, weekly digest, CVE
sync) has one row. A worker claims a job by atomically moving
``locked_until`` into the future, so with many workers each job still runs
once per interval.
"""
from sqlalchemy import Column, String, DateTime

from app.database import Base


class PeriodicTaskState(Base):
    __tablename__ = "periodic_task_state"

    name = Column(String(100), primary_key=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    locked_by = Column(String(255), nullable=True)

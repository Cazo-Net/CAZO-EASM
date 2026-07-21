from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey, LargeBinary
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Passkey(Base):
    __tablename__ = "passkeys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    credential_id = Column(String(255), unique=True, nullable=False, index=True)
    public_key = Column(String(500), nullable=False)
    sign_count = Column(Integer, default=0)
    device_name = Column(String(255), nullable=True)
    aaguid = Column(String(36), nullable=True)
    transports = Column(String(255), nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from ..database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    table_name = Column(String(100), nullable=False, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    action = Column(String(20), nullable=False)   # CREATE, UPDATE, DELETE
    changed_fields = Column(JSON)                  # {"field": {"old": ..., "new": ...}}
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    user_name = Column(String(200))
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    ip_address = Column(String(50))

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


RELATIONSHIP_TYPES = [
    "אב", "בן", "אח", "גיס", "דוד", "חתן", "חמיו",
    "תלמיד של", "רב של", "חבר", "אחר"
]


class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True, index=True)
    alumni_id = Column(Integer, ForeignKey("alumni.id"), nullable=False, index=True)
    related_alumni_id = Column(Integer, ForeignKey("alumni.id"), nullable=False, index=True)
    relationship_type = Column(String(50), nullable=False)
    notes = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    alumni = relationship("Alumni", foreign_keys=[alumni_id], back_populates="relationships_as_source")
    related_alumni = relationship("Alumni", foreign_keys=[related_alumni_id], back_populates="relationships_as_target")

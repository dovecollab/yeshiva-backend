from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Cycle(Base):
    __tablename__ = "cycles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)        # e.g. "מחזור ס"א"
    hebrew_year = Column(String(20), nullable=False)               # e.g. "תשע"ט"
    gregorian_year_start = Column(Integer)                         # e.g. 2018
    gregorian_year_end = Column(Integer)                           # e.g. 2019
    description = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    alumni = relationship("Alumni", back_populates="cycle")

    @property
    def alumni_count(self):
        return len(self.alumni)

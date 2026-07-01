from sqlalchemy import Column, Integer, String, Date, DateTime, Text, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Alumni(Base):
    __tablename__ = "alumni"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False, index=True)
    last_name = Column(String(100), nullable=False, index=True)
    full_name = Column(String(200), index=True)
    id_number = Column(String(20), unique=True, index=True)
    birth_date = Column(Date)
    phone = Column(String(20), index=True)
    phone2 = Column(String(20))
    address = Column(String(300))
    city = Column(String(100), index=True)
    email = Column(String(200), index=True)
    marital_status = Column(String(50))
    notes = Column(Text)
    photo_path = Column(String(500))
    completeness_score = Column(Float, default=0.0)
    tags = Column(String(500), default="", nullable=False)


    # Cycle association
    cycle_id = Column(Integer, ForeignKey("cycles.id"), index=True)
    hebrew_year_entry = Column(String(20))
    hebrew_year_exit = Column(String(20))
    gregorian_year_entry = Column(Integer)
    gregorian_year_exit = Column(Integer)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    cycle = relationship("Cycle", back_populates="alumni")
    documents = relationship("AlumniDocument", back_populates="alumni", cascade="all, delete-orphan")
    relationships_as_source = relationship(
        "Relationship", foreign_keys="Relationship.alumni_id", back_populates="alumni", cascade="all, delete-orphan"
    )
    relationships_as_target = relationship(
        "Relationship", foreign_keys="Relationship.related_alumni_id", back_populates="related_alumni"
    )
    audit_logs = relationship("AuditLog", foreign_keys="AuditLog.record_id",
                              primaryjoin="and_(AuditLog.record_id==Alumni.id, AuditLog.table_name=='alumni')",
                              viewonly=True)

    @property
    def cycle_name(self) -> str:
        return self.cycle.name if self.cycle else None

    def calculate_completeness(self) -> float:
        fields = [
            self.first_name, self.last_name, self.id_number, self.birth_date,
            self.phone, self.address, self.city, self.email,
            self.marital_status, self.photo_path
        ]
        filled = sum(1 for f in fields if f is not None and str(f).strip() not in ("", "None", "none"))
        return round((filled / len(fields)) * 100, 1)


class AlumniDocument(Base):
    __tablename__ = "alumni_documents"

    id = Column(Integer, primary_key=True, index=True)
    alumni_id = Column(Integer, ForeignKey("alumni.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50))
    file_size = Column(Integer)
    description = Column(String(500))
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    uploaded_by = Column(Integer, ForeignKey("users.id"))

    alumni = relationship("Alumni", back_populates="documents")

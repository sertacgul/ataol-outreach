from sqlalchemy import Column, Integer, String, ForeignKey, Enum, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

class SeniorityEnum(str, enum.Enum):
    Junior = "Junior"
    Mid = "Mid"
    Senior = "Senior"
    Executive = "Executive"

class EmailStatusEnum(str, enum.Enum):
    Unverified = "Unverified"
    Valid = "Valid"
    Invalid = "Invalid"
    Catch_all = "Catch-all"

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    domain = Column(String, unique=True, index=True, nullable=False)
    industry = Column(String, index=True)
    employees_count = Column(Integer)
    country = Column(String, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    contacts = relationship("Contact", back_populates="company", cascade="all, delete-orphan")


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, index=True)
    seniority = Column(Enum(SeniorityEnum))
    email_status = Column(Enum(EmailStatusEnum), default=EmailStatusEnum.Unverified)
    linkedin_url = Column(String)

    company = relationship("Company", back_populates="contacts")

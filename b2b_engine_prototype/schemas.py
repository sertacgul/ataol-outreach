from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
from models import SeniorityEnum, EmailStatusEnum

class CompanyBase(BaseModel):
    name: str
    domain: str
    industry: Optional[str] = None
    employees_count: Optional[int] = None
    country: Optional[str] = None

class CompanyResponse(CompanyBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ContactBase(BaseModel):
    first_name: str
    last_name: str
    email: str
    title: Optional[str] = None
    seniority: Optional[SeniorityEnum] = None
    email_status: EmailStatusEnum = EmailStatusEnum.Unverified
    linkedin_url: Optional[str] = None

class ContactResponse(ContactBase):
    id: int
    company_id: int
    company: Optional[CompanyResponse] = None

    model_config = ConfigDict(from_attributes=True)

class ContactSearchRequest(BaseModel):
    industry: Optional[List[str]] = Field(default=None, description="List of industries to filter by")
    employees_count_min: Optional[int] = Field(default=None, ge=0)
    employees_count_max: Optional[int] = Field(default=None, ge=0)
    seniority: Optional[List[SeniorityEnum]] = None
    country: Optional[str] = None
    title: Optional[str] = Field(default=None, description="Substring match for title")

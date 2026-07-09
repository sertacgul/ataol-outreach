from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from typing import List

from database import get_db
from models import Contact, Company
from schemas import ContactSearchRequest, ContactResponse
import services

router = APIRouter(prefix="/api/v1", tags=["search", "verification"])

@router.post("/search", response_model=List[ContactResponse])
async def search_contacts(request: ContactSearchRequest, db: AsyncSession = Depends(get_db)):
    """
    Dynamic filter endpoint for Contacts based on Company and Contact criteria.
    Abstracted for easier future migration to Elasticsearch.
    """
    # Base query joining Contact and Company
    query = select(Contact).join(Contact.company)
    
    filters = []
    
    # Apply Company filters
    if request.industry:
        filters.append(Company.industry.in_(request.industry))
        
    if request.employees_count_min is not None:
        filters.append(Company.employees_count >= request.employees_count_min)
        
    if request.employees_count_max is not None:
        filters.append(Company.employees_count <= request.employees_count_max)
        
    if request.country:
        filters.append(Company.country == request.country)
        
    # Apply Contact filters
    if request.seniority:
        filters.append(Contact.seniority.in_(request.seniority))
        
    if request.title:
        # ilike for case-insensitive substring match
        filters.append(Contact.title.ilike(f"%{request.title}%"))
        
    # Combine filters dynamically
    if filters:
        query = query.where(and_(*filters))
        
    # Eager load the related company for response generation
    query = query.options(selectinload(Contact.company))
        
    # Execute async query
    result = await db.execute(query)
    contacts = result.scalars().all()
    
    return contacts

@router.get("/verify-test")
async def test_verify(email: str):
    """
    Test endpoint to invoke the email verification service directly.
    """
    status = await services.verify_email(email)
    return {"email": email, "status": status}

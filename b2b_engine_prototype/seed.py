from sqlalchemy.ext.asyncio import AsyncSession
from models import Company, Contact, SeniorityEnum, EmailStatusEnum
from sqlalchemy import select

async def seed_data(db: AsyncSession):
    # Check if we already have data by querying companies
    result = await db.execute(select(Company).limit(1))
    if result.scalars().first() is not None:
        print("Database already contains data, skipping seed.")
        return

    print("Seeding database with mock B2B data...")
    
    # Create 5-10 Companies
    companies_data = [
        Company(name="TechFlow Inc", domain="techflow.io", industry="Software", employees_count=120, country="USA"),
        Company(name="Global Manufacturing", domain="global-mfg.com", industry="Manufacturing", employees_count=4500, country="Germany"),
        Company(name="HealthPlus", domain="healthplus.org", industry="Healthcare", employees_count=800, country="UK"),
        Company(name="FinServe Corp", domain="finserve.com", industry="Finance", employees_count=2100, country="USA"),
        Company(name="EduTech Solutions", domain="edutech.edu", industry="Education", employees_count=45, country="Canada")
    ]
    
    db.add_all(companies_data)
    await db.commit() # Commit to generate IDs
    
    # Need to fetch them back to get IDs reliably in some async db setups, 
    # but add_all updates the objects if configured or we can just access them
    # Let's refresh or just assume IDs are populated (asyncpg usually populates them after commit)
    
    c_techflow = companies_data[0]
    c_global = companies_data[1]
    c_health = companies_data[2]
    c_fin = companies_data[3]
    c_edu = companies_data[4]
    
    contacts_data = [
        # TechFlow
        Contact(company_id=c_techflow.id, first_name="Alice", last_name="Smith", email="alice.smith@techflow.io", title="CTO", seniority=SeniorityEnum.Executive, email_status=EmailStatusEnum.Valid, linkedin_url="linkedin.com/in/alicesmith"),
        Contact(company_id=c_techflow.id, first_name="Bob", last_name="Jones", email="bjones@techflow.io", title="Senior Backend Engineer", seniority=SeniorityEnum.Senior, email_status=EmailStatusEnum.Valid, linkedin_url="linkedin.com/in/bjones"),
        # Global Manufacturing
        Contact(company_id=c_global.id, first_name="Klaus", last_name="Muller", email="kmuller@global-mfg.com", title="VP of Operations", seniority=SeniorityEnum.Executive, email_status=EmailStatusEnum.Catch_all, linkedin_url="linkedin.com/in/klausm"),
        Contact(company_id=c_global.id, first_name="Emma", last_name="Schmidt", email="emma.s@global-mfg.com", title="Logistics Manager", seniority=SeniorityEnum.Mid, email_status=EmailStatusEnum.Valid, linkedin_url="linkedin.com/in/emmaschmidt"),
        # HealthPlus
        Contact(company_id=c_health.id, first_name="Sarah", last_name="Connor", email="sconnor@healthplus.org", title="Director of IT", seniority=SeniorityEnum.Senior, email_status=EmailStatusEnum.Valid, linkedin_url="linkedin.com/in/sconnor"),
        Contact(company_id=c_health.id, first_name="fake_john", last_name="Doe", email="fake_john@healthplus.org", title="Junior IT Support", seniority=SeniorityEnum.Junior, email_status=EmailStatusEnum.Unverified, linkedin_url="linkedin.com/in/jdoe"),
        # FinServe
        Contact(company_id=c_fin.id, first_name="Michael", last_name="Chang", email="mchang@finserve.com", title="Chief Financial Officer", seniority=SeniorityEnum.Executive, email_status=EmailStatusEnum.Valid, linkedin_url="linkedin.com/in/mchang"),
        Contact(company_id=c_fin.id, first_name="David", last_name="Wallace", email="dwallace@finserve.com", title="Financial Analyst", seniority=SeniorityEnum.Mid, email_status=EmailStatusEnum.Unverified, linkedin_url="linkedin.com/in/dwallace"),
        # EduTech
        Contact(company_id=c_edu.id, first_name="Laura", last_name="Palmer", email="lpalmer@edutech.edu", title="Product Manager", seniority=SeniorityEnum.Mid, email_status=EmailStatusEnum.Valid, linkedin_url="linkedin.com/in/lpalmer"),
        Contact(company_id=c_edu.id, first_name="James", last_name="Hurley", email="james@catchall-edutech.edu", title="Marketing Intern", seniority=SeniorityEnum.Junior, email_status=EmailStatusEnum.Unverified, linkedin_url="linkedin.com/in/jhurley"),
    ]
    
    db.add_all(contacts_data)
    await db.commit()
    print("Database seeding completed.")

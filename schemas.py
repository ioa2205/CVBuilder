from pydantic import BaseModel, Field, EmailStr, HttpUrl
from typing import List, Optional

# Use Pydantic V2 features

class ContactInfo(BaseModel):
    full_name: Optional[str] = Field(None, description="Full name of the candidate")
    email: Optional[EmailStr] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    linkedin_url: Optional[HttpUrl] = Field(None, description="URL to LinkedIn profile")
    portfolio_url: Optional[HttpUrl] = Field(None, description="URL to personal portfolio/website")
    address: Optional[str] = Field(None, description="Physical address (optional, less common now)")

class WorkExperienceItem(BaseModel):
    job_title: Optional[str] = Field(None, description="Job title")
    company: Optional[str] = Field(None, description="Company name")
    location: Optional[str] = Field(None, description="Company location (e.g., City, State)")
    start_date: Optional[str] = Field(None, description="Start date (e.g., YYYY-MM or Month YYYY)")
    end_date: Optional[str] = Field(None, description="End date (e.g., YYYY-MM or Month YYYY or 'Present')")
    description: Optional[List[str]] = Field(None, description="List of responsibilities or achievements (bullet points)")

class EducationItem(BaseModel):
    degree: Optional[str] = Field(None, description="Degree obtained (e.g., B.S. in Computer Science)")
    institution: Optional[str] = Field(None, description="Name of the educational institution")
    location: Optional[str] = Field(None, description="Institution location")
    graduation_date: Optional[str] = Field(None, description="Graduation date (e.g., YYYY or Month YYYY)")
    details: Optional[str] = Field(None, description="Optional details like GPA, honors, relevant coursework")

class SkillItem(BaseModel):
    category: Optional[str] = Field(None, description="Skill category (e.g., Programming Languages, Tools, Languages)")
    skills_list: Optional[List[str]] = Field(None, description="List of specific skills within the category")

# Main CV Data Structure
class CVData(BaseModel):
    contact_info: Optional[ContactInfo] = Field(None)
    summary: Optional[str] = Field(None, description="Professional summary or objective statement")
    work_experience: Optional[List[WorkExperienceItem]] = Field(None)
    education: Optional[List[EducationItem]] = Field(None)
    skills: Optional[List[SkillItem]] = Field(None) # Or just Optional[List[str]] for simpler skills section
    # Add other sections as needed (e.g., projects, certifications, awards)

    class Config:
        str_strip_whitespace = True # Utility to clean up strings
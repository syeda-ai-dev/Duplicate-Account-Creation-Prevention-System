import logging
from typing import Dict, Optional, List
from openai import AsyncOpenAI, OpenAIError
from datetime import datetime

from fastapi import HTTPException

from com.mhire.app.config.config import Config
from com.mhire.app.services.job_description.job_description_schema import ErrorResponse, JobDescriptionSection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JobDescription:
    def __init__(self):
        self.config = Config()
        self.client = AsyncOpenAI(api_key=self.config.openai_api_key)
        self.model = self.config.openai_model
        
        if not self.config.openai_api_key:
            error = ErrorResponse(
                status_code=500, 
                detail="OpenAI API key not configured",
                error_type="ConfigurationError"
            )
            raise HTTPException(status_code=error.status_code, detail=error.dict())

    def _create_prompt(self, job_data: Dict) -> str:
        """Create a prompt for the OpenAI model"""
        prompt = "Create a professional, structured job description with the following details:\n\n"
        
        # Company Information
        prompt += "Company Information:\n"
        prompt += f"Company Name: {job_data['company_name']}\n"
        if job_data.get('company_details'):
            prompt += f"Company Details: {job_data['company_details']}\n"
        
        # Position Details
        prompt += "\nPosition Details:\n"
        prompt += f"Job Title: {job_data['job_title']}\n"
        prompt += f"Location: {job_data['job_location']}\n"
        prompt += f"Job Type: {job_data['job_type']}\n"
        prompt += f"Number of Vacancies: {job_data.get('vacancy', 1)}\n"
        
        if job_data.get('salary_range'):
            prompt += f"Salary Range: {job_data['salary_range']}\n"
        if job_data.get('work_hours'):
            prompt += f"Work Hours: {job_data['work_hours']}\n"
        if job_data.get('specialization'):
            prompt += f"Specialization: {job_data['specialization']}\n"
        
        # Requirements
        prompt += "\nRequirements:\n"
        if job_data.get('qualification'):
            prompt += f"Qualification: {job_data['qualification']}\n"
        if job_data.get('years_of_experience'):
            prompt += f"Experience Required: {job_data['years_of_experience']}\n"
        prompt += f"Skills & Requirements: {job_data['job_requirements']}\n"
          # Output Format Instructions
        prompt += "\nPlease structure the job description with exactly the following sections in order. Start each section with its exact title on a new line:\n"
        prompt += "1. Company Overview - Brief introduction to the company\n"
        prompt += "2. Position Summary - Overview of the role and its importance\n"
        prompt += "3. Key Responsibilities - Detailed list of job duties\n"
        prompt += "4. Required Qualifications - Education, experience, and skills needed\n"
        prompt += "5. Benefits & Perks - Compensation package and company benefits\n"
        prompt += "6. How to Apply - Application process and contact information\n\n"
        prompt += "Important formatting rules:\n"
        prompt += "- Start each section with its title exactly as given above\n"
        prompt += "- Put each section title on its own line\n"
        prompt += "- Include all sections in the given order\n"
        prompt += "- Keep section titles exactly as written above\n"
        prompt += "- Do not add any additional section titles\n"
        
        return prompt

    def _parse_sections(self, content: str) -> List[JobDescriptionSection]:
        """Parse the generated content into structured sections"""
        sections = []
        current_title = ""
        current_content = []
        
        # Define section headers to look for
        section_headers = [
            'company overview',
            'position summary',
            'key responsibilities',
            'required qualifications',
            'benefits & perks',
            'how to apply'
        ]
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Remove any leading numbers and dots (e.g., "1. ", "2. ", etc.)
            clean_line = line.lower()
            while clean_line and clean_line[0].isdigit():
                clean_line = clean_line[1:].strip()
            clean_line = clean_line.lstrip('.-):').strip()
            
            # Check if this line is a section header
            is_header = False
            matched_header = None
            
            for header in section_headers:
                if clean_line.startswith(header) or clean_line == header:
                    is_header = True
                    matched_header = header
                    break
            
            if is_header:
                # Save previous section if exists
                if current_title and current_content:
                    sections.append(JobDescriptionSection(
                        title=current_title,
                        content='\n'.join(current_content).strip()
                    ))
                
                # Start new section using the original line format (not lowercase)
                start_idx = line.lower().find(matched_header)
                current_title = line[start_idx:].strip()
                current_content = []
            else:
                current_content.append(line)
        
        # Add the last section
        if current_title and current_content:
            sections.append(JobDescriptionSection(
                title=current_title,
                content='\n'.join(current_content).strip()
            ))
        
        # If no sections were found, try to create a basic structure
        if not sections and content.strip():
            sections = [
                JobDescriptionSection(
                    title="Job Description",
                    content=content.strip()
                )
            ]
        
        return sections

    async def generate_description(self, job_data: Dict) -> Dict:
        """Generate job description using OpenAI"""
        try:
            prompt = self._create_prompt(job_data)
            
            logger.info(f"Generating description for job: {job_data['job_title']}")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional HR content writer. Create clear, well-structured job descriptions with distinct sections."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            if not response.choices or not response.choices[0].message.content:
                error = ErrorResponse(
                    status_code=500,
                    detail="Failed to generate job description",
                    error_type="GenerationError"
                )
                raise HTTPException(status_code=error.status_code, detail=error.dict())
            
            description = response.choices[0].message.content.strip()
            sections = self._parse_sections(description)
            
            if not sections:
                error = ErrorResponse(
                    status_code=500,
                    detail="Failed to parse job description sections",
                    error_type="ParsingError"
                )
                raise HTTPException(status_code=error.status_code, detail=error.dict())
            
            logger.info(f"Successfully generated structured description for: {job_data['job_title']}")
            
            return {
                "status": "success",
                "message": "Job description generated successfully",
                "sections": sections
            }
            
        except OpenAIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            error = ErrorResponse(
                status_code=500,
                detail=f"OpenAI API error: {str(e)}",
                error_type="APIError"
            )
            raise HTTPException(status_code=error.status_code, detail=error.dict())
            
        except Exception as e:
            logger.error(f"Error generating job description: {str(e)}")
            error = ErrorResponse(
                status_code=500,
                detail=f"Error generating job description: {str(e)}",
                error_type="UnexpectedError"
            )
            raise HTTPException(status_code=error.status_code, detail=error.dict())
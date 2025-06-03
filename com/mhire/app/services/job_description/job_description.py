import logging
from typing import Dict, Optional
from openai import AsyncOpenAI, OpenAIError
from datetime import datetime

from fastapi import HTTPException

from com.mhire.app.config.config import Config
from com.mhire.app.services.job_description.job_description_schema import ErrorResponse

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
        prompt = f"Create a professional job description for the following position:\n\n"
        prompt += f"Job Title: {job_data['job_title']}\n"
        prompt += f"Location: {job_data['job_location']}\n"
        
        if job_data.get('salary_range'):
            prompt += f"Salary Range: {job_data['salary_range']}\n"
        
        if job_data.get('work_hours'):
            prompt += f"Work Hours: {job_data['work_hours']}\n"
            
        prompt += f"Job Type: {job_data['job_type']}\n"
        prompt += f"Required Skills: {job_data['job_requirements']}\n\n"
        
        prompt += "Please provide a detailed job description including:\n"
        prompt += "1. Brief company overview\n"
        prompt += "2. Role overview and responsibilities\n"
        prompt += "3. Key qualifications and requirements\n"
        prompt += "4. Benefits and perks (if salary is provided)\n"
        prompt += "5. How to apply\n"
        
        return prompt

    async def generate_description(self, job_data: Dict) -> Dict:
        """Generate job description using OpenAI"""
        try:
            prompt = self._create_prompt(job_data)
            
            logger.info(f"Generating description for job: {job_data['job_title']}")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional HR content writer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            if not response.choices or not response.choices[0].message.content:
                error = ErrorResponse(
                    status_code=500,
                    detail="Failed to generate job description",
                    error_type="GenerationError"
                )
                raise HTTPException(status_code=error.status_code, detail=error.dict())
            
            description = response.choices[0].message.content.strip()
            logger.info(f"Successfully generated description for: {job_data['job_title']}")
            
            return {
                "status": "success",
                "message": "Job description generated successfully",
                "job_description": description
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
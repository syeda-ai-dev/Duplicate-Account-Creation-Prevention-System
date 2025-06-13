import logging
from typing import Dict, List
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
        prompt = (
            "Create an analytical and comprehensive job description that emphasizes the role's impact "
            "and strategic importance. Use clear, professional language without any special characters "
            "or formatting. Structure the content with the following sections:\n\n"
        )
        
        # Input Data
        prompt += f"- Role: {job_data['title']}\n"
        prompt += f"- Company: {job_data['companyName']}\n"
        if job_data.get('companyDetails'):
            prompt += f"- Company Profile: {job_data['companyDetails']}\n"
        prompt += f"- Location: {job_data['location']}\n"
        prompt += f"- Type: {', '.join(job_data['type'])}\n"
        if job_data.get('position'):
            prompt += f"- Level: {job_data['position']}\n"
        if job_data.get('salaryRange'):
            prompt += f"- Compensation: {job_data['salaryRange']}\n"
        if job_data.get('workHours'):
            prompt += f"- Schedule: {job_data['workHours']}\n"
        if job_data.get('specialization'):
            prompt += f"- Focus Area: {job_data['specialization']}\n"
        if job_data.get('qualification'):
            prompt += f"- Education: {job_data['qualification']}\n"
        if job_data.get('experience'):
            prompt += f"- Experience: {job_data['experience']}\n"
        prompt += f"- Required Skills: {', '.join(job_data['skills'])}\n\n"
        
        # Output Instructions
        prompt += "Create a professional job description that includes:\n\n"
        prompt += "1. Company Overview:\n"
        prompt += "- Analyze the company's market position and value proposition\n"
        prompt += "- Highlight company culture and work environment\n\n"
        
        prompt += "2. Position Summary:\n"
        prompt += "- Explain the role's strategic importance\n"
        prompt += "- Describe the impact on business objectives\n"
        prompt += "- Outline growth opportunities\n\n"
        
        prompt += "3. Key Responsibilities:\n"
        prompt += "- List core duties with their business impact\n"
        prompt += "- Emphasize leadership and collaborative aspects\n"
        prompt += "- Include strategic decision-making responsibilities\n\n"
        
        prompt += "4. Required Qualifications:\n"
        prompt += "- Detail essential technical skills and their relevance\n"
        prompt += "- Specify experience requirements with context\n"
        prompt += "- Include soft skills and leadership capabilities\n\n"
        
        prompt += "5. Benefits and Compensation:\n"
        prompt += "- Present complete compensation package\n"
        prompt += "- Highlight professional development opportunities\n"
        prompt += "- Describe work-life balance benefits\n\n"
        
        prompt += "6. Application Process:\n"
        prompt += "- Provide clear application instructions\n"
        prompt += "- Outline next steps in the process\n\n"
        
        prompt += "Important Guidelines:\n"
        prompt += "- Use clear, professional language\n"
        prompt += "- Avoid special characters or formatting\n"
        prompt += "- Focus on value and impact\n"
        prompt += "- Be specific and actionable\n"
        prompt += "- Keep sections clearly separated\n"
        prompt += "- Maintain a professional, engaging tone\n"
        
        return prompt

    def _parse_sections(self, content: str) -> List[JobDescriptionSection]:
        """Parse the generated content into a single section"""
        return [JobDescriptionSection(
            title="Job Description",
            content=content.strip()
        )]

    async def generate_description(self, job_data: Dict) -> Dict:
        """Generate job description using OpenAI"""
        try:
            prompt = self._create_prompt(job_data)
            
            logger.info(f"Generating description for job: {job_data['title']}")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": (
                            "You are a professional technical recruiter and HR content writer. "
                            "Create clear, analytical job descriptions that emphasize impact and value. "
                            "Use plain text without special characters or markdown formatting. "
                            "Structure content with clear section headers and maintain a professional tone. "
                            "Focus on explaining why each requirement matters and how the role contributes to business success."
                        )
                    },
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
            
            logger.info(f"Successfully generated description for: {job_data['title']}")
            
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

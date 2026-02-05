import requests
from bs4 import BeautifulSoup
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from markdown_utils import generate_pdf_from_markdown

def extract_job_link_content(url: str) -> str:
    """Extract job description from a job posting URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to find job description - this is site-specific and may need adjustments
        # Common job sites have specific div classes or IDs for job descriptions
        
        # LinkedIn
        if 'linkedin.com' in url:
            job_description = soup.find('div', {'class': 'description__text'})
            if job_description:
                return job_description.get_text()
        
        # Indeed
        elif 'indeed.com' in url:
            job_description = soup.find('div', {'id': 'jobDescriptionText'})
            if job_description:
                return job_description.get_text()
        
        # Generic fallback - look for common job description containers
        for potential_container in [
            soup.find('div', {'class': ['job-description', 'description', 'jobDescription']}),
            soup.find('section', {'class': ['job-description', 'description', 'jobDescription']}),
            soup.find(id=['job-description', 'jobDescription', 'description'])
        ]:
            if potential_container:
                return potential_container.get_text()
        
        # If no specific container found, extract the main content
        main_content = soup.find('main') or soup.find('article') or soup.body
        if main_content:
            return main_content.get_text()
            
        # Last resort - extract all text from the page
        return soup.get_text()
        
    except Exception as e:
        raise Exception(f"Failed to extract job description from URL: {str(e)}")

def analyze_job_description(job_description: str, model) -> Dict[str, Any]:
    """
    Analyze a job description using Claude API.
    Returns structured data about the job requirements, skills, etc.
    """
    analysis_prompt = f"""
    Analyze the following job description and extract key information in a structured JSON format:

    JOB DESCRIPTION:
    {job_description}

    Please identify and return a JSON object with the following elements:
    1. job_title: The title of the job
    2. company_name: The name of the company (if available)
    3. key_responsibilities: A list of the main job responsibilities
    4. required_skills: A list of technical skills required for the job
    5. preferred_skills: A list of skills mentioned as preferred or a plus
    6. required_experience: Details about years of experience or specific experience required
    7. education_requirements: Any educational requirements mentioned
    8. keywords: A list of important keywords from the job description that should be included in a resume
    9. industry: The industry this job belongs to
    10. company_values: Any mentions of company culture or values

    Format your response as a valid JSON object without any additional text.
    """
    
    response = model.generate_content(analysis_prompt)
    
    try:
        # Attempt to parse the response as JSON
        # First, try to extract JSON if it's wrapped in markdown code blocks
        text = response.text
        if '```json' in text and '```' in text.split('```json', 1)[1]:
            json_str = text.split('```json', 1)[1].split('```', 1)[0].strip()
        elif '```' in text and '```' in text.split('```', 1)[1]:
            json_str = text.split('```', 1)[1].split('```', 1)[0].strip()
        else:
            json_str = text
            
        return json.loads(json_str)
    except json.JSONDecodeError:
        # If JSON parsing fails, return a simplified structure with the raw text
        return {
            "raw_analysis": response.text,
            "job_title": "Unknown",
            "required_skills": [],
            "keywords": []
        }
        
def generate_cover_letter(resume_data, job_description, model, timestamp=None):
    """
    Generate a cover letter based on the resume data and job description
    
    Args:
        resume_data: The tailored resume data (JSON object)
        job_description: The job description text
        model: The AI model to use for generation
        timestamp: Optional timestamp for file naming
        
    Returns:
        Path to the generated cover letter PDF
    """
    # Extract key information from resume
    if isinstance(resume_data, str):
        with open(resume_data, 'r') as f:
            resume_data = json.load(f)
    
    # Create a timestamp if not provided
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Prepare candidate information for the prompt
    name = resume_data.get("name", "")
    contact = resume_data.get("contact", {})
    summary = resume_data.get("summary", "")
    
    # Extract key skills and experience
    skills_text = ""
    if "skills" in resume_data:
        skills = resume_data["skills"]
        if isinstance(skills, dict):
            skills_items = []
            for category, skill_list in skills.items():
                if isinstance(skill_list, list):
                    skills_items.append(f"{category}: {', '.join(skill_list)}")
                else:
                    skills_items.append(f"{category}: {skill_list}")
            skills_text = "\n".join(skills_items)
        elif isinstance(skills, list):
            skills_text = ", ".join(skills)
        else:
            skills_text = str(skills)
    
    # Extract experience highlights
    experience_highlights = []
    if "experience" in resume_data:
        for exp in resume_data["experience"]:
            if "highlights" in exp and exp["highlights"]:
                experience_highlights.extend(exp["highlights"])
            if "summary" in exp:
                experience_highlights.append(exp["summary"])
    
    # Create the cover letter generation prompt
    cover_letter_prompt = f"""
    I need to create a professional cover letter for a job application. I'll provide my resume information and the job description.
    
    CANDIDATE INFORMATION:
    Name: {name}
    Professional Summary: {summary}
    Key Skills: {skills_text}
    Experience Highlights: 
    {json.dumps(experience_highlights, indent=2)}
    
    JOB DESCRIPTION:
    {job_description}
    
    Please write a professional, personalized cover letter that:
    1. Addresses the hiring manager respectfully (use "Dear Hiring Manager" if no specific name)
    2. Introduces myself and states the position I'm applying for
    3. Explains why I'm interested in the role and company
    4. Highlights 2-3 of my most relevant skills/experiences for this specific job
    5. Connects my experience to the job requirements
    6. Includes a strong closing paragraph with a call to action
    7. Uses a professional sign-off with my name
    
    The cover letter should be 3-4 paragraphs, concise but persuasive, and demonstrate that I'm the right fit for this role.
    
    FORMAT REQUIREMENTS:
    - Use proper Markdown syntax throughout
    - Bold all technical skills and important terms (like **React**, **AWS**, **Python**, **project management**, etc.)
    - Use a clean, professional layout with appropriate spacing
    - Format my name at the bottom with my title underneath
    
    IMPORTANT: Start directly with the salutation (e.g., "Dear Hiring Manager,"). Do NOT include any introductory text, explanations, or phrases like "Here is a professional cover letter" before the actual cover letter content. Return ONLY the cover letter text with Markdown formatting, beginning immediately with the greeting.
    """
    
    response = model.generate_content(cover_letter_prompt)
    
    # Process the response 
    cover_letter_markdown = response.text
    
    # Clean up if the response contains code blocks
    if '```' in cover_letter_markdown:
        # Extract content from markdown code blocks if present
        matches = re.findall(r'```(?:markdown)?(.*?)```', cover_letter_markdown, re.DOTALL)
        if matches:
            cover_letter_markdown = matches[0].strip()
    
    # Remove common introductory phrases that AI might add
    intro_phrases = [
        r'^Here is a professional cover letter[^:]*:\s*',
        r'^Here\'s a professional cover letter[^:]*:\s*',
        r'^Below is a professional cover letter[^:]*:\s*',
        r'^I\'ve prepared a professional cover letter[^:]*:\s*',
        r'^Here is the cover letter[^:]*:\s*',
        r'^Here\'s the cover letter[^:]*:\s*',
    ]
    for pattern in intro_phrases:
        cover_letter_markdown = re.sub(pattern, '', cover_letter_markdown, flags=re.IGNORECASE | re.MULTILINE)
    
    # Remove any leading/trailing whitespace after cleanup
    cover_letter_markdown = cover_letter_markdown.strip()
    
    # Save the cover letter markdown
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Use template name for the filename if provided, otherwise use a timestamp
    if timestamp and not timestamp.startswith("2"):  # If timestamp is actually a template name
        template_name = timestamp
        file_prefix = f"{template_name}_cover_letter"
    else:
        file_prefix = f"cover_letter_{timestamp}" if timestamp else "cover_letter"
    
    markdown_file_path = output_dir / f"{file_prefix}.md"
    with open(markdown_file_path, "w") as f:
        f.write(cover_letter_markdown)
    
    # Generate PDF from the cover letter markdown
    pdf_path = output_dir / f"{file_prefix}.pdf"
    generate_pdf_from_markdown(cover_letter_markdown, pdf_path)
    
    return pdf_path

def generate_question_answers(questions, job_description, resume_data, model):
    """
    Generate answers to application questions based on the resume and job description
    
    Args:
        questions: List of questions to answer
        job_description: The job description text
        resume_data: The tailored resume data (JSON object)
        model: The AI model to use for generation
        
    Returns:
        List of answers corresponding to the questions
    """
    # Extract key information from resume
    if isinstance(resume_data, str):
        with open(resume_data, 'r') as f:
            resume_data = json.load(f)
    
    # Prepare candidate information for the prompt
    name = resume_data.get("name", "")
    summary = resume_data.get("summary", "")
    
    # Extract key skills and experience
    skills_text = ""
    if "skills" in resume_data:
        skills = resume_data["skills"]
        if isinstance(skills, dict):
            skills_items = []
            for category, skill_list in skills.items():
                if isinstance(skill_list, list):
                    skills_items.append(f"{category}: {', '.join(skill_list)}")
                else:
                    skills_items.append(f"{category}: {skill_list}")
            skills_text = "\n".join(skills_items)
        elif isinstance(skills, list):
            skills_text = ", ".join(skills)
        else:
            skills_text = str(skills)
    
    # Extract experience information
    experience_text = []
    if "experience" in resume_data:
        for exp in resume_data["experience"]:
            exp_info = []
            exp_info.append(f"Position: {exp.get('title', '')}")
            exp_info.append(f"Company: {exp.get('company', '')}")
            exp_info.append(f"Period: {exp.get('period', '')}")
            
            if "summary" in exp:
                exp_info.append(f"Summary: {exp['summary']}")
            
            if "highlights" in exp and exp["highlights"]:
                exp_info.append("Highlights:")
                for highlight in exp["highlights"]:
                    exp_info.append(f"- {highlight}")
            
            experience_text.append("\n".join(exp_info))
    
    # Generate answers for each question
    answers = []
    
    for question in questions:
        question_prompt = f"""
        I'm applying for a job and need to answer an application question. I'll provide my resume information, the job description, and the question.
        
        RESUME INFORMATION:
        Name: {name}
        Professional Summary: {summary}
        Skills: {skills_text}
        
        Experience:
        {json.dumps(experience_text, indent=2)}
        
        JOB DESCRIPTION:
        {job_description}
        
        APPLICATION QUESTION:
        {question}
        
        Please provide a well-crafted answer to this question based on my resume and the job description. The answer should:
        1. Be concise but comprehensive (100-200 words)
        2. Highlight relevant experience, skills, and achievements
        3. Demonstrate how my background makes me a good fit for this role
        4. Use specific examples whenever possible
        5. Be professional in tone and language
        6. Use markdown formatting with **bold** for technical skills and important terms (like **JavaScript**, **team management**, etc.)
        7. Use proper paragraph spacing for readability
        
        Return ONLY the answer to the question, with no explanations or additional text.
        """
        
        response = model.generate_content(question_prompt)
        answers.append(response.text.strip())
    
    return answers

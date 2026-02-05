from venv import logger

from fastapi import FastAPI, HTTPException, Depends, status, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import uuid
from anthropic import Anthropic
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
import json
from datetime import datetime, timedelta
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
import pandas as pd
import zipfile
import tempfile
import shutil
import re
import requests
import asyncio
from urllib.parse import urlparse, parse_qs
try:
    import xlrd
    HAS_XLRD = True
except ImportError:
    HAS_XLRD = False

# Import custom modules
from markdown_utils import generate_pdf_from_json, generate_pdf_from_markdown
from resume_tailor import tailor_resume, convert_json_to_text, convert_json_to_markdown
from job_analysis import generate_cover_letter, generate_question_answers

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")  # Explicit path to ensure local .env is loaded

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Security - auto_error=False allows OPTIONS requests to pass through
security = HTTPBearer(auto_error=False)

# Configure Anthropic Claude with OpenAI fallback
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize both clients if keys are available
claude_client = None
openai_client = None

if ANTHROPIC_API_KEY:
    ANTHROPIC_API_KEY = ANTHROPIC_API_KEY.strip()
    claude_client = Anthropic(api_key=ANTHROPIC_API_KEY)

if OPENAI_API_KEY:
    OPENAI_API_KEY = OPENAI_API_KEY.strip()
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

if not claude_client and not openai_client:
    raise ValueError("At least one of ANTHROPIC_API_KEY or OPENAI_API_KEY must be set")

# Create a model-like object that mimics Gemini's interface for compatibility
class ClaudeModelWrapper:
    def __init__(self, claude_client=None, openai_client=None):
        self.claude_client = claude_client
        self.openai_client = openai_client
        self.claude_model = "claude-3-5-sonnet-20241022"  # Default Claude model
        self.openai_model = "gpt-4o-mini"  # Default OpenAI model
        self.credit_exhausted = False  # Track if Claude credits are exhausted
    
    def generate_content(self, prompt):
        """Mimics Gemini's generate_content method with Claude primary, OpenAI fallback"""
        # Reset credit_exhausted flag at the start of each request
        self.credit_exhausted = False
        
        # Try Claude first if available
        if self.claude_client:
            try:
                response = self.claude_client.messages.create(
                    model=self.claude_model,
                    max_tokens=4096,
                    temperature=0.7,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                
                # Create a response object that mimics Gemini's response
                class Response:
                    def __init__(self, text):
                        self.text = text
                
                # Check if response has content
                if response.content and len(response.content) > 0:
                    # Claude returns content as a list of text blocks
                    content = response.content[0].text if hasattr(response.content[0], 'text') else str(response.content[0])
                    if content:
                        return Response(content)
                    else:
                        raise Exception("Claude API returned empty content")
                else:
                    raise Exception("Claude API returned no content")
                    
            except Exception as e:
                error_msg = str(e)
                error_type = type(e).__name__
                
                # Check if it's a credit/balance error - fallback to OpenAI
                # Check for various credit-related error patterns
                credit_error_keywords = [
                    "credit balance", "too low", "insufficient", "payment", 
                    "payment required", "billing", "account", "quota", 
                    "limit exceeded", "402", "payment_method"
                ]
                is_credit_error = any(keyword in error_msg.lower() for keyword in credit_error_keywords)
                
                # Also check for HTTP status codes that might indicate payment issues
                if hasattr(e, 'status_code'):
                    if e.status_code == 402:  # Payment Required
                        is_credit_error = True
                
                if is_credit_error:
                    print(f"Claude API Error (insufficient credits): {error_msg}")
                    print("Falling back to OpenAI...")
                    self.credit_exhausted = True  # Mark that credits are exhausted
                    if self.openai_client:
                        return self._use_openai(prompt)
                    else:
                        raise Exception(f"Claude API error (insufficient credits) and no OpenAI fallback available: {error_msg}")
                else:
                    # For other errors, try OpenAI fallback if available
                    print(f"Claude API Error: {error_msg}")
                    if self.openai_client:
                        print("Falling back to OpenAI...")
                        return self._use_openai(prompt)
                    else:
                        raise Exception(f"Claude API error: {error_msg}")
        
        # If no Claude client, use OpenAI
        if self.openai_client:
            return self._use_openai(prompt)
        
        raise Exception("No API client available")
    
    def _use_openai(self, prompt):
        """Internal method to use OpenAI API"""
        try:
            response = self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            
            class Response:
                def __init__(self, text):
                    self.text = text
            
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                if content:
                    return Response(content)
                else:
                    raise Exception("OpenAI API returned empty content")
            else:
                raise Exception("OpenAI API returned no choices")
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"OpenAI API Error: {str(e)}")
            print(f"Error details: {error_details}")
            raise Exception(f"OpenAI API error: {str(e)}")

model = ClaudeModelWrapper(claude_client=claude_client, openai_client=openai_client)

# Create output directory for intermediate files
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Batch concurrency (controls how many rows are processed in parallel)
# Note: higher values can trigger Claude API rate limits or high CPU usage during PDF generation.
BATCH_MAX_CONCURRENCY = int(os.getenv("BATCH_MAX_CONCURRENCY", "3"))

# Helper function to normalize template name (case-insensitive file matching)
def normalize_template_name(template_name: str) -> str:
    """
    Normalize template name by finding the actual file in the filesystem (case-insensitive).
    Returns the actual filename as it exists in the filesystem.
    """
    if not template_name:
        return template_name
    
    template_dir = Path("resume_templates")
    if not template_dir.exists():
        return template_name
    
    # Try exact match first
    exact_path = template_dir / template_name
    if exact_path.exists():
        return template_name
    
    # Try case-insensitive match
    template_name_lower = template_name.lower()
    for file in template_dir.iterdir():
        if file.is_file() and file.name.lower() == template_name_lower:
            return file.name
    
    # If not found, return original (will cause error later, but preserves original behavior)
    return template_name

def _process_one_batch_job(
    *,
    row_number: int,
    job_title: str,
    job_description: str,
    questions: List[str],
    safe_title: str,
    built_resume_dir: Path,
    batch_output_dir: Path,
    template_file: str,
    model,
    file_prefix: str
):
    """
    Synchronous per-row job processor (runs in a worker thread via asyncio.to_thread).
    Returns: (generated_files_for_row: List[dict], errors_for_row: List[dict])
    """
    generated_files_for_row: List[dict] = []
    errors_for_row: List[dict] = []

    try:
        # Create folder for this job title in built_resume
        job_folder = built_resume_dir / safe_title
        job_folder.mkdir(exist_ok=True)

        # Tailor the resume (Claude API call)
        _, tailored_resume = tailor_resume(job_description, model, template_file)

        # Resume filename based on person's name in template JSON
        person_name = tailored_resume.get('name', 'Resume') if isinstance(tailored_resume, dict) else 'Resume'
        safe_name = "".join(c for c in person_name if c.isalnum())[:50] if person_name else "Resume"
        resume_filename = f"{safe_name}_resume.pdf"

        # Generate resume PDF
        resume_pdf_path = job_folder / resume_filename
        generate_pdf_from_json(tailored_resume, resume_pdf_path)

        zip_resume_path = batch_output_dir / safe_title / resume_filename
        zip_resume_path.parent.mkdir(exist_ok=True, parents=True)
        shutil.copy2(resume_pdf_path, zip_resume_path)
        generated_files_for_row.append({
            "type": "resume",
            "title": job_title,
            "folder": safe_title,
            "filename": resume_filename,
            "path": str(resume_pdf_path),
            "zip_path": str(zip_resume_path)
        })

        # Generate cover letter
        cover_letter_path = generate_cover_letter(tailored_resume, job_description, model, file_prefix)
        if cover_letter_path and cover_letter_path.exists():
            job_cover_letter_path = job_folder / "cover_letter.pdf"
            if str(cover_letter_path) != str(job_cover_letter_path):
                shutil.move(str(cover_letter_path), str(job_cover_letter_path))

            markdown_filename = cover_letter_path.name.replace('.pdf', '.md')
            original_markdown_path = OUTPUT_DIR / markdown_filename
            if original_markdown_path.exists():
                job_markdown_path = job_folder / "cover_letter.md"
                shutil.move(str(original_markdown_path), str(job_markdown_path))

            zip_cover_letter_path = batch_output_dir / safe_title / "cover_letter.pdf"
            zip_cover_letter_path.parent.mkdir(exist_ok=True, parents=True)
            shutil.copy2(job_cover_letter_path, zip_cover_letter_path)
            generated_files_for_row.append({
                "type": "cover_letter",
                "title": job_title,
                "folder": safe_title,
                "filename": "cover_letter.pdf",
                "path": str(job_cover_letter_path),
                "zip_path": str(zip_cover_letter_path)
            })

        # Generate question answers PDF if questions exist
        if questions:
            try:
                answers = generate_question_answers(questions, job_description, tailored_resume, model)
                question_markdown = "# Question\n\n"
                for i, (question, answer) in enumerate(zip(questions, answers), 1):
                    question_markdown += f"## Question {i}\n\n"
                    question_markdown += f"{question}\n\n"
                    question_markdown += f"### Answer\n\n"
                    question_markdown += f"{answer}\n\n"
                    question_markdown += "---\n\n"

                question_pdf_path = job_folder / "question.pdf"
                generate_pdf_from_markdown(question_markdown, question_pdf_path)

                zip_question_path = batch_output_dir / safe_title / "question.pdf"
                zip_question_path.parent.mkdir(exist_ok=True, parents=True)
                shutil.copy2(question_pdf_path, zip_question_path)
                generated_files_for_row.append({
                    "type": "question",
                    "title": job_title,
                    "folder": safe_title,
                    "filename": "question.pdf",
                    "path": str(question_pdf_path),
                    "zip_path": str(zip_question_path)
                })
            except Exception as e:
                print(f"Error generating question PDF for {job_title}: {str(e)}")
                errors_for_row.append({
                    "row": row_number,
                    "title": job_title,
                    "error": f"Failed to generate question PDF: {str(e)}"
                })

    except Exception as e:
        errors_for_row.append({
            "row": row_number,
            "title": job_title,
            "error": str(e)
        })

    return generated_files_for_row, errors_for_row

# Initialize FastAPI app
app = FastAPI(
    title="Resumer API",
    description="API for customizing resumes based on job descriptions using AI",
    version="1.0.0"
)

# Configure CORS
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
if ENVIRONMENT == "production":
    allowed_origins = [
        "https://easyhired.online",
        "https://www.easyhired.online",
        "https://cv-rusuland.vercel.app",
        "http://localhost:3000",
        "https://cv55.vercel.app"
    ]
    allow_credentials = True
else:
    # In development: explicitly allow localhost for frontend
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:5173",  # Vite default
        "http://127.0.0.1:5173",
        "https://cv55.vercel.app"
    ]
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Data models
class UserLogin(BaseModel):
    username: str
    password: str

class User(BaseModel):
    username: str

class Token(BaseModel):
    token: str
    user: User

class JobSubmission(BaseModel):
    job_description: str
    questions: Optional[List[str]] = None
    template: Optional[str] = None
    return_json: Optional[bool] = False
    # When True: generate only a cover letter (no resume PDF)
    # When False: generate both resume PDF and cover letter
    cover_letter_only: Optional[bool] = True

class TailoredResumeResponse(BaseModel):
    # May be omitted when only a cover letter is requested
    resume_url: Optional[str] = None
    cover_letter_url: Optional[str] = None
    answers: Optional[List[str]] = None
    json_path: Optional[str] = None
    text_path: Optional[str] = None
    notification: Optional[str] = None

class GoogleSheetsBatchSubmission(BaseModel):
    google_sheets_links: List[str]
    template: str

# Authentication functions
def load_users():
    with open("users.json", "r") as f:
        return json.load(f)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(name: str, password: str):
    users = load_users()
    for user in users:
        if user["username"] == name and user["password"] == password:
            return user
    return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if credentials is None:
        raise credentials_exception
    
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
    
    users = load_users()
    user = None
    for u in users:
        if u["username"] == username:
            user = u
            break
    
    if user is None:
        raise credentials_exception
    return user

def extract_google_sheet_id(url: str) -> Optional[str]:
    """Extract spreadsheet ID from Google Sheets URL."""
    # Handle various Google Sheets URL formats
    patterns = [
        r'/spreadsheets/d/([a-zA-Z0-9-_]+)',
        r'id=([a-zA-Z0-9-_]+)',
        r'/d/([a-zA-Z0-9-_]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def fetch_google_sheet_content(sheet_url: str) -> List[dict]:
    """Fetch content from Google Sheets and return as list of rows with Title and Description."""
    sheet_id = extract_google_sheet_id(sheet_url)
    if not sheet_id:
        raise ValueError("Invalid Google Sheets URL. Could not extract spreadsheet ID.")
    
    # Use CSV export URL (works for publicly shared sheets)
    # Format: https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}
    # If no gid specified, it exports the first sheet
    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    
    try:
        response = requests.get(export_url, timeout=10)
        response.raise_for_status()
        content = response.text
        
        # Parse CSV content
        import io
        import csv
        
        # Read CSV from string
        csv_reader = csv.DictReader(io.StringIO(content))
        
        rows = []
        for row in csv_reader:
            # Normalize column names (case-insensitive)
            normalized_row = {}
            for key, value in row.items():
                normalized_key = key.strip()
                normalized_row[normalized_key] = value.strip() if value else ''
            
            # Check if Title and Description columns exist (case-insensitive)
            title_key = None
            desc_key = None
            
            for key in normalized_row.keys():
                if key.lower() == 'title':
                    title_key = key
                elif key.lower() == 'description':
                    desc_key = key
            
            if title_key and desc_key:
                title = normalized_row[title_key]
                description = normalized_row[desc_key]
                
                # Skip empty rows
                if title and description:
                    row_data = {
                        "Title": title,
                        "Description": description
                    }
                    
                    # Add question columns if they exist
                    for key in normalized_row.keys():
                        if key.lower().startswith('question') and key.lower() != 'question':
                            q_value = normalized_row.get(key, '').strip()
                            if q_value:
                                row_data[key] = q_value
                    
                    rows.append(row_data)
        
        if not rows:
            raise ValueError("No valid rows found in Google Sheets. Make sure it has 'Title' and 'Description' columns with data.")
        
        return rows
        
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch Google Sheets content: {str(e)}. Make sure the sheet is publicly shared (Anyone with the link can view).")
    except Exception as e:
        raise ValueError(f"Error parsing Google Sheets: {str(e)}")

@app.get("/")
async def read_root():
    return {"message": "Resumer API is running"}

@app.get("/api-status")
async def get_api_status(current_user: dict = Depends(get_current_user)):
    """Get the current status of available AI APIs"""
    status_info = {
        "claude_available": claude_client is not None,
        "openai_available": openai_client is not None,
        "claude_credit_exhausted": model.credit_exhausted if hasattr(model, 'credit_exhausted') else False,
        "primary_api": "claude" if claude_client and not (model.credit_exhausted if hasattr(model, 'credit_exhausted') else False) else "openai" if openai_client else "none",
        "fallback_available": openai_client is not None if claude_client else False
    }
    return status_info

@app.options("/signin")
async def signin_options(request: Request):
    """Handle OPTIONS preflight requests for /signin"""
    origin = request.headers.get("origin")
    # Check if origin is allowed
    if origin in allowed_origins or "*" in allowed_origins:
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": origin if origin and origin in allowed_origins else allowed_origins[0] if allowed_origins else "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "Access-Control-Allow-Credentials": "true" if allow_credentials else "false",
                "Access-Control-Max-Age": "3600",
            }
        )
    return Response(status_code=403)

@app.post("/signin", response_model=Token)
async def signin(user_login: UserLogin):
    user = authenticate_user(user_login.username, user_login.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {
        "token": access_token, 
        "user": {"username": user["username"]}
    }

@app.post("/tailor-resume", response_model=TailoredResumeResponse)
async def tailor_resume_endpoint(job_data: JobSubmission, current_user: dict = Depends(get_current_user)):
    """Generate a tailored resume based on the job description."""
    try:
        # Check if user has access to the requested template
        user_role = current_user.get("role", "user")
        if user_role != "admin":
            allowed_template = current_user.get("allowed_template")
            if allowed_template and job_data.template.lower() != allowed_template.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You don't have permission to use template '{job_data.template}'. You can only use '{allowed_template}'."
                )
        
        cover_letter_only = job_data.cover_letter_only

        # Normalize template name to match filesystem (case-insensitive)
        template_name_normalized = normalize_template_name(job_data.template)
        template_file = f"resume_templates/{template_name_normalized}"
        json_path, tailored_resume = tailor_resume(job_data.job_description, model, template_file)

        # Convert JSON to text format
        text_path, _ = convert_json_to_text(tailored_resume)
        # Extract template name from the normalized file path for the output filename
        template_name = os.path.splitext(os.path.basename(template_name_normalized))[0] if template_name_normalized else "default"

        response: dict = {}

        # Generate resume PDF only when requested
        if not cover_letter_only:
            output_dir = Path("output")
            pdf_path = output_dir / f"{template_name}_resume.pdf"
            generate_pdf_from_json(tailored_resume, pdf_path)
            response["resume_url"] = f"/download/resume/{pdf_path.name}"

        # Generate cover letter (for both modes)
        cover_letter_path = None
        if tailored_resume:
            cover_letter_path = generate_cover_letter(tailored_resume, job_data.job_description, model, template_name)
            if cover_letter_path:
                response["cover_letter_url"] = f"/download/cover_letter/{cover_letter_path.name}"
        # Generate answers to questions if provided
        answers = None
        if job_data.questions and len(job_data.questions) > 0:
            answers = generate_question_answers(job_data.questions, job_data.job_description, tailored_resume, model)
            response["answers"] = answers
        
        # Include JSON and text paths if requested
        if job_data.return_json:
            response["json_path"] = str(json_path)
            response["text_path"] = str(text_path)
        
        # Check if Claude credits were exhausted and add notification
        if model.credit_exhausted:
            response["notification"] = "Your Claude AI credits have been used up. To ensure uninterrupted service, we've automatically switched to OpenAI for this request. You can continue generating resumes without any action required."
        
        return response
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in tailor_resume_endpoint: {str(e)}")
        print(f"Full traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error tailoring resume: {str(e)}")

@app.post("/tailor-resume-batch")
async def tailor_resume_batch_endpoint(
    file: UploadFile = File(...),
    template: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Generate multiple tailored resumes based on Excel file with Title and Description columns."""
    # Check if user has access to the requested template
    user_role = current_user.get("role", "user")
    if user_role != "admin":
        allowed_template = current_user.get("allowed_template")
        if allowed_template and template.lower() != allowed_template.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have permission to use template '{template}'. You can only use '{allowed_template}'."
            )
    
    # Validate file type
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an Excel file (.xlsx or .xls)"
        )
    
    # Save uploaded file temporarily
    temp_dir = tempfile.mkdtemp()
    temp_file_path = Path(temp_dir) / file.filename
    
    try:
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Read Excel file - handle both .xls and .xlsx formats
            file_ext = temp_file_path.suffix.lower()
            if file_ext == '.xls':
                # For .xls files, read directly with xlrd and convert to DataFrame
                # This bypasses pandas' version check for xlrd
                try:
                    import xlrd
                    workbook = xlrd.open_workbook(temp_file_path)
                    sheet = workbook.sheet_by_index(0)
                    
                    # Read headers from first row
                    headers = [str(sheet.cell_value(0, col)) for col in range(sheet.ncols)]
                    
                    # Read data rows
                    data = []
                    for row_idx in range(1, sheet.nrows):
                        row_data = [sheet.cell_value(row_idx, col) for col in range(sheet.ncols)]
                        data.append(row_data)
                    
                    # Create DataFrame
                    df = pd.DataFrame(data, columns=headers)
                except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Error reading .xls file: {str(e)}. Please ensure the file is a valid Excel file."
                    )
            else:
                # Use openpyxl engine for .xlsx files
                df = pd.read_excel(temp_file_path, engine='openpyxl')
            
            # Validate required columns
            required_columns = ['Title', 'Description']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Excel file must contain columns: {', '.join(required_columns)}. Missing: {', '.join(missing_columns)}"
                )
            
            # Find question columns (Question1, Question2, Question3, Question4)
            question_columns = []
            for col in df.columns:
                if col.strip().lower().startswith('question') and col.strip().lower() not in ['question']:
                    question_columns.append(col)
            # Sort question columns to maintain order
            question_columns.sort(key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 999)
            
            # Normalize template name to match filesystem (case-insensitive)
            template_name_normalized = normalize_template_name(template)
            template_name = os.path.splitext(os.path.basename(template_name_normalized))[0] if template_name_normalized else "default"
            template_file = f"resume_templates/{template_name_normalized}"
            
            # Create built_resume directory structure
            built_resume_dir = Path("built_resume")
            built_resume_dir.mkdir(exist_ok=True)
            
            # Create temporary directory for batch outputs (for ZIP)
            batch_output_dir = Path(temp_dir) / "batch_output"
            batch_output_dir.mkdir(exist_ok=True)
            
            generated_files = []
            errors = []

            # Build row payloads (avoid passing pandas objects to threads)
            row_payloads = []
            for index, row in df.iterrows():
                job_title = str(row.get('Title', '')).strip()
                job_description = str(row.get('Description', '')).strip()

                # Skip empty rows
                if not job_title or not job_description or job_title == 'nan' or job_description == 'nan':
                    continue

                # Extract questions from question columns
                questions = []
                for q_col in question_columns:
                    q_value = str(row.get(q_col, '')).strip()
                    if q_value and q_value != 'nan':
                        questions.append(q_value)

                safe_title = "".join(c for c in job_title if c.isalnum() or c in (' ', '-', '_', '.')).strip()
                safe_title = safe_title.replace(' ', '_')
                safe_title = "".join(c for c in safe_title if c.isalnum() or c in ('_', '-', '.'))[:100]

                row_payloads.append({
                    "row_number": index + 1,
                    "job_title": job_title,
                    "job_description": job_description,
                    "questions": questions,
                    "safe_title": safe_title,
                    "file_prefix": f"{safe_title}_{index + 1}"
                })

            # Run rows concurrently (one request; multiple worker threads)
            sem = asyncio.Semaphore(max(1, BATCH_MAX_CONCURRENCY))

            async def run_one(payload: dict):
                async with sem:
                    return await asyncio.to_thread(
                        _process_one_batch_job,
                        row_number=payload["row_number"],
                        job_title=payload["job_title"],
                        job_description=payload["job_description"],
                        questions=payload["questions"],
                        safe_title=payload["safe_title"],
                        built_resume_dir=built_resume_dir,
                        batch_output_dir=batch_output_dir,
                        template_file=template_file,
                        model=model,
                        file_prefix=payload["file_prefix"]
                    )

            results = await asyncio.gather(*(run_one(p) for p in row_payloads))
            for files_for_row, errors_for_row in results:
                generated_files.extend(files_for_row)
                errors.extend(errors_for_row)
            
            if not generated_files:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No valid rows found in Excel file or all rows failed to process"
                )
            
            # Create zip file with folder structure
            zip_filename = f"batch_resumes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            zip_path = Path(temp_dir) / zip_filename
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Walk through batch_output_dir to maintain folder structure
                for root, dirs, files in os.walk(batch_output_dir):
                    for file in files:
                        file_path = Path(root) / file
                        # Get relative path from batch_output_dir to maintain structure
                        arcname = file_path.relative_to(batch_output_dir)
                        zipf.write(file_path, arcname)
            
            # Move zip to output directory for download
            output_zip_path = OUTPUT_DIR / zip_filename
            shutil.move(zip_path, output_zip_path)
            
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            response = {
                "zip_url": f"/download/batch/{zip_filename}",
                "files_count": len(generated_files),
                "errors": errors if errors else None
            }
            
            # Check if Claude credits were exhausted and add notification
            if model.credit_exhausted:
                response["notification"] = "Your Claude AI credits have been used up. To ensure uninterrupted service, we've automatically switched to OpenAI for this request. You can continue generating resumes without any action required."
            
            return response
        
    except HTTPException:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in tailor_resume_batch_endpoint: {str(e)}")
        print(f"Full traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error processing batch: {str(e)}")

@app.post("/tailor-resume-batch-google-sheets")
async def tailor_resume_batch_google_sheets_endpoint(
    batch_data: GoogleSheetsBatchSubmission,
    current_user: dict = Depends(get_current_user)
):
    """Generate multiple tailored resumes based on Google Sheets links."""
    # Check if user has access to the requested template
    user_role = current_user.get("role", "user")
    if user_role != "admin":
        allowed_template = current_user.get("allowed_template")
        if allowed_template and batch_data.template.lower() != allowed_template.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have permission to use template '{batch_data.template}'. You can only use '{allowed_template}'."
            )
    
    if not batch_data.google_sheets_links or len(batch_data.google_sheets_links) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one Google Sheets link is required"
        )
    
    # Normalize template name to match filesystem (case-insensitive)
    template_name_normalized = normalize_template_name(batch_data.template)
    template_file = f"resume_templates/{template_name_normalized}"
    template_name = os.path.splitext(os.path.basename(template_name_normalized))[0] if template_name_normalized else "default"
    
    # Create built_resume directory structure
    built_resume_dir = Path("built_resume")
    built_resume_dir.mkdir(exist_ok=True)
    
    # Create temporary directory for batch outputs (for ZIP)
    temp_dir = tempfile.mkdtemp()
    batch_output_dir = Path(temp_dir) / "batch_output"
    batch_output_dir.mkdir(exist_ok=True)
    
    generated_files = []
    errors = []
    row_index = 0
    row_payloads = []
    
    try:
        # Process each Google Sheets link
        for sheet_index, sheet_url in enumerate(batch_data.google_sheets_links):
            try:
                # Fetch all rows from Google Sheets
                sheet_rows = fetch_google_sheet_content(sheet_url)
                
                # Process each row from the sheet
                for row_data in sheet_rows:
                    row_index += 1
                    job_title = row_data.get('Title', '').strip()
                    job_description = row_data.get('Description', '').strip()

                    if not job_title or not job_description:
                        continue

                    # Extract questions from row data (find question columns)
                    questions = []
                    question_keys = []
                    for key in row_data.keys():
                        if key.lower().startswith('question') and key.lower() != 'question':
                            question_keys.append(key)
                    question_keys.sort(key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 999)
                    for q_key in question_keys:
                        q_value = str(row_data.get(q_key, '')).strip()
                        if q_value and q_value != 'nan':
                            questions.append(q_value)

                    safe_title = "".join(c for c in job_title if c.isalnum() or c in (' ', '-', '_', '.')).strip()
                    safe_title = safe_title.replace(' ', '_')
                    safe_title = "".join(c for c in safe_title if c.isalnum() or c in ('_', '-', '.'))[:100]

                    row_payloads.append({
                        "row_number": row_index,
                        "job_title": job_title,
                        "job_description": job_description,
                        "questions": questions,
                        "safe_title": safe_title,
                        "file_prefix": f"{safe_title}_{row_index}"
                    })
            
            except Exception as e:
                errors.append({
                    "row": sheet_index + 1,
                    "title": sheet_url[:50] if sheet_url else "Unknown",
                    "error": f"Failed to process Google Sheet: {str(e)}"
                })
                continue

        # Run rows concurrently (one request; multiple worker threads)
        sem = asyncio.Semaphore(max(1, BATCH_MAX_CONCURRENCY))

        async def run_one(payload: dict):
            async with sem:
                return await asyncio.to_thread(
                    _process_one_batch_job,
                    row_number=payload["row_number"],
                    job_title=payload["job_title"],
                    job_description=payload["job_description"],
                    questions=payload["questions"],
                    safe_title=payload["safe_title"],
                    built_resume_dir=built_resume_dir,
                    batch_output_dir=batch_output_dir,
                    template_file=template_file,
                    model=model,
                    file_prefix=payload["file_prefix"]
                )

        results = await asyncio.gather(*(run_one(p) for p in row_payloads))
        for files_for_row, errors_for_row in results:
            generated_files.extend(files_for_row)
            errors.extend(errors_for_row)
        
        if not generated_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid rows found in Google Sheets or all rows failed to process"
            )
        
        # Create zip file with folder structure
        zip_filename = f"batch_resumes_googlesheets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = Path(temp_dir) / zip_filename
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(batch_output_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(batch_output_dir)
                    zipf.write(file_path, arcname)
        
        # Move zip to output directory for download
        output_zip_path = OUTPUT_DIR / zip_filename
        shutil.move(zip_path, output_zip_path)
        
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return {
            "zip_url": f"/download/batch/{zip_filename}",
            "files_count": len(generated_files),
            "errors": errors if errors else None
        }
    
    except HTTPException:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in tailor_resume_batch_google_sheets_endpoint: {str(e)}")
        print(f"Full traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error processing Google Sheets batch: {str(e)}")

@app.get("/download/resume/{filename}")
async def download_resume(filename: str, mode: Optional[str] = None):
    """Download a generated resume."""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Extract template name from the filename
    template_name = file_path.name.split("_resume")[0] if "_resume" in file_path.name else "tailored"
    
    if mode == "download":
        return FileResponse(
            path=file_path,
            filename=f"{template_name}_resume.pdf",
            media_type="application/pdf"
        )
    else:
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline"}
        )
    
@app.get("/download/cover_letter/{filename}")
async def download_cover_letter(filename: str, mode: Optional[str] = None):
    """Download a generated cover letter."""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Cover letter not found")
    
    # Extract template name from the filename
    template_name = file_path.name.split("_cover_letter")[0] if "_cover_letter" in file_path.name else "default"
    
    if mode == "download":
        return FileResponse(
            path=file_path,
            filename=f"{template_name}_cover_letter.pdf",
            media_type="application/pdf"
        )
    else:
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline"}
        )

@app.get("/download/batch/{filename}")
async def download_batch(filename: str):
    """Download a batch zip file."""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Batch file not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/zip"
    )

@app.get("/templates")
async def get_templates(current_user: dict = Depends(get_current_user)):
    """Get a list of available templates."""
    all_templates = os.listdir("resume_templates")
    
    # Filter templates based on user role
    user_role = current_user.get("role", "user")
    
    if user_role == "admin":
        # Admin can see all templates
        return all_templates
    else:
        # Regular users can only see their allowed template
        allowed_template = current_user.get("allowed_template")
        if allowed_template:
            # Normalize the allowed template name to match filesystem
            normalized_allowed = normalize_template_name(allowed_template)
            # Check if normalized template exists in the list (case-insensitive)
            for template in all_templates:
                if template.lower() == normalized_allowed.lower():
                    return [template]
        # If no allowed_template is set or not found, return empty list
        return []

@app.get("/cover_letter/content/{filename}")
async def get_cover_letter_content(filename: str, current_user: dict = Depends(get_current_user)):
    """Get the markdown content of a cover letter."""
    # Convert PDF filename to MD filename
    md_filename = filename.replace(".pdf", ".md")
    file_path = OUTPUT_DIR / md_filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Cover letter markdown not found")
    
    try:
        with open(file_path, "r") as f:
            content = f.read()
        
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading cover letter content: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)

from venv import logger

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import uuid
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
import json
from datetime import datetime, timedelta
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

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

# Configure OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set")

# Strip any whitespace/newlines from the API key
OPENAI_API_KEY = OPENAI_API_KEY.strip()

client = OpenAI(api_key=OPENAI_API_KEY)

# Create a model-like object that mimics Gemini's interface for compatibility
class OpenAIModelWrapper:
    def __init__(self, client):
        self.client = client
        self.model = "gpt-4o-mini"  # Default OpenAI model; can be changed to gpt-4, gpt-3.5-turbo, etc.
    
    def generate_content(self, prompt):
        """Mimics Gemini's generate_content method for compatibility"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            
            # Create a response object that mimics Gemini's response
            class Response:
                def __init__(self, text):
                    self.text = text
            
            # Check if response has content
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                if content:
                    return Response(content)
                else:
                    raise Exception("OpenAI API returned empty content")
            else:
                raise Exception("OpenAI API returned no choices")
                
        except Exception as e:
            # Log the error for debugging
            import traceback
            error_details = traceback.format_exc()
            print(f"OpenAI API Error: {str(e)}")
            print(f"Error details: {error_details}")
            raise Exception(f"OpenAI API error: {str(e)}")

model = OpenAIModelWrapper(client)

# Create output directory for intermediate files
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

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
        "https://cv87.vercel.app"
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
        "https://cv-rusuland.vercel.app",
        "https://cv87.vercel.app"
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

@app.get("/")
async def read_root():
    return {"message": "Resumer API is running"}

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
            if allowed_template and job_data.template != allowed_template:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You don't have permission to use template '{job_data.template}'. You can only use '{allowed_template}'."
                )
        
        cover_letter_only = job_data.cover_letter_only

        # Tailor the resume based on the job description
        template_file = f"resume_templates/{job_data.template}"
        json_path, tailored_resume = tailor_resume(job_data.job_description, model, template_file)

        # Convert JSON to text format
        text_path, _ = convert_json_to_text(tailored_resume)
        # Extract template name from the file path for the output filename
        template_name = os.path.splitext(os.path.basename(job_data.template))[0] if job_data.template else "default"

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
        
        return response
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in tailor_resume_endpoint: {str(e)}")
        print(f"Full traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error tailoring resume: {str(e)}")

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
        if allowed_template and allowed_template in all_templates:
            return [allowed_template]
        else:
            # If no allowed_template is set, return empty list
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

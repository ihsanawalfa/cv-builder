# Resumer API

An AI-powered REST API service that automatically tailors resumes and generates cover letters based on job descriptions using OpenAI's GPT models.

## Features

- **Resume Tailoring**: Customizes your resume content based on specific job descriptions
- **Cover Letter Generation**: Creates targeted cover letters matching the job requirements
- **Question Answering**: Generates relevant answers for job application questions
- **Multiple Output Formats**: Supports PDF, JSON, and plain text outputs

## Prerequisites

- Python 3.8+
- pip
- OpenAI API key

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd resume-build-backend
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
```

3. Activate the virtual environment:
   - **Windows (PowerShell):**
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - **Windows (Command Prompt):**
     ```cmd
     venv\Scripts\activate.bat
     ```
   - **Linux/Mac:**
     ```bash
     source venv/bin/activate
     ```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Set up environment variables:
   - Create a `.env` file in the root directory (if not already present)
   - Add the following variables:
     ```
     OPENAI_API_KEY=your_openai_api_key_here
     SECRET_KEY=your_secret_key_here
     ENVIRONMENT=development
     ```

## Running the Project

### Option 1: Using Python directly
```bash
python main.py
```

### Option 2: Using uvicorn directly
```bash
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

The API will be available at:
- **Local:** http://localhost:5000
- **API Documentation:** http://localhost:5000/docs (Swagger UI)
- **Alternative Docs:** http://localhost:5000/redoc

## API Endpoints

### Authentication
- `POST /signin` - Sign in and get JWT token
  - Body: `{"username": "rusuland9@gmail.com", "password": "20030807"}`

### Resume Operations
- `POST /tailor-resume` - Generate tailored resume (requires authentication)
- `GET /templates` - Get list of available templates (requires authentication)
- `GET /download/resume/{filename}` - Download generated resume PDF
- `GET /download/cover_letter/{filename}` - Download generated cover letter PDF
- `GET /cover_letter/content/{filename}` - Get cover letter markdown content

## Default User Credentials

The project includes a default user in `users.json`:
- Username: `rusuland9@gmail.com`
- Password: `20030807`

**Note:** Change these credentials in production!
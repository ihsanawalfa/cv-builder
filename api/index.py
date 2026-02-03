from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
from pathlib import Path

# Add the parent directory to the Python path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

# Import the main app from the parent directory
from main import app

# This is the entry point for Vercel
# The app is already configured in main.py
handler = app

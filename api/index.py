"""
Vercel serverless function entry point.
This file serves as the main entry point for the Flask application on Vercel.
"""

import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Flask app
from app import app

# Vercel expects the app to be named 'app' or 'application'
# The app variable is already exported from app.py

"""
Vercel serverless entry point for the Study Planner app.

Vercel imports this file and maps all incoming requests to our Flask app.
"""
import os
import sys

# Ensure the project root is importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel serverless handler (Vercel's Python runtime expects a WSGI app)
# Use the Flask app object directly - Vercel's @vercel/python adapter
# will wrap it as needed.
handler = app

# Some Vercel adapters look for a callable named `app` directly.
# Providing both names maximizes compatibility.
app_ = app


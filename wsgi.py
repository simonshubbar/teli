"""
WSGI entry point for PythonAnywhere.

PythonAnywhere doesn't run app.py directly — instead it uses WSGI
(Web Server Gateway Interface), a standard way for web servers to
talk to Python apps. This file imports your Flask app and makes sure
the database is ready before handling any requests.

You'll point PythonAnywhere's WSGI configuration to this file.
"""

from app import app
from database import init_db

# Create database tables if they don't exist yet.
# This runs once when PythonAnywhere loads your app.
init_db()

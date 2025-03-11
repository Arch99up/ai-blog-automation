#!/bin/bash
# Ensure the SQLite database and tables are created before starting the app
python -c "from app import init_db; init_db()"

# Start the Flask application using Gunicorn
gunicorn -b 0.0.0.0:10000 app:app

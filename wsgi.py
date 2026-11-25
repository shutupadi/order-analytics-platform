# Entry point for gunicorn on EC2:  gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app
from app.api import create_app

app = create_app()

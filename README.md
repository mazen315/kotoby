# Kotoby - Deployment

This repository is a Flask app for selling digital books.

Quick local run:

```bash
python -m venv venv
venv\Scripts\Activate.ps1    # Windows PowerShell
pip install -r requirements.txt
$env:SECRET_KEY='your_secret_here'; $env:FLASK_DEBUG='True'; python app.py
```

Deploy options (free):

- Replit: Import the repo into Replit, set `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` in Secrets, and use `gunicorn app:app` or set `run` to `python app.py`.
- PythonAnywhere: Upload files, set up a WSGI web app pointing to `app.app`, and install requirements in the virtualenv.

Notes:
- For production use a proper DB (Postgres) and secure storage for uploads.
- Add environment variables for `SECRET_KEY`, `DATABASE_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`.

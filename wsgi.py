"""Entry point. Dev: `python wsgi.py`. Production: `gunicorn wsgi:app`."""
import os

from planner import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)

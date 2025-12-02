"""
Remove database and create a new one based on models.py
Usage (from project root): python reset_db.py
"""

import os
from clinvar_anno_app.models import db
from clinvar_anno_app.app import app


def reset_database():
    """Drops all existing tables and recreates a fresh SQLite database."""
    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    print(f"Using database: {db_path}")

    if os.path.exists(db_path):
        os.remove(db_path)
        print("Existing database removed.")

    with app.app_context():
        db.create_all()
        print("New database created successfully.")


if __name__ == '__main__':
    reset_database()

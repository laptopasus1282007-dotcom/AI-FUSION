#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Collect static files into staticfiles/
python manage.py collectstatic --no-input

# Apply database migrations
python manage.py migrate

# Seed default bug categories and educational curated videos
python manage.py seed_data

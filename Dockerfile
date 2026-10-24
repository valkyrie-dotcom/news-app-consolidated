# Use the official Python image (Django 6 needs Python 3.12 or later)
FROM python:3.12-slim

# Tools needed to install mysqlclient from requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc pkg-config default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the work directory
WORKDIR /app

# Install the Python packages first, so this step is cached between builds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project files into the work directory
COPY . .

# Inside the container the app uses SQLite, so no MariaDB server is needed.
# ALLOWED_HOSTS=* lets the site be opened from outside the container.
ENV DB_ENGINE=django.db.backends.sqlite3 \
    DB_NAME=/app/db.sqlite3 \
    ALLOWED_HOSTS=* \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Create the tables (and the role groups), then start the server
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]

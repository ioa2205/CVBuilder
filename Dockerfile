# Use an official Python runtime as a parent image
FROM python:3.10-slim-bullseye

# Set environment variables to prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

# Install WeasyPrint system dependencies (The tricky part!)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    python3-cffi \
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    fontconfig \
    # Cleanup afterwards
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the environment
WORKDIR /app

# Copy ONLY the requirements file first (for better caching)
COPY requirements.txt ./

# Install all Python packages listed in requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy ALL your other code (main.py, templates/, etc.) into the environment
COPY . .

# This is the command that Railway will run to start your bot
CMD ["python", "main.py"]
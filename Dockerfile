# Use lightweight Python
FROM python:3.12-slim

# Set work directory
WORKDIR /app

# Copy project into container
COPY . /app

# Install git (optional) + clean apt cache
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the default Flask port
EXPOSE 5000

# Command to run the Flask app
CMD ["python", "clinvar_anno_app/app.py"]

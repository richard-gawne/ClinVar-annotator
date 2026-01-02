# Use lightweight Python
FROM python:3.12-slim

# Set work directory
WORKDIR /app

# Copy project into container
COPY . /app

# Upgrade pip
RUN pip install --upgrade pip

# Install the package
RUN pip install .

# Expose the default Flask port
EXPOSE 5000

# Command to run the Flask app
CMD ["python", "-m", "clinvar_anno_app.app"]

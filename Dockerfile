# Use Miniconda base image
FROM continuumio/miniconda3:latest

# Set working directory
WORKDIR /app

# Copy environment yaml
COPY environment.yml .

# Create conda environment
RUN conda env create -f environment.yml \
    && conda clean -afy

# Make sure the conda environment is activated by default
SHELL ["conda", "run", "-n", "clinvar_anno_env", "/bin/bash", "-c"]

# Copy project files
COPY . .

# Upgrade pip and install ClinVar-annotator package inside conda env
RUN pip install --upgrade pip \
    && pip install .

# Expose application port
EXPOSE 5000

# Run app with Gunicorn
CMD ["conda", "run", "--no-capture-output", "-n", "clinvar_anno_env", \
     "gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", \
     "clinvar_anno_app.app:app"]

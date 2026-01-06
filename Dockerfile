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

# Copy the rest of the project
COPY . .

# Upgrade pip inside the conda env
RUN pip install --upgrade pip

# Install ClinVar-annotator package
RUN pip install .

# Expose Flask port
EXPOSE 5000

# Run the Flask app inside the conda environment
CMD ["conda", "run", "--no-capture-output", "-n", "clinvar_anno_env", "python", "-m", "clinvar_anno_app.app"]

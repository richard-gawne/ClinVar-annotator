# Installation
This guide describes how to install `ClinVar-annotator` on Linux systems.

Instructions for installation using `Docker` are provided at the end of this guide.
## Pre-requisites
Required:
- `Python 3.12`
- `Git`
- `Conda` (`Miniconda` or `Anaconda`)

Optional:
- `Docker`
## Clone the repository (`main` branch)
```
git clone https://github.com/richard-gawne/ClinVar-annotator.git
cd ClinVar-annotator
```
## Create and activate the `conda` environment
```
conda env create -f environment.yml
conda activate clinvar_anno_env
```
## Install the `ClinVar-annotator` package
```
pip install .
```
## Run the `Flask` application
```
python -m clinvar_anno_app.app
```
Access the application at: `http://localhost:5000`
## Installation with `Docker`
### Build the `Docker` image
```
docker build -t clinvar-annotator .
```
### Run the application in the container
```
docker run -p 5000:5000 clinvar-annotator
```
Access the application at: `http://localhost:5000`

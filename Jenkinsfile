pipeline {
    agent any

    environment {
        CONDA_PREFIX = '/usr/local/miniconda3'
        CONDA_ENV_NAME = 'clinvar_anno_env'
        PIP_DISABLE_PIP_VERSION_CHECK = '1'
        PYTHONUNBUFFERED = '1'
        DOCKER_IMAGE_NAME = 'clinvar-annotator'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Set Up Conda Environment') {
            steps {
                sh '''
                bash -c "
                    source ${CONDA_PREFIX}/etc/profile.d/conda.sh

                    # Create env only if it doesn't exist
                    if ! conda env list | grep -q ${CONDA_ENV_NAME}; then
                        echo 'Creating conda environment...'
                        conda env create -f environment.yml
                    else
                        echo 'Conda environment already exists.'
                    fi
                "
                '''
            }
        }

        stage('Install Package') {
            steps {
                sh '''
                bash -c "
                    source ${CONDA_PREFIX}/etc/profile.d/conda.sh
                    conda activate ${CONDA_ENV_NAME}

                    pip install --upgrade pip
                    pip install .
                "
                '''
            }
        }

        stage('Run Tests') {
            steps {
                sh '''
                bash -c "
                    source ${CONDA_PREFIX}/etc/profile.d/conda.sh
                    conda activate ${CONDA_ENV_NAME}

                    echo 'Running pytest...'
                    pytest --maxfail=1 --disable-warnings --cov=clinvar_anno_app tests/
                "
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                sh '''
                    echo "Building Docker image..."
                    docker build -t ${DOCKER_IMAGE_NAME}:latest .
                '''
            }
        }
    }

    post {
        always {
            echo "✔ Pipeline completed."
        }
    }
}

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

                    # Remove existing environment if it exists
                    conda env remove -n ${CONDA_ENV_NAME} -y || true

                    # Create fresh environment
                    conda env create -f environment.yml
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
                echo 'Building Docker image...'
                sh '''
                    # Use sudo to ensure Jenkins can access the Docker daemon
                    sudo docker build -t clinvar-annotator:latest .
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

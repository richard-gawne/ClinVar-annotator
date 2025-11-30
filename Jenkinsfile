pipeline {
    agent any

    environment {
        CONDA_PREFIX = '/usr/local/miniconda3'   // Path to conda installation
        CONDA_ENV_NAME = 'clinvar_anno_env'     // Your environment
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
                conda env remove -n ${CONDA_ENV_NAME} || true
                conda env create -f environment.yml
                "
                '''
            }
        }

        stage('Install Package (pip install .)') {
            steps {
                sh '''
                bash -c "
                source ${CONDA_PREFIX}/etc/profile.d/conda.sh
                conda activate ${CONDA_ENV_NAME}
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
                pytest --cov=clinvar_anno_app tests/
                "
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                sh '''
                docker build -t ${DOCKER_IMAGE_NAME}:latest .
                '''
            }
        }
    }

    post {
        always {
            echo "Pipeline completed."
        }
    }
}

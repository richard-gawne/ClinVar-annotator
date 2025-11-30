pipeline {
    agent any

    environment {
        VENV_DIR = ".venv"
        PIP_DISABLE_PIP_VERSION_CHECK = "1"
        PYTHONUNBUFFERED = "1"
        DOCKER_IMAGE_NAME = "clinvar-annotator"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Set Up Python Environment') {
            steps {
                sh '''
                python3 -m venv ${VENV_DIR}
                . ${VENV_DIR}/bin/activate
                pip install --upgrade pip
                pip install -r requirements.txt
                pip install pytest pytest-cov
                '''
            }
        }

        stage('Run Tests') {
            steps {
                sh '''
                . ${VENV_DIR}/bin/activate
                pytest --cov=clinvar_anno_app tests/
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

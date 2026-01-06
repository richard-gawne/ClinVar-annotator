pipeline {
    agent any

    options {
        timeout(time: 20, unit: 'MINUTES')
    }

    environment {
        CONDA_PREFIX = '/usr/local/miniconda3'
        CONDA_ENV_NAME = 'clinvar_anno_env'
        PIP_DISABLE_PIP_VERSION_CHECK = '1'
        PYTHONUNBUFFERED = '1'
        CODECOV_TOKEN = credentials('0b1c51a0-423e-4a70-ab29-4629bbf70d79')
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
                source ${CONDA_PREFIX}/etc/profile.d/conda.sh

                # Update env if it exists, otherwise create it
                conda env update -n ${CONDA_ENV_NAME} -f environment.yml || \
                conda env create -n ${CONDA_ENV_NAME} -f environment.yml
                '''
            }
        }

        stage('Install Package') {
            steps {
                sh '''
                source ${CONDA_PREFIX}/etc/profile.d/conda.sh
                conda activate ${CONDA_ENV_NAME}

                pip install --upgrade pip
                pip install .
                '''
            }
        }

        stage('Run Tests') {
            steps {
                sh '''
                source ${CONDA_PREFIX}/etc/profile.d/conda.sh
                conda activate ${CONDA_ENV_NAME}

                pytest --maxfail=1 \
                       --disable-warnings \
                       --cov=clinvar_anno_core \
                       --cov=clinvar_anno_app \
                       --cov-report=xml \
                       tests/
                '''
            }
        }

        stage('Upload Coverage to Codecov') {
            steps {
                sh '''
                curl -Os https://uploader.codecov.io/latest/linux/codecov
                chmod +x codecov
                ./codecov -t ${CODECOV_TOKEN} -f coverage.xml
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

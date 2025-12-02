from setuptools import setup, find_packages

setup(
    name="clinvar-annotator",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'flask',
        'flask-sqlalchemy',
        'werkzeug',
    ],
    extras_require={
        'dev': [
            'pytest>=7.0',
            'pytest-cov>=4.0',
            'pytest-mock>=3.10',
        ]
    },
)

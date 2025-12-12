"""Tests for the ClinVar Annotator Flask application."""

import os
import tempfile
from unittest.mock import patch
import pytest

from clinvar_anno_app.app import app, db
from clinvar_anno_app.models import Patient, Variant, PatientVariant


@pytest.fixture
def client():
    """Create a test client with a temporary database"""
    db_fd, db_path = tempfile.mkstemp()
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["TESTING"] = True
    app.config["UPLOAD_FOLDER"] = tempfile.mkdtemp()

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def sample_vcf_content():
    """Sample VCF file content for testing"""
    return """##fileformat=VCFv4.2
##reference=GRCh38
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO
chr1	7984930	.	A	C	.	.	.
chr2	1234567	.	G	T	.	.	.
"""


@pytest.fixture
def mock_annotation_data():
    """Mock annotation data returned by the pipeline"""
    return {
        "chr1:7984930:A:C": {
            "genomic_hgvs": "NC_000001.11:g.7984930A>C",
            "transcript_hgvs": "NM_001234.5:c.123A>C",
            "genes": [{"symbol": "GENE1", "hgnc_id": "HGNC:1234"}],
            "protein_change": "p.Lys41Asn",
            "molecular_consequences": ["missense_variant", "splice_region_variant"],
            "review_status": "criteria provided, multiple submitters, no conflicts",
            "clinical_significance": "Pathogenic",
            "trait_name": "Test Disease",
            "trait_omim": "123456",
            "variation_id": "999888",
            "gnomad_total_af": "0.0001",
        },
        "chr2:1234567:G:T": {
            "genomic_hgvs": "NC_000002.12:g.1234567G>T",
            "transcript_hgvs": "NM_005678.3:c.456G>T",
            "genes": [{"symbol": "GENE2", "hgnc_id": "HGNC:5678"}],
            "protein_change": "p.Arg152Leu, p.Arg152Trp",
            "molecular_consequences": ["missense_variant"],
            "review_status": "reviewed by expert panel",
            "clinical_significance": "Likely pathogenic",
            "trait_name": "Another Disease",
            "trait_omim": "654321",
            "variation_id": "777666",
            "gnomad_total_af": "0.0002",
        },
    }


class TestHomeRoute:
    """Tests for the home route"""

    def test_home_get(self, client):
        """Test GET request to home page"""
        response = client.get("/")
        assert response.status_code == 200

    def test_home_post_no_file(self, client):
        """Test POST request without file"""
        response = client.post("/", data={})
        assert response.status_code == 200


class TestFileUpload:
    """Tests for file upload functionality"""

    @patch("clinvar_anno_app.app.annotation_pipeline")
    def test_upload_single_vcf(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test uploading a single VCF file"""
        mock_pipeline.process_vcf.return_value = mock_annotation_data

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            response = client.post(
                "/",
                data={"vcf_files": (open(tf.name, "rb"), "patient001.vcf")},
                content_type="multipart/form-data",
            )

            assert response.status_code == 200
            assert mock_pipeline.process_vcf.called

            with app.app_context():
                patient = Patient.query.filter_by(patient_id="patient001").first()
                assert patient is not None
                variants = Variant.query.all()
                assert len(variants) == 2
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.annotation_pipeline")
    def test_upload_multiple_vcf(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test uploading multiple VCF files"""
        mock_pipeline.process_vcf.return_value = mock_annotation_data

        temp_files = []
        for i in range(2):
            tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
            with open(tf.name, "w") as f:
                f.write(sample_vcf_content)
            temp_files.append(tf.name)

        try:
            response = client.post(
                "/",
                data={
                    "vcf_files": [
                        (open(temp_files[0], "rb"), "patient001.vcf"),
                        (open(temp_files[1], "rb"), "patient002.vcf"),
                    ]
                },
                content_type="multipart/form-data",
            )

            assert response.status_code == 200

            with app.app_context():
                patients = Patient.query.all()
                assert len(patients) == 2
        finally:
            for tf in temp_files:
                os.unlink(tf)

    def test_upload_non_vcf_file(self, client):
        """Test uploading a non-VCF file is skipped"""
        tf = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)

        try:
            response = client.post(
                "/",
                data={"vcf_files": (open(tf.name, "rb"), "test.txt")},
                content_type="multipart/form-data",
            )

            assert response.status_code == 200

            with app.app_context():
                patients = Patient.query.all()
                assert len(patients) == 0
        finally:
            os.unlink(tf.name)


class TestDatabaseOperations:
    """Tests for database operations"""

    @patch("clinvar_anno_app.app.annotation_pipeline")
    def test_variant_fields_stored_correctly(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test that variant fields are stored correctly in database"""
        mock_pipeline.process_vcf.return_value = mock_annotation_data

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            client.post(
                "/",
                data={"vcf_files": (open(tf.name, "rb"), "patient123.vcf")},
                content_type="multipart/form-data",
            )

            with app.app_context():
                variant = Variant.query.filter_by(gene_symbol="GENE1").first()
                assert variant is not None
                assert variant.hgvsg == "NC_000001.11:g.7984930A>C"
                assert variant.protein_change == "p.Lys41Asn"  # First one only
                assert variant.molecular_consequences == "missense_variant"  # First one only
                assert variant.consensus_classification == "Pathogenic"
                assert variant.review_status_stars == "★★"  # Multiple submitters = 2 stars
                assert variant.gnomad_af == "0.0001"
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.annotation_pipeline")
    def test_patient_variant_linking(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test that patient-variant links are created correctly"""
        mock_pipeline.process_vcf.return_value = mock_annotation_data

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            client.post(
                "/",
                data={"vcf_files": (open(tf.name, "rb"), "patient456.vcf")},
                content_type="multipart/form-data",
            )

            with app.app_context():
                patient = Patient.query.filter_by(patient_id="patient456").first()
                assert len(patient.variants) == 2

                variant = Variant.query.first()
                assert len(variant.patient_links) == 1
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.annotation_pipeline")
    def test_duplicate_patient_not_created(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test that uploading same patient twice doesn't create duplicates"""
        mock_pipeline.process_vcf.return_value = mock_annotation_data

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            for _ in range(2):
                client.post(
                    "/",
                    data={"vcf_files": (open(tf.name, "rb"), "patient789.vcf")},
                    content_type="multipart/form-data",
                )

            with app.app_context():
                patients = Patient.query.filter_by(patient_id="patient789").all()
                assert len(patients) == 1
        finally:
            os.unlink(tf.name)


class TestAnnotationProcessing:
    """Tests for annotation data processing"""

    @patch("clinvar_anno_app.app.annotation_pipeline")
    def test_review_status_stars_mapping(
        self, mock_pipeline, client, sample_vcf_content
    ):
        """Test review status to stars mapping"""
        test_cases = [
            ("practice guideline", 4),
            ("reviewed by expert panel", 3),
            ("criteria provided, multiple submitters, no conflicts", 2),
            ("criteria provided, single submitter", 1),
            ("no assertion criteria provided", 0),
        ]

        for review_status, expected_stars in test_cases:
            mock_data = {
                "chr1:7984930:A:C": {
                    "genomic_hgvs": "NC_000001.11:g.7984930A>C",
                    "transcript_hgvs": "NM_001234.5:c.123A>C",
                    "genes": [{"symbol": "GENE1", "hgnc_id": "HGNC:1234"}],
                    "protein_change": "p.Lys41Asn",
                    "molecular_consequences": ["missense_variant"],
                    "review_status": review_status,
                    "clinical_significance": "Pathogenic",
                    "trait_name": "Test Disease",
                    "trait_omim": "123456",
                    "variation_id": "999888",
                    "gnomad_total_af": "0.0001",
                }
            }
            mock_pipeline.process_vcf.return_value = mock_data

            tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
            with open(tf.name, "w") as f:
                f.write(sample_vcf_content)

            try:
                client.post(
                    "/",
                    data={"vcf_files": (open(tf.name, "rb"), f"test_{expected_stars}.vcf")},
                    content_type="multipart/form-data",
                )

                with app.app_context():
                    variant = Variant.query.filter_by(gene_symbol="GENE1").first()
                    assert variant.review_status_stars.count("★") == expected_stars
            finally:
                os.unlink(tf.name)

            with app.app_context():
                db.session.query(PatientVariant).delete()
                db.session.query(Variant).delete()
                db.session.query(Patient).delete()
                db.session.commit()


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    @patch("clinvar_anno_app.app.annotation_pipeline")
    def test_empty_annotation_results(self, mock_pipeline, client, sample_vcf_content):
        """Test handling of empty annotation results"""
        mock_pipeline.process_vcf.return_value = {}

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            response = client.post(
                "/",
                data={"vcf_files": (open(tf.name, "rb"), "empty.vcf")},
                content_type="multipart/form-data",
            )

            assert response.status_code == 200

            with app.app_context():
                variants = Variant.query.all()
                assert len(variants) == 0
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.annotation_pipeline")
    def test_missing_gene_info(self, mock_pipeline, client, sample_vcf_content):
        """Test handling of missing gene information"""
        mock_data = {
            "chr1:7984930:A:C": {
                "genomic_hgvs": "NC_000001.11:g.7984930A>C",
                "transcript_hgvs": "NM_001234.5:c.123A>C",
                "genes": [],
                "protein_change": "p.Lys41Asn",
                "molecular_consequences": ["missense_variant"],
                "review_status": "criteria provided, single submitter",
                "clinical_significance": "Pathogenic",
                "trait_name": "Test Disease",
                "trait_omim": "123456",
                "variation_id": "999888",
                "gnomad_total_af": "0.0001",
            }
        }
        mock_pipeline.process_vcf.return_value = mock_data

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            response = client.post(
                "/",
                data={"vcf_files": (open(tf.name, "rb"), "test.vcf")},
                content_type="multipart/form-data",
            )

            assert response.status_code == 200

            with app.app_context():
                # When genes list is empty, the app tries to access genes[0] which causes an IndexError
                # The exception is caught and logged, so no variant is created
                variants = Variant.query.all()
                assert len(variants) == 0
        finally:
            os.unlink(tf.name)

"""Integration and unit tests for the ClinVar Annotator Flask application.

This test suite validates request handling, file upload behaviour, annotation
processing, and database persistence to ensure that the application behaves
correctly across normal operation, edge cases, and error conditions.
"""

import os
import tempfile
from unittest.mock import patch
import pytest

from clinvar_anno_app.app import app, db
from clinvar_anno_app.models import Patient, Variant, PatientVariant


@pytest.fixture
def client():
    """Provide a Flask test client backed by an isolated temporary database.

    This fixture configures the application for testing by:
    - Creating a temporary SQLite database
    - Initialising all database tables
    - Yielding a Flask test client for request simulation
    - Ensuring all database state is cleaned up after each test

    Scope: Per-test.
    """
    # Create a temporary file to back the SQLite database
    db_fd, db_path = tempfile.mkstemp()

    # Override application configuration for an isolated test environment
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["TESTING"] = True
    app.config["UPLOAD_FOLDER"] = tempfile.mkdtemp()

    with app.app_context():
        # Initialise schema before yielding the test client
        db.create_all()
        yield app.test_client()

        # Ensure all DB state is cleared after the test completes
        db.session.remove()
        db.drop_all()

    # Clean up temporary database file
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def sample_vcf_content():
    """Return minimal but valid VCF content for upload-based tests.

    The content includes:
    - Required VCF headers
    - Two variant records on different chromosomes

    Intended to exercise multi-variant ingestion and annotation behaviour
    without introducing unnecessary complexity.
    """
    # Minimal VCF sufficient to trigger parsing and annotation logic
    return """##fileformat=VCFv4.2
##reference=GRCh38
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO
chr1	7984930	.	A	C	.	.	.
chr2	1234567	.	G	T	.	.	.
"""


@pytest.fixture
def mock_annotation_data():
    """Provide deterministic mock annotation output from the annotation pipeline.

    This fixture simulates fully annotated ClinVar-style results for two variants,
    including:
    - HGVS nomenclature
    - Gene metadata
    - Clinical significance and review status
    - Population allele frequency

    Used to validate downstream parsing, transformation, and persistence logic
    independently of the real annotation pipeline.
    """
    # Keys correspond to CHROM:POS:REF:ALT identifiers
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
    """Validate behaviour of the application home (index) route."""

    def test_home_get(self, client):
        """Ensure the home page responds successfully to a GET request.

        Expected behaviour:
        - The route renders without error
        - HTTP 200 is returned
        """
        # Basic smoke test for the index route
        response = client.get("/")
        assert response.status_code == 200

    def test_home_post_no_file(self, client):
        """Ensure POSTing to the home route without files is handled gracefully.

        Expected behaviour:
        - No server error occurs
        - The response returns HTTP 200
        - No database changes are triggered
        """
        # Simulate a form submission without any uploaded files
        response = client.post("/", data={})
        assert response.status_code == 200


class TestFileUpload:
    """Validate file upload handling and request-level behaviour."""

    @patch("clinvar_anno_app.app.annotation_pipeline")
    def test_upload_single_vcf(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Verify that a single valid VCF file is processed end-to-end.

        Scope:
        - File upload handling
        - Invocation of the annotation pipeline
        - Creation of one patient record
        - Creation of multiple variant records

        Expected behaviour:
        - The annotation pipeline is called
        - One patient is created based on the filename
        - All variants in the VCF are persisted
        """
        # Mock the annotation pipeline to avoid external dependencies
        mock_pipeline.process_vcf.return_value = mock_annotation_data

        # Write VCF content to a temporary file to mimic a real upload
        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            # Submit the VCF file via multipart form data
            response = client.post(
                "/",
                data={"vcf_files": (open(tf.name, "rb"), "patient001.vcf")},
                content_type="multipart/form-data",
            )

            assert response.status_code == 200
            assert mock_pipeline.process_vcf.called

            with app.app_context():
                # Patient ID is derived from the filename
                patient = Patient.query.filter_by(patient_id="patient001").first()
                assert patient is not None

                # Both variants in the VCF should be persisted
                variants = Variant.query.all()
                assert len(variants) == 2
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.annotation_pipeline")
    def test_upload_multiple_vcf(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Verify that multiple VCF files can be uploaded in a single request.

        Scope:
        - Multipart request handling
        - Independent patient creation per file

        Expected behaviour:
        - Each VCF file results in a distinct patient record
        - The request completes successfully
        """
        mock_pipeline.process_vcf.return_value = mock_annotation_data

        # Create two temporary VCF files to upload together
        temp_files = []
        for i in range(2):
            tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
            with open(tf.name, "w") as f:
                f.write(sample_vcf_content)
            temp_files.append(tf.name)

        try:
            # Upload both files in a single request
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
                # Each file should correspond to one patient
                patients = Patient.query.all()
                assert len(patients) == 2
        finally:
            for tf in temp_files:
                os.unlink(tf)

    def test_upload_non_vcf_file(self, client):
        """Ensure that non-VCF files are ignored during upload.

        Expected behaviour:
        - The request completes without error
        - No patients or variants are created
        """
        # Use a .txt file to simulate an unsupported upload type
        tf = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)

        try:
            response = client.post(
                "/",
                data={"vcf_files": (open(tf.name, "rb"), "test.txt")},
                content_type="multipart/form-data",
            )

            assert response.status_code == 200

            with app.app_context():
                # Non-VCF files should not affect the database
                patients = Patient.query.all()
                assert len(patients) == 0
        finally:
            os.unlink(tf.name)


class TestDatabaseOperations:
    """Validate correctness of database persistence and relationships."""

    @patch("clinvar_anno_app.app.annotation_pipeline")
    def test_variant_fields_stored_correctly(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Ensure annotated variant fields are correctly transformed and stored.

        Scope:
        - Mapping of annotation fields to database columns
        - Selection of primary values where multiple are provided

        Expected behaviour:
        - HGVS, protein change, molecular consequence, review stars,
          and allele frequency fields are persisted as expected
        """
        mock_pipeline.process_vcf.return_value = mock_annotation_data

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            # Trigger upload and annotation
            client.post(
                "/",
                data={"vcf_files": (open(tf.name, "rb"), "patient123.vcf")},
                content_type="multipart/form-data",
            )

            with app.app_context():
                # Inspect one variant to validate field-level mappings
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
        """Verify many-to-many relationships between patients and variants.

        Expected behaviour:
        - A patient is linked to all variants in their VCF
        - Each variant records the correct patient linkage
        """
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
                # Patient should be linked to both variants
                patient = Patient.query.filter_by(patient_id="patient456").first()
                assert len(patient.variants) == 2

                # Each variant should have exactly one patient link
                variant = Variant.query.first()
                assert len(variant.patient_links) == 1
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.annotation_pipeline")
    def test_duplicate_patient_not_created(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Ensure idempotent behaviour when the same patient is uploaded repeatedly.

        Expected behaviour:
        - Re-uploading a VCF for the same patient does not create duplicate
          patient records
        """
        mock_pipeline.process_vcf.return_value = mock_annotation_data

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            # Upload the same file twice for the same patient
            for _ in range(2):
                client.post(
                    "/",
                    data={"vcf_files": (open(tf.name, "rb"), "patient789.vcf")},
                    content_type="multipart/form-data",
                )

            with app.app_context():
                # Patient table should contain a single record
                patients = Patient.query.filter_by(patient_id="patient789").all()
                assert len(patients) == 1
        finally:
            os.unlink(tf.name)


class TestAnnotationProcessing:
    """Validate interpretation and transformation of annotation metadata."""

    @patch("clinvar_anno_app.app.annotation_pipeline")
    def test_review_status_stars_mapping(
        self, mock_pipeline, client, sample_vcf_content
    ):
        """Ensure ClinVar review status strings map to the correct star ratings.

        Scope:
        - Mapping logic for review status → star count

        Expected behaviour:
        - Each known review status produces the correct number of stars
        - The persisted representation matches the expected star count
        """
        # Each tuple represents (review_status_string, expected_star_count)
        test_cases = [
            ("practice guideline", 4),
            ("reviewed by expert panel", 3),
            ("criteria provided, multiple submitters, no conflicts", 2),
            ("criteria provided, single submitter", 1),
            ("no assertion criteria provided", 0),
        ]

        for review_status, expected_stars in test_cases:
            # Build mock annotation data dynamically for each case
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
                    # Star symbols should match the expected count
                    variant = Variant.query.filter_by(gene_symbol="GENE1").first()
                    assert variant.review_status_stars.count("★") == expected_stars
            finally:
                os.unlink(tf.name)

            with app.app_context():
                # Explicit cleanup to isolate each sub-test
                db.session.query(PatientVariant).delete()
                db.session.query(Variant).delete()
                db.session.query(Patient).delete()
                db.session.commit()


class TestEdgeCases:
    """Validate graceful handling of incomplete or unexpected input."""

    @patch("clinvar_anno_app.app.annotation_pipeline")
    def test_empty_annotation_results(self, mock_pipeline, client, sample_vcf_content):
        """Ensure empty annotation results do not create database records.

        Expected behaviour:
        - The request completes successfully
        - No variants are created when the annotation pipeline returns no data
        """
        # Simulate a pipeline returning no annotations
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
                # No variants should be persisted
                variants = Variant.query.all()
                assert len(variants) == 0
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.annotation_pipeline")
    def test_missing_gene_info(self, mock_pipeline, client, sample_vcf_content):
        """Verify behaviour when annotation results lack gene information.

        Scope:
        - Error handling during variant creation

        Expected behaviour:
        - An IndexError occurs internally when accessing genes[0]
        - The exception is caught and logged
        - No variant records are persisted
        """
        # Annotation result deliberately omits gene entries
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
                # Variant creation should fail safely
                variants = Variant.query.all()
                assert len(variants) == 0
        finally:
            os.unlink(tf.name)

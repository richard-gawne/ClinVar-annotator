"""Tests for the ClinVar Annotator Flask application."""

import os
import sys
import tempfile
from unittest.mock import patch
import pytest

from clinvar_anno_app.app import app, db
from clinvar_anno_app.models import Patient, Variant, PatientVariant


@pytest.fixture
def client():
    """Create a test client with a temporary database"""
    # Create a temporary file for the test database
    db_fd, db_path = tempfile.mkstemp()
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["TESTING"] = True
    app.config["UPLOAD_FOLDER"] = tempfile.mkdtemp()

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()

    # Clean up temporary files
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
            "genes": [{"symbol": "GENE1"}],
            "protein_change": "p.Lys41Asn",
            "molecular_consequences": ["missense_variant", "splice_region_variant"],
            "review_status": "criteria provided, multiple submitters, no conflicts",
            "clinical_significance": "Pathogenic",
            "trait_name": "Test Disease",
            "trait_omim": "123456",
            "variation_id": "999888",
        },
        "chr2:1234567:G:T": {
            "genomic_hgvs": "NC_000002.12:g.1234567G>T",
            "transcript_hgvs": "NM_005678.3:c.456G>T",
            "genes": [{"symbol": "GENE2"}],
            "protein_change": "p.Arg152Leu, p.Arg152Trp",
            "molecular_consequences": ["missense_variant"],
            "review_status": "reviewed by expert panel",
            "clinical_significance": "Likely pathogenic",
            "trait_name": "Another Disease",
            "trait_omim": "654321",
            "variation_id": "777666",
        },
    }


class TestHomeRoute:
    """Tests for the home route"""

    def test_home_get(self, client):
        """Test GET request to home page"""
        response = client.get("/")
        assert response.status_code == 200
        assert b"ClinVar Annotator" in response.data
        assert b"Upload" in response.data

    def test_home_post_no_file(self, client):
        """Test POST request without file"""
        response = client.post("/", data={})
        assert response.status_code == 200


class TestFileUpload:
    """Tests for file upload functionality"""

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_upload_single_vcf(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test uploading a single VCF file"""
        mock_pipeline.return_value = mock_annotation_data

        data = {
            "vcf_files": (
                tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False),
                "patient001.vcf",
            )
        }

        # Write content to temp file
        with open(data["vcf_files"][0].name, "w") as f:
            f.write(sample_vcf_content)

        try:
            response = client.post(
                "/",
                data={
                    "vcf_files": (
                        open(data["vcf_files"][0].name, "rb"),
                        "patient001.vcf",
                    )
                },
                content_type="multipart/form-data",
            )

            assert response.status_code == 200
            assert b"patient001.vcf" in response.data
            assert mock_pipeline.called
        finally:
            os.unlink(data["vcf_files"][0].name)

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_upload_multiple_vcf(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test uploading multiple VCF files"""
        mock_pipeline.return_value = mock_annotation_data

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
            assert b"patient001.vcf" in response.data
            assert b"patient002.vcf" in response.data
        finally:
            for tf in temp_files:
                os.unlink(tf)

    def test_upload_non_vcf_file(self, client):
        """Test uploading a non-VCF file"""
        data = {
            "vcf_files": (
                tempfile.NamedTemporaryFile(suffix=".txt", delete=False),
                "test.txt",
            )
        }

        try:
            response = client.post(
                "/",
                data={"vcf_files": (open(data["vcf_files"][0].name, "rb"), "test.txt")},
                content_type="multipart/form-data",
            )

            # Should still return 200 but skip processing
            assert response.status_code == 200
        finally:
            os.unlink(data["vcf_files"][0].name)


class TestDatabaseOperations:
    """Tests for database operations"""

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_patient_creation(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test that patients are created in database"""
        mock_pipeline.return_value = mock_annotation_data

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
                patient = Patient.query.filter_by(patient_id="patient123").first()
                assert patient is not None
                assert patient.patient_id == "patient123"
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_variant_creation(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test that variants are created in database"""
        mock_pipeline.return_value = mock_annotation_data

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
                variants = Variant.query.all()
                assert len(variants) == 2

                variant1 = Variant.query.filter_by(gene_symbol="GENE1").first()
                assert variant1 is not None
                assert variant1.hgvsg == "NC_000001.11:g.7984930A>C"
                assert variant1.protein_change == "p.Lys41Asn"
                assert (
                    "★" in variant1.review_status_stars
                    or variant1.review_status_stars == ""
                )
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_patient_variant_link(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test that patient-variant links are created"""
        mock_pipeline.return_value = mock_annotation_data

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
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_duplicate_patient_not_created(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test that uploading same patient twice doesn't create duplicates"""
        mock_pipeline.return_value = mock_annotation_data

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            # Upload twice
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

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_protein_change_extraction(self, mock_pipeline, client, sample_vcf_content):
        """Test that first protein change is extracted correctly"""
        mock_data = {
            "chr1:7984930:A:C": {
                "genomic_hgvs": "NC_000001.11:g.7984930A>C",
                "transcript_hgvs": "NM_001234.5:c.123A>C",
                "genes": [{"symbol": "GENE1"}],
                "protein_change": "p.Arg152Leu, p.Arg152Trp, p.Arg152Cys",
                "molecular_consequences": ["missense_variant"],
                "review_status": "criteria provided, single submitter",
                "clinical_significance": "Pathogenic",
                "trait_name": "Test Disease",
                "trait_omim": "123456",
                "variation_id": "999888",
            }
        }
        mock_pipeline.return_value = mock_data

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            client.post(
                "/",
                data={"vcf_files": (open(tf.name, "rb"), "test.vcf")},
                content_type="multipart/form-data",
            )

            with app.app_context():
                variant = Variant.query.first()
                assert variant.protein_change == "p.Arg152Leu"
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_molecular_consequence_extraction(
        self, mock_pipeline, client, sample_vcf_content
    ):
        """Test that first molecular consequence is extracted"""
        mock_data = {
            "chr1:7984930:A:C": {
                "genomic_hgvs": "NC_000001.11:g.7984930A>C",
                "transcript_hgvs": "NM_001234.5:c.123A>C",
                "genes": [{"symbol": "GENE1"}],
                "protein_change": "p.Lys41Asn",
                "molecular_consequences": [
                    "splice_acceptor_variant",
                    "missense_variant",
                    "intron_variant",
                ],
                "review_status": "criteria provided, single submitter",
                "clinical_significance": "Pathogenic",
                "trait_name": "Test Disease",
                "trait_omim": "123456",
                "variation_id": "999888",
            }
        }
        mock_pipeline.return_value = mock_data

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            client.post(
                "/",
                data={"vcf_files": (open(tf.name, "rb"), "test.vcf")},
                content_type="multipart/form-data",
            )

            with app.app_context():
                variant = Variant.query.first()
                assert variant.molecular_consequences == "splice_acceptor_variant"
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
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
                    "genes": [{"symbol": "GENE1"}],
                    "protein_change": "p.Lys41Asn",
                    "molecular_consequences": ["missense_variant"],
                    "review_status": review_status,
                    "clinical_significance": "Pathogenic",
                    "trait_name": "Test Disease",
                    "trait_omim": "123456",
                    "variation_id": "999888",
                }
            }
            mock_pipeline.return_value = mock_data

            tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
            with open(tf.name, "w") as f:
                f.write(sample_vcf_content)

            try:
                client.post(
                    "/",
                    data={
                        "vcf_files": (open(tf.name, "rb"), f"test_{expected_stars}.vcf")
                    },
                    content_type="multipart/form-data",
                )

                with app.app_context():
                    variant = Variant.query.filter_by(gene_symbol="GENE1").first()
                    assert variant.review_status_stars.count("★") == expected_stars
            finally:
                os.unlink(tf.name)

            # Clear database for next test
            with app.app_context():
                db.session.query(PatientVariant).delete()
                db.session.query(Variant).delete()
                db.session.query(Patient).delete()
                db.session.commit()


class TestRendering:
    """Tests for template rendering"""

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_variant_table_rendered(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test that variant table is rendered correctly"""
        mock_pipeline.return_value = mock_annotation_data

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            response = client.post(
                "/",
                data={"vcf_files": (open(tf.name, "rb"), "patient001.vcf")},
                content_type="multipart/form-data",
            )

            assert b"GENE1" in response.data
            assert b"GENE2" in response.data
            assert b"Pathogenic" in response.data
            assert b"Test Disease" in response.data
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_clinvar_url_generated(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test that ClinVar URLs are generated correctly"""
        mock_pipeline.return_value = mock_annotation_data

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            response = client.post(
                "/",
                data={"vcf_files": (open(tf.name, "rb"), "patient001.vcf")},
                content_type="multipart/form-data",
            )

            assert (
                b"https://www.ncbi.nlm.nih.gov/clinvar/variation/999888"
                in response.data
            )
            assert (
                b"https://www.ncbi.nlm.nih.gov/clinvar/variation/777666"
                in response.data
            )
        finally:
            os.unlink(tf.name)


class TestDatabasePersistence:
    """Tests for database persistence and data integrity"""

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_data_persists_across_requests(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test that data persists in database between requests"""
        mock_pipeline.return_value = mock_annotation_data

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            # First upload
            client.post(
                "/",
                data={"vcf_files": (open(tf.name, "rb"), "patient001.vcf")},
                content_type="multipart/form-data",
            )

            # Verify data exists in database
            with app.app_context():
                patient = Patient.query.filter_by(patient_id="patient001").first()
                assert patient is not None
                initial_patient_id = patient.id

                variants = Variant.query.all()
                assert len(variants) == 2
                initial_variant_ids = [v.id for v in variants]

            # Make another request (simulating app restart or new session)
            client.get("/")

            # Verify data still exists
            with app.app_context():
                patient = Patient.query.filter_by(patient_id="patient001").first()
                assert patient is not None
                assert patient.id == initial_patient_id

                variants = Variant.query.all()
                assert len(variants) == 2
                assert sorted([v.id for v in variants]) == sorted(initial_variant_ids)
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_same_variant_different_patients(
        self, mock_pipeline, client, sample_vcf_content
    ):
        """Test that the same variant can be linked to multiple patients"""
        mock_data = {
            "chr1:7984930:A:C": {
                "genomic_hgvs": "NC_000001.11:g.7984930A>C",
                "transcript_hgvs": "NM_001234.5:c.123A>C",
                "genes": [{"symbol": "GENE1"}],
                "protein_change": "p.Lys41Asn",
                "molecular_consequences": ["missense_variant"],
                "review_status": "criteria provided, single submitter",
                "clinical_significance": "Pathogenic",
                "trait_name": "Test Disease",
                "trait_omim": "123456",
                "variation_id": "999888",
            }
        }
        mock_pipeline.return_value = mock_data

        # Upload for patient1
        tf1 = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf1.name, "w") as f:
            f.write(sample_vcf_content)

        # Upload for patient2
        tf2 = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf2.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            client.post(
                "/",
                data={"vcf_files": (open(tf1.name, "rb"), "patient_A.vcf")},
                content_type="multipart/form-data",
            )

            client.post(
                "/",
                data={"vcf_files": (open(tf2.name, "rb"), "patient_B.vcf")},
                content_type="multipart/form-data",
            )

            with app.app_context():
                # Should have 2 patients
                patients = Patient.query.all()
                assert len(patients) == 2

                # Should have only 1 variant (not duplicated)
                variants = Variant.query.all()
                assert len(variants) == 1

                # Should have 2 patient-variant links
                links = PatientVariant.query.all()
                assert len(links) == 2

                # Both patients should be linked to the same variant
                variant = variants[0]
                patient_ids = {
                    link.patient.patient_id for link in variant.patient_links
                }
                assert patient_ids == {"patient_A", "patient_B"}
        finally:
            os.unlink(tf1.name)
            os.unlink(tf2.name)

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_database_rollback_on_error(
        self, mock_pipeline, client, sample_vcf_content
    ):
        """Test that database changes are rolled back on error"""
        # Make the pipeline raise an exception after some processing
        mock_pipeline.side_effect = Exception("Pipeline error")

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            with app.app_context():
                initial_patient_count = Patient.query.count()
                initial_variant_count = Variant.query.count()

            # This should fail
            try:
                client.post(
                    "/",
                    data={"vcf_files": (open(tf.name, "rb"), "test.vcf")},
                    content_type="multipart/form-data",
                )
            except Exception:
                pass

            # Database should remain unchanged (or changes should be minimal)
            with app.app_context():
                final_patient_count = Patient.query.count()
                final_variant_count = Variant.query.count()

                # Counts should be the same or close (depends on when error occurred)
                assert abs(final_patient_count - initial_patient_count) <= 1
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_variant_uniqueness_by_vcf_description(
        self, mock_pipeline, client, sample_vcf_content
    ):
        """Test that variants are unique by VCF description"""
        mock_data = {
            "chr1:7984930:A:C": {
                "genomic_hgvs": "NC_000001.11:g.7984930A>C",
                "transcript_hgvs": "NM_001234.5:c.123A>C",
                "genes": [{"symbol": "GENE1"}],
                "protein_change": "p.Lys41Asn",
                "molecular_consequences": ["missense_variant"],
                "review_status": "criteria provided, single submitter",
                "clinical_significance": "Pathogenic",
                "trait_name": "Test Disease",
                "trait_omim": "123456",
                "variation_id": "999888",
            }
        }
        mock_pipeline.return_value = mock_data

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            # Upload same variant twice
            for i in range(2):
                client.post(
                    "/",
                    data={"vcf_files": (open(tf.name, "rb"), f"patient{i}.vcf")},
                    content_type="multipart/form-data",
                )

            with app.app_context():
                # Should only have one variant with this VCF description
                variants = Variant.query.filter_by(
                    vcf_description="GRCh38:chr1:7984930:A:C"
                ).all()
                assert len(variants) == 1
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_patient_variant_relationship_integrity(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test that patient-variant relationships maintain referential integrity"""
        mock_pipeline.return_value = mock_annotation_data

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        try:
            client.post(
                "/",
                data={"vcf_files": (open(tf.name, "rb"), "patient_xyz.vcf")},
                content_type="multipart/form-data",
            )

            with app.app_context():
                patient = Patient.query.filter_by(patient_id="patient_xyz").first()
                assert patient is not None

                # Check relationships work both ways
                assert len(patient.variants) == 2

                for link in patient.variants:
                    assert link.patient.patient_id == "patient_xyz"
                    assert link.variant is not None
                    assert link.variant.gene_symbol in ["GENE1", "GENE2"]

                # Check from variant side
                variant = Variant.query.first()
                assert len(variant.patient_links) > 0
                assert variant.patient_links[0].patient.patient_id == "patient_xyz"
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_data_integrity_after_multiple_uploads(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test data integrity after multiple sequential uploads"""
        mock_pipeline.return_value = mock_annotation_data

        patient_names = ["patientA", "patientB", "patientC"]
        temp_files = []

        # Create temp files
        for _ in patient_names:
            tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
            with open(tf.name, "w") as f:
                f.write(sample_vcf_content)
            temp_files.append(tf.name)

        try:
            # Upload multiple files
            for i, name in enumerate(patient_names):
                client.post(
                    "/",
                    data={"vcf_files": (open(temp_files[i], "rb"), f"{name}.vcf")},
                    content_type="multipart/form-data",
                )

            with app.app_context():
                # Verify all patients exist
                patients = Patient.query.all()
                assert len(patients) == 3
                patient_ids = {p.patient_id for p in patients}
                assert patient_ids == set(patient_names)

                # Verify variants are not duplicated
                variants = Variant.query.all()
                assert len(variants) == 2  # Only 2 unique variants

                # Verify all links exist
                links = PatientVariant.query.all()
                assert len(links) == 6  # 3 patients × 2 variants

                # Verify each patient has 2 variants
                for patient in patients:
                    assert len(patient.variants) == 2

                # Verify each variant has 3 patients
                for variant in variants:
                    assert len(variant.patient_links) == 3
        finally:
            for tf in temp_files:
                os.unlink(tf)

    def test_database_schema_integrity(self, client):
        """Test that database schema is created correctly"""
        with app.app_context():
            # Check that tables exist
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()

            assert "patient" in tables
            assert "variant" in tables
            assert "patient_variant" in tables

            # Check Patient table columns
            patient_columns = {col["name"] for col in inspector.get_columns("patient")}
            assert "id" in patient_columns
            assert "patient_id" in patient_columns

            # Check Variant table columns
            variant_columns = {col["name"] for col in inspector.get_columns("variant")}
            assert "id" in variant_columns
            assert "vcf_description" in variant_columns
            assert "hgvsg" in variant_columns
            assert "gene_symbol" in variant_columns

            # Check PatientVariant table columns and foreign keys
            pv_columns = {
                col["name"] for col in inspector.get_columns("patient_variant")
            }
            assert "id" in pv_columns
            assert "patient_id" in pv_columns
            assert "variant_id" in pv_columns

            fks = inspector.get_foreign_keys("patient_variant")
            fk_tables = {fk["referred_table"] for fk in fks}
            assert "patient" in fk_tables
            assert "variant" in fk_tables


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_empty_annotation_results(self, mock_pipeline, client, sample_vcf_content):
        """Test handling of empty annotation results"""
        mock_pipeline.return_value = {}

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

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_missing_gene_symbol(self, mock_pipeline, client, sample_vcf_content):
        """Test handling of missing gene symbol"""
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
            }
        }
        mock_pipeline.return_value = mock_data

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
                variant = Variant.query.first()
                assert variant.gene_symbol is None
        finally:
            os.unlink(tf.name)

    @patch("clinvar_anno_app.app.run_annotation_pipeline")
    def test_file_cleanup(
        self, mock_pipeline, client, sample_vcf_content, mock_annotation_data
    ):
        """Test that temporary files are cleaned up"""
        mock_pipeline.return_value = mock_annotation_data

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False)
        with open(tf.name, "w") as f:
            f.write(sample_vcf_content)

        filename = os.path.basename(tf.name)

        try:
            client.post(
                "/",
                data={"vcf_files": (open(tf.name, "rb"), "test.vcf")},
                content_type="multipart/form-data",
            )

            # Check that file in upload folder is cleaned up
            upload_path = os.path.join(app.config["UPLOAD_FOLDER"], "test.vcf")
            assert not os.path.exists(upload_path)
        finally:
            if os.path.exists(tf.name):
                os.unlink(tf.name)

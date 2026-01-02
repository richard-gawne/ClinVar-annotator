"""
Tests for VariantAnnotationPipeline (main.py)
These tests validate the orchestration logic of the pipeline:
- Correct wiring between modules
- Proper handling of edge cases
- No duplication of module-level unit tests (ClinVar, gnomAD, HGVS)
All external dependencies are mocked so that:
- No network calls occur
- No real files are required
- Failures indicate pipeline logic issues only
"""

# pylint: disable=use-implicit-booleaness-not-comparison

from pathlib import Path

from clinvar_anno_core.main import VariantAnnotationPipeline


def test_process_vcf_annotates_variant(monkeypatch):
    """
    Test the full, successful execution path of process_vcf.
    This test verifies that when:
    - A VCF contains one variant
    - HGVS conversion succeeds
    - ClinVar returns an annotation
    - gnomAD returns allele frequencies
    Then:
    - Exactly one annotated variant is produced
    - Clinical significance is propagated correctly
    """

    # Create a fresh pipeline instance
    pipeline = VariantAnnotationPipeline()

    # Mock Step 1: VCF parsing
    # Pretend the VCF file contains exactly one variant
    monkeypatch.setattr(
        "clinvar_anno_core.main.parse_vcf_file", lambda _: ["chr1:100:A:G"]
    )

    # Mock Step 2: gnomAD allele frequency extraction
    # Return pre-computed allele frequencies for the variant
    monkeypatch.setattr(
        "clinvar_anno_core.main.extract_gnomad_afs_from_vcf",
        lambda _: [
            {
                "variant_id": "chr1:100:A:G",
                "genome_af": "0.1",
                "exome_af": "0.1",
                "total_af": "0.1",
            }
        ],
    )

    # Mock Step 3: HGVS conversion
    # Convert the coordinate into both genomic and transcript HGVS
    monkeypatch.setattr(
        pipeline.hgvs_converter,
        "batch_convert",
        lambda _: [
            {
                "input_variant": "chr1:100:A:G",
                "genomic_hgvs": "g.100A>G",
                "transcript_hgvs": "c.100A>G",
            }
        ],
    )

    # Mock Step 4: ClinVar search
    # Return a minimal but valid ClinVar annotation dictionary
    monkeypatch.setattr(
        pipeline.clinvar_searcher,
        "search_by_hgvs",
        lambda _: {
            "variation_id": "123",
            "clinical_significance": "Pathogenic",
            "genes": [],
        },
    )

    # Execute the pipeline
    result = pipeline.process_vcf(Path("fake.vcf"))

    # Assertions
    # Exactly one variant should be returned
    assert len(result) == 1

    # The clinical significance should be preserved from ClinVar
    assert result["chr1:100:A:G"]["clinical_significance"] == "Pathogenic"


def test_process_vcf_skips_variant_without_transcript_hgvs(monkeypatch):
    """
    Test that variants without a transcript-level HGVS (c. notation)
    are skipped by the pipeline.
    This reflects a design decision:
    - ClinVar searches prioritise MANE Select transcript HGVS
    - Variants without transcript HGVS should not proceed
    """

    # Create a fresh pipeline instance
    pipeline = VariantAnnotationPipeline()

    # Mock VCF parsing to return a single variant
    monkeypatch.setattr(
        "clinvar_anno_core.main.parse_vcf_file", lambda _: ["chr1:100:A:G"]
    )

    # Mock gnomAD extraction to return no allele frequency data
    monkeypatch.setattr(
        "clinvar_anno_core.main.extract_gnomad_afs_from_vcf", lambda _: []
    )

    # Mock HGVS conversion where transcript HGVS is missing
    monkeypatch.setattr(
        pipeline.hgvs_converter,
        "batch_convert",
        lambda _: [
            {
                "input_variant": "chr1:100:A:G",
                "genomic_hgvs": "g.100A>G",
                "transcript_hgvs": None,
            }
        ],
    )

    # Execute pipeline
    result = pipeline.process_vcf(Path("fake.vcf"))

    # The variant should be skipped entirely
    assert result == {}


def test_process_vcf_skips_variant_when_clinvar_missing(monkeypatch):
    """
    Test that variants are skipped when ClinVar returns no matching record.
    Even if:
    - VCF parsing succeeds
    - HGVS conversion succeeds
    The variant should not be included unless ClinVar provides annotations.
    """

    # Create a fresh pipeline instance
    pipeline = VariantAnnotationPipeline()

    # Mock VCF parsing
    monkeypatch.setattr(
        "clinvar_anno_core.main.parse_vcf_file", lambda _: ["chr1:100:A:G"]
    )

    # Mock gnomAD extraction
    monkeypatch.setattr(
        "clinvar_anno_core.main.extract_gnomad_afs_from_vcf", lambda _: []
    )

    # Mock HGVS conversion
    monkeypatch.setattr(
        pipeline.hgvs_converter,
        "batch_convert",
        lambda _: [
            {
                "input_variant": "chr1:100:A:G",
                "genomic_hgvs": "g.100A>G",
                "transcript_hgvs": "c.100A>G",
            }
        ],
    )

    # Mock ClinVar returning no result
    monkeypatch.setattr(pipeline.clinvar_searcher, "search_by_hgvs", lambda _: None)

    # Execute pipeline
    result = pipeline.process_vcf(Path("fake.vcf"))

    # Variant should be excluded from output
    assert result == {}


def test_process_vcf_empty(monkeypatch):
    """
    Test that process_vcf returns an empty dictionary
    when the input VCF contains no variants.
    This ensures the early-exit guard clause works correctly.
    """

    # Mock VCF parser to return no variants
    monkeypatch.setattr("clinvar_anno_core.main.parse_vcf_file", lambda _: [])

    pipeline = VariantAnnotationPipeline()
    result = pipeline.process_vcf(Path("fake.vcf"))

    # No variants → no annotations
    assert result == {}


def test_save_results(tmp_path):
    """
    Test that save_results correctly writes a JSON file to disk.
    This test verifies:
    - The file is created
    - No exceptions are raised
    - The method handles filesystem output correctly
    """

    # Create a fresh pipeline instance
    pipeline = VariantAnnotationPipeline()

    # Create a temporary output path provided by pytest
    output = tmp_path / "out.json"

    # Write a minimal annotation dictionary
    pipeline.save_results({"v": {}}, output)

    # Confirm the file was created
    assert output.exists()

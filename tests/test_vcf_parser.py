import pytest
import tempfile
from pathlib import Path
from clinvar_anno_core.modules.vcf_parser import parse_vcf_file

def create_temp_vcf(tmp_path, content: str) -> Path:
    """Helper to create a temporary VCF file using pytest tmp_path."""
    vcf_path = tmp_path / "test.vcf"
    vcf_path.write_text(content)
    return vcf_path


def test_valid_vcf_parsing(tmp_path):
    content = (
        "##fileformat=VCFv4.2\n"
        "#CHROM POS ID REF ALT\n"
        "chr1\t12345\t.\tA\tT\n"
        "chr2\t67890\t.\tG\tC\n"
    )
    vcf_path = create_temp_vcf(tmp_path, content)

    result = parse_vcf_file(vcf_path)

    assert result == [
        "chr1:12345:A:T",
        "chr2:67890:G:C"
    ]


def test_space_delimited_lines(tmp_path):
    content = (
        "##header\n"
        "chr3  11111  id  T  G\n"
    )
    vcf_path = create_temp_vcf(tmp_path, content)

    result = parse_vcf_file(vcf_path)

    assert result == ["chr3:11111:T:G"]


def test_skips_headers_and_empty_lines(tmp_path):
    content = (
        "##fileformat=VCFv4.2\n"
        "# Another header\n"
        "\n"
        "   \n"
        "chr1\t200\t.\tC\tA\n"
    )
    vcf_path = create_temp_vcf(tmp_path, content)

    result = parse_vcf_file(vcf_path)

    assert result == ["chr1:200:C:A"]


def test_insufficient_fields(tmp_path):
    content = (
        "# header\n"
        "chr1\t123\n"          # too few fields → skipped
        "chr2\t456\t.\tA\tG\n"  # valid
    )
    vcf_path = create_temp_vcf(tmp_path, content)

    result = parse_vcf_file(vcf_path)

    assert result == ["chr2:456:A:G"]


def test_missing_file():
    fake_path = Path("nonexistent_file_12345.vcf")
    result = parse_vcf_file(fake_path)

    assert result is None


def test_exception_handling(tmp_path):
    # Use a directory path to trigger exception
    dir_path = tmp_path
    result = parse_vcf_file(dir_path)

    assert result is None
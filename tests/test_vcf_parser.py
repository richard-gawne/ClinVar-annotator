""" This test suite verifies the functionality of the `parse_vcf_file` function,
which parses VCF files and extracts variants in the format "chrom:pos:REF:ALT"  """

from pathlib import Path
from clinvar_anno_core.modules.vcf_parser import parse_vcf_file

def create_temp_vcf(tmp_path, content: str) -> Path:
    """Helper to create a temporary VCF file using pytest tmp_path."""
    vcf_path = tmp_path / "test.vcf"
    vcf_path.write_text(content)
    return vcf_path


def test_valid_vcf_parsing(tmp_path):
    """ 
    Test parsing of a valid VCF file with standard headers and tab-delimited fields.

    Verifies that parse_vcf_file correctly:
      - Skips VCF meta-information and header lines
      - Extracts CHROM, POS, REF, and ALT fields
      - Returns variants in the format "chrom:pos:REF:ALT"
    """
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
    """
    Test parsing of VCF lines that are space-delimited instead of tab-delimited.

    Verifies that parse_vcf_file can correctly handle lines
    where columns are separated by multiple spaces and still extract variants
    in the format "chrom:pos:REF:ALT".
    """
    content = (
        "##header\n"
        "chr3  11111  id  T  G\n"
    )
    vcf_path = create_temp_vcf(tmp_path, content)

    result = parse_vcf_file(vcf_path)

    assert result == ["chr3:11111:T:G"]


def test_skips_headers_and_empty_lines(tmp_path):
    """
    Test that parse_vcf_file correctly skips VCF header lines and 
    empty/whitespace-only lines.

    Ensures that only valid variant lines are parsed and returned,
    ignoring headers starting with '#' and empty lines.
    """
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
    """
    Test handling of VCF lines with insufficient fields.

    Verifies that lines with fewer than 5 columns are skipped and do not appear
    in the output, while valid lines are correctly parsed.
    """
    content = (
        "# header\n"
        "chr1\t123\n"          # too few fields → skipped
        "chr2\t456\t.\tA\tG\n"  # valid
    )
    vcf_path = create_temp_vcf(tmp_path, content)

    result = parse_vcf_file(vcf_path)

    assert result == ["chr2:456:A:G"]


def test_missing_file():
    """
    Test behavior when the specified VCF file does not exist.

    Ensures that parse_vcf_file returns None and handles 
    FileNotFoundError
    """
    fake_path = Path("nonexistent_file_12345.vcf")
    result = parse_vcf_file(fake_path)

    assert result is None


def test_exception_handling(tmp_path):
    """
    Test general exception handling during VCF parsing.

    Simulates a parsing error by passing a directory path instead of a file, 
    and verifies that the function returns None without raising an exception.
    """
    # Use a directory path to trigger exception
    dir_path = tmp_path
    result = parse_vcf_file(dir_path)

    assert result is None

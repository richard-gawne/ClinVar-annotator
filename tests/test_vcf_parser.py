import unittest
import tempfile
from pathlib import Path
from clinvar_anno_core.modules.vcf_parser import parse_vcf_file


class TestParseVcfFile(unittest.TestCase):

    def create_temp_vcf(self, content: str) -> Path:
        """Helper to create a temporary VCF file."""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".vcf", mode="w")
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)

    def test_valid_vcf_parsing(self):
        """Ensure variants are parsed correctly from a normal VCF file."""
        content = (
            "##fileformat=VCFv4.2\n"
            "#CHROM POS ID REF ALT\n"
            "chr1\t12345\t.\tA\tT\n"
            "chr2\t67890\t.\tG\tC\n"
        )
        vcf_path = self.create_temp_vcf(content)

        result = parse_vcf_file(vcf_path)

        self.assertEqual(result, [
            "chr1:12345:A:T",
            "chr2:67890:G:C"
        ])

    def test_space_delimited_lines(self):
        """Ensure parser works for VCF lines separated by spaces instead of tabs."""
        content = (
            "##header\n"
            "chr3  11111  id  T  G\n"
        )
        vcf_path = self.create_temp_vcf(content)

        result = parse_vcf_file(vcf_path)

        self.assertEqual(result, ["chr3:11111:T:G"])

    def test_skips_headers_and_empty_lines(self):
        """Ensure headers (#...), blank lines, and whitespace lines are skipped."""
        content = (
            "##fileformat=VCFv4.2\n"
            "# Another header\n"
            "\n"
            "   \n"
            "chr1\t200\t.\tC\tA\n"
        )
        vcf_path = self.create_temp_vcf(content)

        result = parse_vcf_file(vcf_path)

        self.assertEqual(result, ["chr1:200:C:A"])

    def test_insufficient_fields(self):
        """Ensure lines with fewer than 5 fields are ignored."""
        content = (
            "# header\n"
            "chr1\t123\n"          # too few fields → skipped
            "chr2\t456\t.\tA\tG\n"  # valid
        )
        vcf_path = self.create_temp_vcf(content)

        result = parse_vcf_file(vcf_path)

        self.assertEqual(result, ["chr2:456:A:G"])

    def test_missing_file(self):
        """Ensure missing file returns None."""
        fake_path = Path("nonexistent_file_12345.vcf")
        result = parse_vcf_file(fake_path)
        self.assertIsNone(result)

    def test_exception_handling(self):
        """Force an exception by passing a directory instead of a file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir)
            result = parse_vcf_file(dir_path)
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()


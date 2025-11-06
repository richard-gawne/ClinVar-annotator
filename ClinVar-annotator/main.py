"""
ClinVar Annotation Pipeline:
Parse a VCF file
Convert each variant to genomic HGVS format via VariantValidator
Query ClinVar for annotations using NCBI E-utilities
Output final dictionary of annotations per variant
"""

from pathlib import Path
import requests
import json
import time
from modules.clinvar_extractor import ClinVarSearch
from modules.vcf_parser import parse_vcf_file
from utils.variant_validation import get_hgvs

def run_annotation_pipeline(vcf_file_path: str, genome_build: str = "GRCh38"):
    vcf_path = Path(vcf_file_path)
    print(f"Reading VCF file: {vcf_path}")

    parsed_variants = parse_vcf_file(vcf_path)
    if not parsed_variants:
        print("No valid variants found in the VCF file.")
        return {}

    print(f"Parsed {len(parsed_variants)} variants successfully.\n")

    clinvar_client = ClinVarSearch()
    annotated_results = {}

    for variant_str in parsed_variants:
        print(f"Processing variant: {variant_str}")

        genomic_hgvs, transcript_hgvs = get_hgvs(variant_str, genome_build)
        print(f"Genomic HGVS: {genomic_hgvs or 'N/A'}")
        print(f"Transcript HGVS: {transcript_hgvs or 'N/A'}")

        if not genomic_hgvs:
            print(f"Skipping {variant_str} — no valid HGVS found.\n")
            continue

        time.sleep(0.3)
        annotation_data = clinvar_client.search_by_hgvs(genomic_hgvs)

        if annotation_data:
            annotation_data["genomic_hgvs"] = genomic_hgvs
            annotation_data["transcript_hgvs"] = transcript_hgvs or "N/A"
            annotated_results[variant_str] = annotation_data
            print(f"  ✅ ClinVar match found: {annotation_data.get('variation_name', 'N/A')}\n")
        else:
            print(f"No ClinVar entry found for {variant_str}.\n")

    print("\nPipeline complete.\n")
    return annotated_results


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python main.py <path_to_vcf> [GRCh37|GRCh38]")
        sys.exit(1)

    vcf_path_arg = sys.argv[1]
    genome_build_arg = sys.argv[2] if len(sys.argv) > 2 else "GRCh38"

    results = run_annotation_pipeline(vcf_path_arg, genome_build_arg)

    if results:
        print("\n========= FINAL PIPELINE OUTPUT =========\n")
        print(json.dumps(results, indent=2))
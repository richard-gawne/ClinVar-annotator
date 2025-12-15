"""
Variant Annotation Pipeline Orchestrator

This master script coordinates the complete variant annotation workflow:
1. Parse VCF file to extract variants
2. Convert variants to HGVS nomenclature using VariantValidator
3. Query gnomAD for allele frequency data
4. Search ClinVar for clinical annotations
5. Consolidate all data into structured dictionaries for frontend consumption
"""

import json
from pathlib import Path
from typing import Dict, List

from clinvar_anno_core.modules.clinvar_extractor import ClinVarSearch
from clinvar_anno_core.modules.gnomad_allele_freq import extract_gnomad_afs_from_vcf
from clinvar_anno_core.modules.variant_validation import HgvsConverter
from clinvar_anno_core.modules.vcf_parser import parse_vcf_file
from clinvar_anno_core.utils.logger import logger


class VariantAnnotationPipeline:
    """
    Orchestrates the complete variant annotation workflow from VCF to annotated data.

    This pipeline integrates four core modules:
    - VCF Parser: Extracts variants in coordinate format
    - HGVS Converter: Converts coordinates to HGVS nomenclature
    - gnomAD Fetcher: Retrieves population allele frequencies
    - ClinVar Searcher: Fetches annotations

    Attributes:
        hgvs_converter (HgvsConverter): Instance for converting variants to HGVS notation
        clinvar_searcher (ClinVarSearch): Instance for searching ClinVar database
    """

    def __init__(self):
        """
        Initialize all pipeline components.

        Creates instances of HgvsConverter and ClinVarSearch for use throughout
        the annotation workflow.
        """
        self.hgvs_converter = HgvsConverter()
        self.clinvar_searcher = ClinVarSearch()

    def process_vcf(self, vcf_path: Path) -> Dict[str, Dict]:
        """
        Execute complete annotation pipeline on a VCF file.
        
        This method orchestrates the full workflow: parsing the VCF, converting to HGVS,
        fetching gnomAD frequencies, searching ClinVar, and consolidating all data into
        a structured format.

        Args:
            vcf_path (Path): Path to input VCF file

        Returns:
            Dict[str, Dict]: Dictionary with variant coordinates (e.g., "1:55516888:A:T")
                            as keys and annotation data dictionaries as values. Returns
                            empty dict if VCF parsing fails or no variants found.
        
        Raises:
            FileNotFoundError: If the VCF file does not exist.
            ValueError: If the VCF file is malformed or cannot be parsed.
            RuntimeError: If HGVS conversion or ClinVar lookup fails.
        """
        # Step 1: Parse VCF file
        variant_coordinates = parse_vcf_file(vcf_path)
        if not variant_coordinates:
            return {}

        # Step 2: Get gnomAD allele frequencies
        allele_freq_data = extract_gnomad_afs_from_vcf(vcf_path)

        # Step 3: Convert to HGVS nomenclature
        hgvs_conversions = self.hgvs_converter.batch_convert(variant_coordinates)

        # Step 4: Search ClinVar and consolidate all data
        annotated_variants = {}

        for hgvs_data in hgvs_conversions:
            variant_coord = hgvs_data["input_variant"]
            genomic_hgvs = hgvs_data["genomic_hgvs"]
            transcript_hgvs = hgvs_data["transcript_hgvs"]

            # Skip if no MANE Select c. HGVS available
            if not transcript_hgvs:
                continue

            # Try c. HGVS first for ClinVar search
            clinvar_result = None
            if transcript_hgvs:
                clinvar_result = self.clinvar_searcher.search_by_hgvs(transcript_hgvs)

            # Fallback to g. HGVS if c. fails
            if not clinvar_result and genomic_hgvs:
                clinvar_result = self.clinvar_searcher.search_by_hgvs(genomic_hgvs)

            # Skip if ClinVar has no match for this variant
            if not clinvar_result:
                continue

            # Build annotation dict in required format
            variant_annotation = self._format_variant_annotation(
                variant_coord,
                genomic_hgvs,
                transcript_hgvs,
                clinvar_result,
                allele_freq_data,
            )

            # Use variant coordinate as dictionary key
            annotated_variants[variant_coord] = variant_annotation

        return annotated_variants

    def _format_variant_annotation(
        self,
        variant_coord: str,
        genomic_hgvs: str,
        transcript_hgvs: str,
        clinvar_data: Dict,
        allele_freq_data: List[Dict],
    ) -> Dict:
        """
         Format variant annotation into required dictionary structure.
        
        This method consolidates data from multiple sources (HGVS conversions, ClinVar,
        gnomAD) into a single structured dictionary suitable for frontend consumption.

        Args:
            variant_coord (str): Variant coordinate string 
            genomic_hgvs (str): Genomic HGVS notation 
            transcript_hgvs (str): Transcript HGVS notation 
            clinvar_data (Dict): ClinVar search result dictionary containing clinical
                                annotations, gene info, and variant details
            allele_freq_data (List[Dict]): List of allele frequency dictionaries from gnomAD

        Returns:
            Dict: Formatted variant annotation dictionary containing all consolidated data
                 including ClinVar annotations, HGVS notations, gene information, and
                 gnomAD allele frequencies.

        Raises:
            KeyError: If expected keys are missing from ClinVar or gnomAD data.
            IndexError: If the variant coordinate format is invalid.
        """
        # Parse variant coordinate
        parts = variant_coord.split(":")
        chrom = parts[0]
        position = parts[1]

        # Extract gene information from ClinVar data
        genes = []
        if "genes" in clinvar_data and clinvar_data["genes"]:
            genes = [
                {
                    "symbol": gene.get("symbol", ""),
                    "geneid": gene.get("geneid", ""),
                    "strand": gene.get("strand", ""),
                    "hgnc_id": gene.get("hgnc_id", ""),
                }
                for gene in clinvar_data["genes"]
            ]

        # Build the formatted annotation
        annotation = {
            "uid": clinvar_data.get("variation_id", ""),
            "obj_type": clinvar_data.get("obj_type", "single nucleotide variant"),
            "variation_name": clinvar_data.get("variation_name", ""),
            "protein_change": clinvar_data.get("protein_change", ""),
            "molecular_consequences": clinvar_data.get("molecular_consequences", []),
            "genes": genes,
            "assembly_name": clinvar_data.get("assembly_name", "GRCh38"),
            "chr": chrom.replace("chr", ""),
            "band": clinvar_data.get("band", ""),
            "start": position,
            "stop": position,
            "clinical_significance": clinvar_data.get("clinical_significance", ""),
            "last_evaluated": clinvar_data.get("last_evaluated", ""),
            "review_status": clinvar_data.get("review_status", ""),
            "trait_name": clinvar_data.get("trait_name", ""),
            "trait_omim": clinvar_data.get("trait_omim", ""),
            "variation_id": clinvar_data.get("variation_id", ""),
            "genomic_hgvs": genomic_hgvs or "",
            "transcript_hgvs": transcript_hgvs or "",
        }

        # Add allele frequency data if available
        matching_af = next(
            (af for af in allele_freq_data if af["variant_id"] == variant_coord), None
        )
        if matching_af:
            annotation["gnomad_genome_af"] = matching_af.get("genome_af")
            annotation["gnomad_exome_af"] = matching_af.get("exome_af")
            annotation["gnomad_total_af"] = matching_af.get("total_af")

        return annotation

    def save_results(
        self, annotated_variants: Dict[str, Dict], output_path: Path
    ) -> None:
        """
        Save annotated variant data to JSON file for frontend consumption.
        
        This method writes the complete annotation dictionary to a JSON file with
        proper formatting and UTF-8 encoding.

        Args:
            annotated_variants (Dict[str, Dict]): Dictionary of variant annotations
                                                  keyed by variant coordinate
            output_path (Path): Path where JSON output should be saved
            
        Returns:
            None

        Raises:
            OSError: If the output file cannot be written.
            TypeError: If annotated_variants is not JSON serialisable.
        """
        # Write dictionary directly (no metadata wrapper needed for downstream compatibility)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(annotated_variants, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Saved {len(annotated_variants)} annotated variants to {output_path}"
        )

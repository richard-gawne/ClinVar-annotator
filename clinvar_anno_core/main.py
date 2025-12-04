"""
Variant Annotation Pipeline Orchestrator

This master script coordinates the complete variant annotation workflow:
1. Parse VCF file to extract variants
2. Convert variants to HGVS nomenclature using VariantValidator
3. Query gnomAD for allele frequency data
4. Search ClinVar for clinical annotations
5. Consolidate all data into structured dictionaries for frontend consumption
"""

from pathlib import Path
from typing import List, Dict
import json
from datetime import datetime

from modules.vcf_parser import parse_vcf_file
from modules.variant_validation import HgvsConverter
from modules.gnomad_allele_freq import extract_gnomad_afs_from_vcf
from modules.clinvar_extractor import ClinVarSearch
from utils.logger import logger

class VariantAnnotationPipeline:
    """
    Orchestrates the complete variant annotation workflow from VCF to annotated data.
    
    This pipeline integrates four core modules:
    - VCF Parser: Extracts variants in coordinate format
    - HGVS Converter: Converts coordinates to HGVS nomenclature
    - gnomAD Fetcher: Retrieves population allele frequencies
    - ClinVar Searcher: Fetches annotations
    """
    
    def __init__(self):
        """Initialize all pipeline components."""
        self.hgvs_converter = HgvsConverter()
        self.clinvar_searcher = ClinVarSearch()
    
    
    def process_vcf(self, vcf_path: Path) -> Dict[str, Dict]:
        """
        Execute complete annotation pipeline on a VCF file.
        
        Args:
            vcf_path: Path to input VCF file
            
        Returns:
            Dictionary with variant coordinates as keys and annotation data as values
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
            variant_coord = hgvs_data['input_variant']
            genomic_hgvs = hgvs_data['genomic_hgvs']
            transcript_hgvs = hgvs_data['transcript_hgvs']
            
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
                allele_freq_data
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
        allele_freq_data: List[Dict]
    ) -> Dict:
        """
        Format variant annotation into required dictionary structure.
        
        Args:
            variant_coord: Variant coordinate string (e.g., "chr1:219915839:G:A")
            genomic_hgvs: Genomic HGVS notation
            transcript_hgvs: Transcript HGVS notation
            clinvar_data: ClinVar search result dictionary
            allele_freq_data: List of allele frequency dictionaries
            
        Returns:
            Formatted variant annotation dictionary
        """
        # Parse variant coordinate
        parts = variant_coord.split(':')
        chrom = parts[0]
        position = parts[1]
        
        # Extract gene information from ClinVar data
        genes = []
        if 'genes' in clinvar_data and clinvar_data['genes']:
            genes = [
                {
                    "symbol": gene.get('symbol', ''),
                    "geneid": gene.get('geneid', ''),
                    "strand": gene.get('strand', '')
                }
                for gene in clinvar_data['genes']
            ]
        
        # Build the formatted annotation
        annotation = {
            "uid": clinvar_data.get('variation_id', ''),
            "obj_type": clinvar_data.get('obj_type', 'single nucleotide variant'),
            "variation_name": clinvar_data.get('variation_name', ''),
            "protein_change": clinvar_data.get('protein_change', ''),
            "molecular_consequences": clinvar_data.get('molecular_consequences', []),
            "genes": genes,
            "assembly_name": clinvar_data.get('assembly_name', 'GRCh38'),
            "chr": chrom.replace('chr', ''),
            "band": clinvar_data.get('band', ''),
            "start": position,
            "stop": position,
            "clinical_significance": clinvar_data.get('clinical_significance', ''),
            "last_evaluated": clinvar_data.get('last_evaluated', ''),
            "review_status": clinvar_data.get('review_status', ''),
            "trait_name": clinvar_data.get('trait_name', ''),
            "trait_omim": clinvar_data.get('trait_omim', ''),
            "variation_id": clinvar_data.get('variation_id', ''),
            "genomic_hgvs": genomic_hgvs or '',
            "transcript_hgvs": transcript_hgvs or ''
        }
        
        # Add allele frequency data if available
        matching_af = next(
            (af for af in allele_freq_data if af['variant_id'] == variant_coord),
            None
        )
        if matching_af:
            annotation['gnomad_genome_af'] = matching_af.get('genome_af')
            annotation['gnomad_exome_af'] = matching_af.get('exome_af')
            annotation['gnomad_total_af'] = matching_af.get('total_af')
        
        # Add HGNC ID if available in ClinVar data
        if 'hgnc_id' in clinvar_data:
            annotation['hgnc_id'] = clinvar_data['hgnc_id']
        
        return annotation
    
    
    def save_results(self, annotated_variants: Dict[str, Dict], output_path: Path) -> None:
        """
        Save annotated variant data to JSON file for frontend consumption.
        
        Args:
            annotated_variants: Dictionary of variant annotations (keyed by coordinate)
            output_path: Path where JSON output should be saved
        """
        # Write dictionary directly (no metadata wrapper needed for downstream compatibility)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(annotated_variants, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(annotated_variants)} annotated variants to {output_path}")
    
    
    def generate_summary_report(self, annotated_variants: Dict[str, Dict]) -> Dict:
        """
        Generate a summary report of annotation results.
        
        Args:
            annotated_variants: Dictionary of variant annotations
            
        Returns:
            Dictionary containing summary statistics
        """

        # Initialise category containers
        pathogenic_variants = []
        benign_variants = []
        vus_variants = []
        
        # Loop over each annotated variant and categorise based on clinical significance
        for variant_coord, variant_data in annotated_variants.items():
            significance = variant_data.get('clinical_significance', '').lower()
            
            # Classify variant based on ClinVar terms
            if 'pathogenic' in significance and 'benign' not in significance:
                pathogenic_variants.append(variant_coord)
            elif 'benign' in significance:
                benign_variants.append(variant_coord)
            elif 'uncertain' in significance or 'vus' in significance:
                vus_variants.append(variant_coord)
        
        # Build summary dictionary with counts and variant identifiers for reporting
        summary = {
            'total_variants': len(annotated_variants),
            'pathogenic_count': len(pathogenic_variants),
            'benign_count': len(benign_variants),
            'vus_count': len(vus_variants),
            'pathogenic_variants': pathogenic_variants,
            'benign_variants': benign_variants,
            'vus_variants': vus_variants
        }
        
        # Log results as a summary
        logger.info("=" * 80)
        logger.info("ANNOTATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total variants: {summary['total_variants']}")
        logger.info(f"Pathogenic: {summary['pathogenic_count']}")
        logger.info(f"Benign: {summary['benign_count']}")
        logger.info(f"VUS: {summary['vus_count']}")
        logger.info("=" * 80)

        return summary


def main():
    """
    Demonstrates usage with example VCF file.
    """
    pipeline = VariantAnnotationPipeline()
    
    vcf_input_path = Path("/home/ubuntu/vscode/ClinVar-annotator/clinvar_anno_core/patient_X.vcf")
    json_output_path = Path("/home/ubuntu/vscode/ClinVar-annotator/clinvar_anno_core/annotated_variants.json")
    
    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    
    annotated_variants = pipeline.process_vcf(vcf_input_path)
    
    if annotated_variants:
        # Print formatted output to terminal
        print("\n" + "="*80)
        print("DICTIONARY PRINTED FOR DEVELOPMENT")
        print("="*80)
        print(json.dumps(annotated_variants, indent=2, ensure_ascii=False))
        print("="*80 + "\n")
        
        pipeline.save_results(annotated_variants, json_output_path)
        pipeline.generate_summary_report(annotated_variants)


if __name__ == "__main__":
    main()
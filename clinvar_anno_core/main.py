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
    
    
    def process_vcf(self, vcf_path: Path) -> List[Dict]:
        """
        Execute complete annotation pipeline on a VCF file.
        
        Args:
            vcf_path: Path to input VCF file
            
        Returns:
            List of dictionaries containing comprehensive variant annotations
        """

        # Step 1: Parse VCF file
        variant_coordinates = parse_vcf_file(vcf_path)
        if not variant_coordinates:
            return []
        
        # Step 2: Get gnomAD allele frequencies
        allele_freq_data = extract_gnomad_afs_from_vcf(vcf_path)
        
        # Step 3: Convert to HGVS nomenclature
        hgvs_conversions = self.hgvs_converter.batch_convert(variant_coordinates)
        
        # Step 4: Search ClinVar and consolidate all data
        annotated_variants = []
        
        for hgvs_data in hgvs_conversions:
            variant_coord = hgvs_data['input_variant']
            genomic_hgvs = hgvs_data['genomic_hgvs']
            transcript_hgvs = hgvs_data['transcript_hgvs']
            
            # Skip if no MANE Select c. HGVS available
            if not transcript_hgvs:
                continue

            # Skip if ClinVar has no match for this variant
            clinvar_result = None
            if genomic_hgvs:
                clinvar_result = self.clinvar_searcher.search_by_hgvs(genomic_hgvs)
            if not clinvar_result and transcript_hgvs:
                clinvar_result = self.clinvar_searcher.search_by_hgvs(transcript_hgvs)

            if not clinvar_result:
                continue

            # Build annotation dict (only if both HGVS + ClinVar exist)
            variant_annotation = {
                'variant_coordinate': variant_coord,
                'genomic_hgvs': genomic_hgvs,
                'transcript_hgvs': transcript_hgvs,
                'allele_frequency': None,
                'clinvar_data': clinvar_result,
                'processing_status': 'complete'
            }

            # Add allele frequency data
            matching_af = next(
                (af for af in allele_freq_data if af['variant_id'] == variant_coord),
                None
            )
            if matching_af:
                variant_annotation['allele_frequency'] = {
                    'genome_af': matching_af['genome_af'],
                    'exome_af': matching_af['exome_af'],
                    'total_af': matching_af['total_af']
                }
            
           # Try c. HGVS first
            if transcript_hgvs:
                clinvar_result = self.clinvar_searcher.search_by_hgvs(transcript_hgvs)

            # Fallback to g. HGVS if c. fails
            if not clinvar_result and genomic_hgvs:
                clinvar_result = self.clinvar_searcher.search_by_hgvs(genomic_hgvs)

            if clinvar_result:
                variant_annotation['clinvar_data'] = clinvar_result
                variant_annotation['processing_status'] = 'complete'
            else:
                variant_annotation['processing_status'] = 'no_clinvar_data'
            
            annotated_variants.append(variant_annotation)
        
        return annotated_variants
    
    
    def save_results(self, annotated_variants: List[Dict], output_path: Path) -> None:
        """
        Save annotated variant data to JSON file for frontend consumption.
        
        Args:
            annotated_variants: List of variant annotation dictionaries
            output_path: Path where JSON output should be saved
        """

        # Construct top level output dictionary
        output_data = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'total_variants': len(annotated_variants),
                'pipeline_version': '1.0.0'
            },
            'variants': annotated_variants 
        }
        
        # Write structured JSON file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    
    def generate_summary_report(self, annotated_variants: List[Dict]) -> Dict:
        """
        Generate a summary report of annotation results.
        
        Args:
            annotated_variants: List of variant annotation dictionaries
            
        Returns:
            Dictionary containing summary statistics
        """

        # Initialise category containers
        pathogenic_variants = []
        benign_variants = []
        vus_variants = []
        
        # Loop over each annotated variant and categorise based on clinical significance
        for variant in annotated_variants:
            clinvar_data = variant.get('clinvar_data')
            if clinvar_data:
                significance = clinvar_data.get('clinical_significance', '').lower()
                
                # Classify variant based on ClinVar terms
                if 'pathogenic' in significance and 'benign' not in significance:
                    pathogenic_variants.append(variant)
                elif 'benign' in significance:
                    benign_variants.append(variant)
                elif 'uncertain' in significance or 'vus' in significance:
                    vus_variants.append(variant)
        
        # Build summary dictionary with counts and variant identifiers for reporting
        summary = {
            'total_variants': len(annotated_variants),
            'pathogenic_count': len(pathogenic_variants),
            'benign_count': len(benign_variants),
            'vus_count': len(vus_variants),
            'pathogenic_variants': [v['variant_coordinate'] for v in pathogenic_variants],
            'benign_variants': [v['variant_coordinate'] for v in benign_variants],
            'vus_variants': [v['variant_coordinate'] for v in vus_variants]
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
        pipeline.save_results(annotated_variants, json_output_path)
        
    pipeline.generate_summary_report(annotated_variants)
     


if __name__ == "__main__":
    main()
"""
This module provides utilities for parcing VCF (variant call format)
files and returning a list of formatted variants
"""

import traceback
from pathlib import Path
from clinvar_anno_core.utils.logger import logger

def parse_vcf_file(vcf_filepath: Path):
    """
    Parse a VCF file and extract variants in the format: chrom:position:REF:ALT
    
    Args:
        - vcf_filepath (Path): Path to the VCF file
        
    Returns:
        - list (str) of formatted variants (chrom:position:REF:ALT)
    """
    variants = []
    
    try:
        with open(vcf_filepath, 'r', encoding='utf-8-sig') as f:
            logger.info(f"User provided input vcf file: {vcf_filepath}")
            for line_num, line in enumerate(f, 1):
                # Remove any trailing whitespace and carriage returns
                line = line.rstrip('\r\n')
                
                # Skip header lines
                if line.startswith('#'):
                    continue
                
                # Skip empty lines
                if not line.strip():
                    continue
                
                # Parse VCF line - handle both tab and space delimiters
                fields = line.split('\t')
                
                # If tab split didn't work, try multiple spaces
                if len(fields) < 5:
                    fields = line.split()

                if len(fields) >= 5:
                    # Ensures current line has at least 5 fields
                    # before extracting values
                    chrom = fields[0].strip()
                    pos = fields[1].strip()
                    ref = fields[3].strip()
                    alt = fields[4].strip()

                    # Formats variants
                    variant = f"{chrom}:{pos}:{ref}:{alt}"
                    variants.append(variant)
                    
                    logger.debug(f"Added variant: {variant}")
                else:
                    logger.debug(
                        f"Skipping line {line_num} "
                        f"(insufficient fields: {len(fields)})"
                    )
    
    except FileNotFoundError:
        logger.error(f"Error: File {vcf_filepath} not found")
        return None
    except Exception as e:
        logger.error(f"Error parsing file: {e}")
        traceback.print_exc()
        return None
    
    logger.info(f"Finished parsing file: {vcf_filepath}. "
                f"Total variants extracted: {len(variants)}")
    
    return variants


# Example usage
if __name__ == "__main__":
    result = parse_vcf_file("/home/ubuntu/software_project/ClinVar-annotator/data/Patient1.vcf")
    print(result)
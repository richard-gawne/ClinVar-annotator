from pathlib import Path

def parse_vcf_file(vcf_filepath: Path, debug: bool=False):
    """
    Parse a VCF file and extract variants in the format: chrom:position:REF:ALT
    
    Args:
        vcf_filepath: Path to the VCF file
        debug: If True, print debugging information
        
    Returns:
         list of formatted variants

    Raises:

    """
    variants = []
    
    try:
        with open(vcf_filepath, 'r', encoding='utf-8-sig') as f:
            for line_num, line in enumerate(f, 1):
                # Remove any trailing whitespace and carriage returns
                line = line.rstrip('\r\n')
                
                if debug:
                    print(f"Line {line_num}: '{line[:100]}'")  # Print first 100 chars
                
                # Skip header lines
                if line.startswith('#'):
                    if debug:
                        print(f"  -> Skipped (header)")
                    continue
                
                # Skip empty lines
                if not line.strip():
                    if debug:
                        print(f"  -> Skipped (empty)")
                    continue
                
                # Parse VCF line - handle both tab and space delimiters
                fields = line.split('\t')
                
                # If tab split didn't work, try multiple spaces
                if len(fields) < 5:
                    fields = line.split()
                
                if debug:
                    print(f"  -> Number of fields: {len(fields)}")
                    print(f"  -> Fields: {fields[:5] if len(fields) >= 5 else fields}")
                
                if len(fields) >= 5:
                    # Ensures current line has at least 5 fields before extracting values
                    chrom = fields[0].strip()
                    pos = fields[1].strip()
                    ref = fields[3].strip()
                    alt = fields[4].strip()
                    
                    variant = f"{chrom}:{pos}:{ref}:{alt}"
                    # Formats variants
                    variants.append(variant)
                    
                    if debug:
                        print(f"  -> Added variant: {variant}")
                else:
                    if debug:
                        print(f"  -> Skipped (insufficient fields: {len(fields)})")
    
    except FileNotFoundError:
        print(f"Error: File {vcf_filepath} not found")
        return None
    except Exception as e:
        print(f"Error parsing file: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    return variants


# Example usage
if __name__ == "__main__":
    result = parse_vcf_file("/home/ubuntu/software_project/ClinVar-annotator/data/Patient1.vcf")
    print(result)



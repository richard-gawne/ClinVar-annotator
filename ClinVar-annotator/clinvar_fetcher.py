import requests

def get_clinvar_data(chrom, pos, ref, alt):
    """
    Query MyVariant.info API for a variant using hg37 genomic coordinates and return ClinVar data.

    Parameters:
        chrom (str): Chromosome (e.g., '1')
        pos (int): 1-based genomic position
        ref (str): Reference allele
        alt (str): Alternate allele

    Returns:
        dict: ClinVar annotation data (if available)
    """
    # Construct HGVS notation for MyVariant.info query
    hgvs = f"chr{chrom}:g.{pos}{ref}>{alt}"

    url = f"https://myvariant.info/v1/variant/{hgvs}"
    params = {"fields": "clinvar"}  # Only retrieve clinvar field
    response = requests.get(url, params=params)

    if response.status_code == 200:  # Success status code
        data = response.json()  # Format as JSON
        return data.get("clinvar", {})
    else:
        print(f"Error: {response.status_code} - {response.text}")  # Message for failed requests
        return None

# Example usage

variant = {"chrom": "17", "pos": 44060786, "ref": "G", "alt": "T"}  # Example variants
clinvar_info = get_clinvar_data(variant["chrom"], variant["pos"], variant["ref"], variant["alt"])
print(clinvar_info)

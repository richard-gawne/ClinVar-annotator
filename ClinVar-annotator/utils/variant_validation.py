"""
Variant Validator Utility
-------------------------
Converts genomic variant (e.g., chr11:2164285:C:T) to
genomic (g.) and transcript (c.) HGVS using the VariantValidator API.
"""

import requests

def get_hgvs(variant_str: str, genome_build: str = "GRCh38"):
    """
    Convert a variant string to HGVS notation using VariantValidator.
    
    Returns:
        tuple: (genomic_hgvs, transcript_hgvs)
    """
    base_urls = [
        "https://rest.variantvalidator.org",
        "https://api.variantvalidator.org"
    ]

    for base in base_urls:
        # /VariantFormatter/variantformatter/{genome_build}/{variant_description}/{transcript_model}/{select_transcripts}/{checkonly}
        api_url = (
            f"{base}/VariantFormatter/variantformatter/"
            f"{genome_build}/{variant_str}/refseq/mane_select/False?content-type=application/json"
        )

        try:
            response = requests.get(api_url, timeout=20)
            response.raise_for_status()
            data = response.json()

            # Extract top-level variant data
            inner = data.get(variant_str, {}).get(variant_str, {})
            genomic_hgvs = inner.get("g_hgvs")

            # Extract transcript HGVS from "hgvs_t_and_p" field (newer API format)
            transcript_hgvs = None
            if "hgvs_t_and_p" in inner:
                for tx_id, tx_data in inner["hgvs_t_and_p"].items():
                    t_hgvs = tx_data.get("t_hgvs")
                    if t_hgvs:
                        transcript_hgvs = t_hgvs
                        break

            return genomic_hgvs, transcript_hgvs

        except requests.exceptions.RequestException as e:
            print(f"[Error] HGVS conversion failed for {variant_str} using {base}: {e}")

    return None, None
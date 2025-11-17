import requests
from pathlib import Path
from typing import List, Optional, Dict
from vcf_parser import parse_vcf_file  # Make sure this module exists in your project


def format_significant_figures(value: Optional[float], sig_figs: int = 4) -> Optional[str]:
    """
    Convert float to a string with N significant figures, without scientific notation.
    """
    if value is None:
        return None
    from math import log10, floor

    if value == 0:
        return "0"

    digits = sig_figs - int(floor(log10(abs(value)))) - 1
    return f"{value:.{digits}f}"


def query_gnomad(variant_id: str, dataset_id: str = "gnomad_r4") -> Optional[Dict]:
    """
    Query gnomAD GraphQL API for a given variant ID.
    """
    endpoint = "https://gnomad.broadinstitute.org/api/graphql"

    query = """
    query VariantQuery($variantId: String!, $datasetId: DatasetId!) {
      variant(variantId: $variantId, dataset: $datasetId) {
        variantId
        genome { ac an af }
        exome { ac an af }
      }
    }
    """

    payload = {
        "query": query,
        "variables": {
            "variantId": variant_id,
            "datasetId": dataset_id
        }
    }

    try:
        response = requests.post(endpoint, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        return data.get("data", {}).get("variant")
    except Exception as e:
        print(f"[gnomAD Error] {variant_id}: {e}")
        return None


def get_af_summary(variant_id: str, variant_data: Optional[Dict]) -> Dict:
    """
    Format gnomAD data to a clean dictionary with 9 significant figures.
    """
    result = {
        "variant_id": variant_id,
        "genome_af": None,
        "exome_af": None,
        "total_af": None
    }

    if not variant_data:
        return result

    genome = variant_data.get("genome") or {}
    exome = variant_data.get("exome") or {}

    genome_ac = genome.get("ac", 0)
    genome_an = genome.get("an", 0)
    genome_af = genome.get("af")

    exome_ac = exome.get("ac", 0)
    exome_an = exome.get("an", 0)
    exome_af = exome.get("af")

    total_ac = genome_ac + exome_ac
    total_an = genome_an + exome_an
    total_af = total_ac / total_an if total_an else None

    result.update({
        "genome_af": format_significant_figures(genome_af),
        "exome_af": format_significant_figures(exome_af),
        "total_af": format_significant_figures(total_af)
    })

    return result


def extract_gnomad_afs_from_vcf(vcf_path: Path) -> List[Dict]:
    """
    Given a VCF file path, return gnomAD AF data for each variant.
    """
    af_results = []
    variant_ids = parse_vcf_file(vcf_path)

    for variant_id in variant_ids:
        raw = query_gnomad(variant_id)
        summary = get_af_summary(variant_id, raw)
        af_results.append(summary)

    return af_results

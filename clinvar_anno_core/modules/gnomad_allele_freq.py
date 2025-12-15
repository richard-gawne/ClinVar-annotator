
"""
This module provides functionality to extract allele frequency (AF) data
from the gnomAD database using its GraphQL API.
"""

from math import floor, log10
from pathlib import Path
from typing import Dict, List, Optional

import requests

from clinvar_anno_core.modules.vcf_parser import parse_vcf_file
from clinvar_anno_core.utils.logger import logger



def format_significant_figures(value: Optional[float], sig_figs: int = 4) -> Optional[str]:
    """
    Format an allele frequency value as a string with specified significant figures.
        
    This function converts a float value to a string representation with a specific
    number of significant figures. It handles None values and zero appropriately.
    
    Args:
        value (Optional[float]): The allele frequency value to format. Can be None
                                for missing data.
        sig_figs (int, optional): Number of significant figures to use in formatting.
                                Defaults to 4.
    
    Returns:
        Optional[str]: Formatted string with specified significant figures, "0" for
                    zero values, or None if input value is None.    
    """
    # Return None unchanged- missing AF data
    if value is None:
        return None

    # Do not process sig fig logic on value of 0
    if value == 0:
        return "0"

    # Core calculation logic
    digits = sig_figs - int(floor(log10(abs(value)))) - 1
    return f"{value:.{digits}f}"


def query_gnomad(variant_id: str, dataset_id: str = "gnomad_r4") -> Optional[Dict]:
    """
    Query the gnomAD GraphQL API for a given variant ID.
    
    This function sends a GraphQL query to the gnomAD API to retrieve allele
    frequency data including allele count (AC), allele number (AN), and allele
    frequency (AF) for both genome and exome datasets.

    Args:
        variant_id (str): Variant identifier in gnomAD format (e.g., "1:55516888:A:T")
        dataset_id (str, optional): Dataset to query. Defaults to "gnomad_r4".

    Returns:
        Optional[Dict]: Parsed JSON dictionary containing variant data with genome
                       and exome frequency information, or None if query fails.
    """
    endpoint = "https://gnomad.broadinstitute.org/api/graphql"
    logger.debug(f"Querying gnomAD for variant: {variant_id} (dataset: {dataset_id})")

    # Define GraphQL query to retrieve AF data for genome and exome
    graphql_query = """
    query VariantQuery($variantId: String!, $datasetId: DatasetId!) {
      variant(variantId: $variantId, dataset: $datasetId) {
        variantId
        genome { ac an af }
        exome { ac an af }
      }
    }
    """

    # Construct the request payload with query and input variables
    payload = {
        "query": graphql_query,
        "variables": {
            "variantId": variant_id,
            "datasetId": dataset_id
        }
    }

    try:
        # Send POST request to the gnomAD GraphQL API
        response = requests.post(endpoint, json=payload, timeout=20)
        response.raise_for_status()

        # Parse JSON response and extract the 'variant' field
        response_data = response.json()
        logger.debug(f"Successfully retrieved data for {variant_id}")
        return response_data.get("data", {}).get("variant")

    except Exception as error:
        # Log and return None on any failure
        logger.error(f"[gnomAD Error] {variant_id}: {error}")
        return None


def get_af_summary(variant_id: str, variant_data: Optional[Dict]) -> Dict:
    """
    Summarise allele frequencies from gnomAD for genome, exome, and combined.
    
    This function processes raw gnomAD data to extract and format allele frequencies.
    It calculates a combined total AF from genome and exome data, and formats all
    frequencies to 4 significant figures.

    Args:
        variant_id (str): gnomAD variant identifier (e.g., "1:55516888:A:T")
        variant_data (Optional[Dict]): Data returned by gnomAD API containing genome
                                      and exome frequency information, or None if
                                      query failed.

    Returns:
        Dict: A dictionary with the following keys:
            - variant_id (str): The input variant identifier
            - genome_af (Optional[str]): Genome allele frequency as formatted string
            - exome_af (Optional[str]): Exome allele frequency as formatted string
            - total_af (Optional[str]): Combined allele frequency as formatted string
    """
    # Default result structure- used if variant data is missing or incomplete
    af_summary = {
        "variant_id": variant_id,
        "genome_af": None,
        "exome_af": None,
        "total_af": None
    }

    # Handle cases where no data was returned for the variant
    if not variant_data:
        logger.warning(f"No variant data returned for {variant_id}")
        return af_summary

    # Fallback to empty dicts if variant_data is None (or if genome/exome keys are missing)
    genome_data = (variant_data or {}).get("genome") or {}
    exome_data = (variant_data or {}).get("exome") or {}

    # Extract raw counts and frequencies for genome
    genome_ac = genome_data.get("ac", 0)
    genome_an = genome_data.get("an", 0)
    genome_af = genome_data.get("af")

    # Extract raw counts and frequencies for exome
    exome_ac = exome_data.get("ac", 0)
    exome_an = exome_data.get("an", 0)
    exome_af = exome_data.get("af")

    # Compute total allele frequency (combined genome + exome), if possible
    total_ac = genome_ac + exome_ac
    total_an = genome_an + exome_an
    total_af = total_ac / total_an if total_an else None

    # Format each AF value to 4 significant figures
    af_summary.update({
        "genome_af": format_significant_figures(genome_af, sig_figs=4),
        "exome_af": format_significant_figures(exome_af, sig_figs=4),
        "total_af": format_significant_figures(total_af, sig_figs=4)
    })

    # Log a summary of the results
    logger.info(f"Processed AF for {variant_id} | genome: {af_summary['genome_af']}, "
                f"exome: {af_summary['exome_af']}, total: {af_summary['total_af']}")

    return af_summary


def extract_gnomad_afs_from_vcf(vcf_path: Path) -> List[Dict]:
    """
    Parse a VCF file and extract gnomAD allele frequencies for each variant.
    
    This function reads a VCF file, extracts variant identifiers, queries the
    gnomAD database for each variant, and collects allele frequency summaries.

    Args:
        vcf_path (Path): Path to the VCF file to process

    Returns:
        List[Dict]: A list of dictionaries containing allele frequency summaries
                   for each variant. Each dictionary contains variant_id, genome_af,
                   exome_af, and total_af keys. Returns empty list if VCF parsing fails.

    Raises:
            FileNotFoundError: If the VCF file does not exist.
            ValueError: If the VCF file is malformed.
    """
    logger.info(f"Starting allele frequency extraction for VCF: {vcf_path}")
    allele_frequency_results = []

    try:
        # Parse the VCF and extract a list of variant IDs in "chr:pos:ref:alt" format
        variant_ids = parse_vcf_file(vcf_path)

    except Exception as e:
        # Handle file read or parse errors
        logger.error(f"Failed to parse VCF file {vcf_path}: {e}")
        return allele_frequency_results

    logger.info(f"Found {len(variant_ids)} variants in VCF")

    # Loop through each variant, query gnomAD, and collect AF data
    for index, variant_id in enumerate(variant_ids, start=1):
        logger.debug(f"[{index}/{len(variant_ids)}] Querying variant: {variant_id}")
        variant_data = query_gnomad(variant_id)  # Query gnomAD API for this variant

        # Format the AF data into a clean summary
        af_summary = get_af_summary(variant_id, variant_data)
        allele_frequency_results.append(af_summary)  # Store the results

    logger.info(f"Extracted GnomAD AF: {len(allele_frequency_results)} variants processed")
    return allele_frequency_results

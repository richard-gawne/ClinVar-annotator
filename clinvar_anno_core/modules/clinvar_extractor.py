"""
ClinVar Variant Search and Annotation Module

This module provides functionality to search and retrieve variant information
from the NCBI ClinVar database using E-utilities API. It supports searching
by HGVS nomenclature and retrieves comprehensive variant annotations including
genomic location, clinical significance, gene information, and associated traits.

Classes:
    ClinVarSearch: Main class for ClinVar variant search and annotation
"""

import json
import time
from typing import Dict, List, Optional

import requests

from clinvar_anno_core.utils.logger import logger


class ClinVarSearch:
    """
    Search and retrieve variant information from NCBI ClinVar database.

    This class interfaces with NCBI's E-utilities API and exposes the following methods:
    - search_by_hgvs(): Search ClinVar using HGVS notation
    - search_clinvar(): Execute raw ClinVar esearch queries
    - fetch_variant_details(): Retrieve and parse ClinVar esummary data
    - get_hgnc_id(): Fetch HGNC identifiers for associated genes
    - display_annotations(): Output formatted variant annotations (development use)

    Attributes:
        eutils_base_url (str): Base URL for NCBI E-utilities API
        clinvar_summary_url (str): Esummary endpoint for ClinVar variant details
        gnomad_api_url (str): Base URL for gnomAD API (reserved for future use)
        search_timeout (int): Timeout in seconds for API requests
    """

    def __init__(self, search_timeout: int = 30):
        """
        Initialize the ClinVarSearch object with API endpoints and configuration.

        Args:
            search_timeout (int): Timeout in seconds for API requests. Defaults to 30.
        """
        # Base URL for NCBI E-utilities, used for searching and fetching data from ClinVar
        self.eutils_base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

        # Specific endpoint for retrieving ClinVar summaries by ID
        self.clinvar_summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

        # GraphQL API endpoint for querying variant frequency data from gnomAD
        self.gnomad_api_url = "https://gnomad.broadinstitute.org/api"

        # Maximum number of variant search results to retrieve from the ClinVar API
        self.search_timeout = search_timeout

    def search_by_hgvs(self, hgvs_notation: str) -> Optional[Dict]:
        """
        Search ClinVar using HGVS notation and return parsed variant annotations.

        This method attempts to find variants in ClinVar using the provided HGVS
        expression. It tries both quoted and unquoted search terms to maximize
        the likelihood of finding a match.

        Args:
            hgvs_notation (str): Variant string in HGVS nomenclature
                           (e.g., "NM_000719.6:c.5550G>A")

        Returns:
        Optional[Dict]: Parsed variant annotations for the first matching ClinVar
        variant. If multiple ClinVar records match the HGVS notation, the first
        result returned by ClinVar is used. Returns None if no matching variant
        is found.
        """
        logger.info(f"Searching ClinVar for HGVS notation: {hgvs_notation}")

        # Try both quoted and unquoted search terms for better match probability
        search_terms = [f'"{hgvs_notation}"', hgvs_notation]
        variant_id_list = []

        # Attempt searches with different formatting
        for search_term in search_terms:
            logger.debug(f"Attempting search with term: {search_term}")
            variant_ids = self.search_clinvar(search_term)

            time.sleep(0.4)  # Respect NCBI rate limits

            if variant_ids:
                variant_id_list = variant_ids
                logger.info(
                    f"Found {len(variant_ids)} variant ID(s) "
                    f"using search term: {search_term}"
                )
                break

        # Handle case where no variants are found
        if not variant_id_list:
            logger.warning(
                f"No ClinVar results found for HGVS notation: {hgvs_notation}"
            )
            return None

        # Retrieve details for the first matching variant
        primary_variant_id = variant_id_list[
            0
        ]  # Take the first variant ID from the list of matched results
        if len(variant_id_list) > 1:
            logger.warning(
                f"Multiple ClinVar variants found for {hgvs_notation}; "
                f"using first match (ID={variant_id_list[0]})"
            )
        logger.debug(f"Fetching details for variant ID: {primary_variant_id}")

        # Calls the method to fetch annotation data
        variant_annotations = self.fetch_variant_details(primary_variant_id)
        # Validate that meaningful annotations were retrieved
        if variant_annotations and variant_annotations.get("variation_name") != "N/A":
            logger.info(
                f"Successfully retrieved annotations for variant: "
                f"{variant_annotations.get('variation_name')}"
            )
            return variant_annotations

        logger.warning(f"No valid ClinVar summary retrieved for HGVS: {hgvs_notation}")
        return None

    def search_clinvar(self, search_term: str = None) -> List[str]:
        """
        Execute ClinVar search query and return list of matching variant IDs.
        This method constructs and executes an esearch query against the ClinVar
        database using the provided search term.

        Args:
            search_term (str, optional): Query string to search in ClinVar

        Returns:
            List[str]: List of variant ID strings from ClinVar. Empty list if search fails
            or no results found.
        """
        # Construct the full URL for the ESearch endpoint
        search_url = f"{self.eutils_base_url}/esearch.fcgi"

        # Define query parameters for the search
        search_params = {
            "db": "clinvar",
            "term": search_term,
            "retmode": "json",
        }

        try:
            # Make a GET request to the ClinVar ESearch API with timeout
            response = requests.get(
                search_url, params=search_params, timeout=self.search_timeout
            )

            # If the HTTP response is successful, parse the JSON content of the response
            if response.status_code == 200:
                search_data = response.json()

                # Attempts to extract the list of variant IDs from the response
                id_list = search_data.get("esearchresult", {}).get("idlist", [])

                # Checks if any variant ID was found in the search result
                if id_list:
                    logger.debug(f"Search returned {len(id_list)} variant IDs")
                    return id_list
                else:
                    logger.warning("No variant IDs found in ClinVar search response")
            else:
                logger.error(
                    f"ClinVar search failed with status code: {response.status_code}"
                )

        # Handle timeout
        except requests.exceptions.Timeout:
            logger.error(
                f"Search request timed out after {self.search_timeout} seconds"
            )

        # Handle any other HTTP related errors
        except requests.exceptions.RequestException as request_error:
            logger.error(f"Search request failed: {request_error}")

        # Handle failure when decoding the JSON response
        except json.JSONDecodeError as json_error:
            logger.error(f"Failed to parse search response JSON: {json_error}")

        # Catch any other unanticipated errors to prevent crashes
        except Exception as unexpected_error:
            logger.error(f"Unexpected error during search: {unexpected_error}")

        return []

    def fetch_variant_details(self, clinvar_variant_id: str) -> Optional[Dict]:
        """
        Fetch comprehensive variant details from ClinVar using esummary endpoint.
        This method retrieves the full variant summary from ClinVar and parses
        it into a structured annotation dictionary.

        Args:
            clinvar_variant_id (str): ClinVar variant identifier (UID)

        Returns:
            Optional[Dict]: Parsed annotations dictionary if successful, None if
                            fetch or parse fails. Dictionary contains keys such as
                            'uid', 'variation_name', 'clinical_significance',
                            'genomic_location', 'genes', etc.
        """
        # Parameters to be sent to the ClinVar ESummary API
        summary_params = {"db": "clinvar", "id": clinvar_variant_id, "retmode": "json"}

        # Make a GET request to ClinVars ESummary endpoint with provided parameters
        try:
            response = requests.get(
                self.clinvar_summary_url,
                params=summary_params,
                timeout=self.search_timeout,
            )

            # If the response code is not 200, log an error
            if response.status_code != 200:
                logger.error(
                    f"Failed to fetch variant details. Status code: "
                    f"{response.status_code}"
                )
                return None

            response_data = (
                response.json()
            )  # Parse the JSON body of the response into a Python dictionary

            # Extract the variant specific data from the response
            variant_result = response_data["result"][clinvar_variant_id]
            logger.debug("Successfully retrieved variant summary from ClinVar")

            # Parse the raw result into structured annotations
            parsed_annotations = self._parse_variant_summary(
                variant_result, clinvar_variant_id
            )

            logger.info(
                f"Successfully parsed annotations for variant ID: "
                f"{clinvar_variant_id}"
            )

            return parsed_annotations

        # Catch timeout-specific exceptions when the ClinVar summary request takes too long
        except requests.exceptions.Timeout:
            logger.error(
                f"Variant details request timed out after "
                f"{self.search_timeout} seconds"
            )

        # Catch other general HTTP or connection related issues
        except requests.exceptions.RequestException as request_error:
            logger.error(f"Failed to fetch variant details: {request_error}")

        # Catch issues when the API response cannot be parsed as valid JSON
        except json.JSONDecodeError as json_error:
            logger.error(f"Failed to parse variant details JSON response: {json_error}")

        # Catch any other unexpected error that were not handled above
        except Exception as unexpected_error:
            logger.error(
                f"Unexpected error fetching variant details: {unexpected_error}"
            )

        return None, None

    def get_hgnc_id(
        self, ncbi_gene_id: str, gene_symbol: str = "Unknown"
    ) -> Optional[str]:
        """
        This method queries the HGNC API using the NCBI Entrez Gene ID
        to retrieve the HGNC ID.

        Args:
            ncbi_gene_id (str): NCBI Entrez Gene identifier
            gene_symbol (str, optional): Gene symbol for logging purposes.
                                        Defaults to "Unknown".

        Returns:
            Optional[str]: HGNC identifier string (e.g., "HGNC:1100") if found,
                        None otherwise
        """
        logger.debug(
            "Fetching HGNC ID for gene %s (NCBI Gene ID: %s)",
            gene_symbol,
            ncbi_gene_id,
        )

        # Construct the HGNC API URL using the given NCBI gene ID
        hgnc_api_url = f"https://rest.genenames.org/fetch/entrez_id/{ncbi_gene_id}"

        # Set headers to request a JSON response from the HGNC API
        request_headers = {"Accept": "application/json"}

        # Send a GET request to the HGNC API with a 10 second timeout
        try:
            response = requests.get(hgnc_api_url, headers=request_headers, timeout=10)
            response.raise_for_status()  # Raise an exception for HTTP errors

            hgnc_data = (
                response.json()
            )  # Parse the JSON response body into a Python dictionary
            gene_documents = hgnc_data.get("response", {}).get(
                "docs", []
            )  # Extract the list of gene documents from the API response

            # Check if any gene documents were returned and
            # try to extract the HGNC ID from the first document
            if gene_documents:
                hgnc_id = gene_documents[0].get("hgnc_id")
                if hgnc_id:
                    logger.debug(
                        f"Found HGNC ID: {hgnc_id} for Gene ID: {ncbi_gene_id}"
                    )
                    return hgnc_id
                logger.warning(
                    f"HGNC response missing 'hgnc_id' field for "
                    f"Gene ID: {ncbi_gene_id}"
                )
            else:
                logger.warning(f"No HGNC data found for NCBI Gene ID: {ncbi_gene_id}")

        # Handle different types of errors that may occur during the HGNC API request
        except requests.exceptions.HTTPError as http_error:
            logger.error(f"HGNC API HTTP error: {http_error}")
        except requests.exceptions.Timeout:
            logger.error("HGNC API request timed out after 10 seconds")
        except requests.exceptions.RequestException as request_error:
            logger.error(f"HGNC API request failed: {request_error}")
        except json.JSONDecodeError as json_error:
            logger.error(f"Failed to parse HGNC API response: {json_error}")
        except Exception as unexpected_error:
            logger.error(f"Unexpected error fetching HGNC ID: {unexpected_error}")

        return None

    def _parse_variant_summary(
        self, variant_result: Dict, clinvar_variant_id: str
    ) -> Dict:
        """
        Parse and normalize ClinVar variant summary into structured dictionary.
        This method extracts and organizes variant information from the raw
        ClinVar API response into a standardized format. It safely handles
        missing fields by providing default "N/A" values.

        Args:
            variant_result (Dict): Raw variant data dictionary from ClinVar API
            clinvar_variant_id (str): ClinVar variant identifier for fallback

        Returns:
            Dict: Dictionary containing normalized variant annotations with keys:
                - uid: Variant unique identifier
                - obj_type: Object type in ClinVar
                - variation_name: Variant description/title
                - protein_change: Amino acid change notation
                - molecular_consequences: List of molecular consequence terms
                - genes: List of associated gene dictionaries
                - assembly_name: Reference genome assembly (e.g., "GRCh38")
                - chr: Chromosome identifier
                - band: Chromosomal band location
                - start: Genomic start position
                - stop: Genomic stop position
                - clinical_significance: Clinical interpretation
                - last_evaluated: Date of last clinical review
                - review_status: Level of review/evidence
                - trait_name: Associated condition/phenotype
                - trait_omim: OMIM identifier for associated trait
                - variation_id: ClinVar variation ID
        """
        logger.debug(f"Parsing variant summary for ID: {clinvar_variant_id}")

        # Initialize annotations dictionary with safe defaults
        variant_annotations = {
            "uid": variant_result.get("uid", clinvar_variant_id),
            "obj_type": variant_result.get("obj_type", "N/A"),
            "variation_name": variant_result.get("title", "N/A"),
            "protein_change": variant_result.get("protein_change", "N/A"),
            "molecular_consequences": variant_result.get(
                "molecular_consequence_list", []
            ),
            "genes": [],
            "assembly_name": "N/A",
            "chr": "N/A",
            "band": "N/A",
            "start": "N/A",
            "stop": "N/A",
            "clinical_significance": "N/A",
            "last_evaluated": "N/A",
            "review_status": "N/A",
            "trait_name": "N/A",
            "trait_omim": "N/A",
            "variation_id": str(variant_result.get("variation_id", clinvar_variant_id)),
        }

        # Extract genomic location information (prioritize GRCh38 assembly)
        logger.debug("Extracting genomic location for GRCh38 assembly")
        for variation_set in variant_result.get("variation_set", []):
            for location in variation_set.get("variation_loc", []):
                if location.get("assembly_name") == "GRCh38":
                    variant_annotations["assembly_name"] = location.get(
                        "assembly_name", "N/A"
                    )
                    variant_annotations["chr"] = location.get("chr", "N/A")
                    variant_annotations["band"] = location.get("band", "N/A")
                    variant_annotations["start"] = str(location.get("start", "N/A"))
                    variant_annotations["stop"] = str(location.get("stop", "N/A"))

                    logger.debug(
                        f"Found GRCh38 location: chr{variant_annotations['chr']}:"
                        f"{variant_annotations['start']}-{variant_annotations['stop']}"
                    )
                    break

        # Extract classification data
        logger.debug("Extracting germline classification information")
        germline_classification = variant_result.get("germline_classification", {})

        variant_annotations["clinical_significance"] = germline_classification.get(
            "description", "N/A"
        )
        variant_annotations["last_evaluated"] = germline_classification.get(
            "last_evaluated", "N/A"
        )
        variant_annotations["review_status"] = germline_classification.get(
            "review_status", "N/A"
        )

        logger.debug(
            f"Clinical significance: " f"{variant_annotations['clinical_significance']}"
        )

        # Extract trait and OMIM identifier
        logger.debug("Extracting trait and OMIM information")
        trait_set = germline_classification.get("trait_set", [])

        if trait_set:
            primary_trait = trait_set[0]
            variant_annotations["trait_name"] = primary_trait.get("trait_name", "N/A")

            # Search for OMIM cross-reference
            for cross_reference in primary_trait.get("trait_xrefs", []):
                if cross_reference.get("db_source") == "OMIM":
                    variant_annotations["trait_omim"] = cross_reference.get(
                        "db_id", "N/A"
                    )
                    logger.debug(f"Found OMIM ID: {variant_annotations['trait_omim']}")
                    break

        # Extract gene information and fetch HGNC identifiers
        logger.debug("Extracting gene information")
        gene_count = len(variant_result.get("genes", []))
        logger.debug(f"Found {gene_count} associated gene(s)")

        for gene_entry in variant_result.get("genes", []):
            ncbi_gene_id = gene_entry.get("geneid", "N/A")
            gene_symbol = gene_entry.get("symbol", "N/A")

            # Fetch HGNC ID if NCBI Gene ID is available
            hgnc_identifier = None
            if ncbi_gene_id != "N/A":
                hgnc_identifier = self.get_hgnc_id(ncbi_gene_id, gene_symbol)

            variant_annotations["genes"].append(
                {
                    "symbol": gene_symbol,
                    "geneid": str(ncbi_gene_id),
                    "strand": gene_entry.get("strand", "N/A"),
                    "hgnc_id": hgnc_identifier or "N/A",
                }
            )

            hgnc_status = hgnc_identifier if hgnc_identifier else "not available"
            logger.debug(
                f"Processed gene: {gene_symbol} | NCBI: {ncbi_gene_id} | "
                f"HGNC: {hgnc_status}"
            )

        logger.info(
            f"Successfully parsed variant: {variant_annotations['variation_name']}"
        )

        return variant_annotations

    def display_annotations(self, variant_annotations: Dict) -> None:
        """
        Display formatted variant annotations to the console via logger.

         Args:
            variant_annotations (Dict): Dictionary containing parsed variant annotations

        Returns:
            None
        """
        logger.info("=" * 70)
        logger.info("CLINVAR VARIANT SUMMARY")
        logger.info("=" * 70)

        # Basic variant information
        logger.info(f"UID: {variant_annotations['uid']}")
        logger.info(f"Type: {variant_annotations['obj_type']}")
        logger.info(f"Variation: {variant_annotations['variation_name']}")
        logger.info(f"Protein Change: {variant_annotations['protein_change']}")

        # Genomic location details
        logger.info("")
        logger.info("GENOMIC LOCATION")
        logger.info("-" * 70)
        logger.info(f"Assembly: {variant_annotations['assembly_name']}")
        logger.info(f"Chromosome: {variant_annotations['chr']}")
        logger.info(f"Band: {variant_annotations['band']}")
        logger.info(
            f"Coordinates: {variant_annotations.get('start', 'N/A')}-"
            f"{variant_annotations.get('stop', 'N/A')}"
        )

        # Clinical classification
        logger.info("")
        logger.info("CLINICAL CLASSIFICATION")
        logger.info("-" * 70)
        logger.info(
            f"Clinical Significance: " f"{variant_annotations['clinical_significance']}"
        )
        logger.info(f"Review Status: {variant_annotations['review_status']}")
        logger.info(f"Last Evaluated: {variant_annotations['last_evaluated']}")

        # Associated condition/trait
        logger.info("")
        logger.info("ASSOCIATED CONDITION")
        logger.info("-" * 70)
        logger.info(f"Trait: {variant_annotations['trait_name']}")
        logger.info(f"OMIM ID: {variant_annotations['trait_omim']}")

        # Gene information
        logger.info("")
        logger.info("ASSOCIATED GENES")
        logger.info("-" * 70)
        for gene_info in variant_annotations["genes"]:
            logger.info(
                f"  • {gene_info['symbol']} "
                f"(GeneID: {gene_info['geneid']}, "
                f"Strand: {gene_info['strand']}, "
                f"HGNC ID: {gene_info['hgnc_id']})"
            )

        # Molecular consequences
        logger.info("")
        logger.info("MOLECULAR CONSEQUENCES")
        logger.info("-" * 70)
        for consequence in variant_annotations["molecular_consequences"]:
            logger.info(f"  • {consequence}")

        # External resource links
        logger.info("")
        logger.info("EXTERNAL LINKS")
        logger.info("-" * 70)
        logger.info(
            f"ClinVar: https://www.ncbi.nlm.nih.gov/clinvar/variation/"
            f"{variant_annotations['variation_id']}/"
        )

        if variant_annotations["genes"]:
            primary_gene_id = variant_annotations["genes"][0]["geneid"]
            logger.info(f"Gene: https://www.ncbi.nlm.nih.gov/gene/{primary_gene_id}")

        logger.info("=" * 70)


def main() -> None:
    """
    Main entry point for command-line variant search.

    This function provides an interactive interface for searching ClinVar
    variants by HGVS notation. It prompts the user for input, performs
    the search, and displays the results.

     Returns:
        Optional[Dict]: Search result dictionary if variant found and annotations
                       retrieved successfully, None otherwise.
    """

    # Initialize searcher
    clinvar_searcher = ClinVarSearch()

    # Prompt user for variant input
    variant_input = input("\nEnter variant (HGVS notation): ").strip()

    # Validate input
    if not variant_input:
        logger.error("No variant input provided by user")
        return None

    # Perform search
    search_result = clinvar_searcher.search_by_hgvs(variant_input)

    # Display results
    if search_result:
        clinvar_searcher.display_annotations(search_result)
        logger.info("Variant search completed successfully")
    else:
        logger.warning("Variant search completed but no annotations were retrieved")

    return None

if __name__ == "__main__":
    main()

"""
HGVS Converter Module using VariantValidator API
This module provides functionality to convert genomic coordinates to HGVS
nomenclature using the VariantValidator REST API. It supports conversion to
both genomic (g.) and transcript (c.) HGVS formats.
"""

import json
from typing import Dict, Optional, Tuple, List
import requests
from clinvar_anno_core.utils.logger import logger


class HgvsConverter:
    """
    Convert genomic variants to HGVS notation using VariantValidator API.

    This class interfaces with VariantValidator's REST API to:
    - Convert genomic coordinates to HGVS format
    - Retrieve both genomic (g.) and transcript (c.) HGVS representations
    - Handle MANE Select transcript selection
    """

    def __init__(self):
        """
        Initialise the HgvsConverter with fixed API configuration.
        """
        self.api_endpoint = ["https://rest.variantvalidator.org"]
        self.genome_build = "GRCh38"
        self.transcript_model = "refseq"
        self.select_transcripts = "mane_select"
        self.request_timeout = 20

        logger.info("Initialized HgvsConverter with GRCh38 and refseq")


    def construct_api_url(self, base_url: str, variant_str: str, genome_build: str) -> str:
        """
        Construct the full VariantValidator API URL.

        Args:
            base_url: Base API endpoint URL
            variant_str: Variant in format "chr:pos:ref:alt"
            genome_build: GRCh38

        Returns:
            Complete API URL string
        """

        # Build the full API URL with all required parameters
        api_url = (
            f"{base_url}/VariantFormatter/variantformatter/"
            f"{genome_build}/{variant_str}/{self.transcript_model}/"
            f"{self.select_transcripts}/False?content-type=application/json"
        )
        
        logger.debug(f"Constructed API URL: {api_url}")  # Log the full constructed URL for debugging purposes
        return api_url


    def parse_validator_response(self, response_data: Dict, variant_str: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse VariantValidator API response to extract HGVS notations.

        Args:
            response_data: Parsed JSON response from VariantValidator
            variant_str: Original variant string (used as key in response)

        Returns:
            Tuple of (genomic_hgvs, transcript_hgvs)
        """
    
        # --- Navigate nested response structure from the variant validator API ---

        # First level: use the original variant string as key
        variant_level = response_data.get(variant_str, {})
        
        # Second level: variant_str as key again
        inner_data = variant_level.get(variant_str, {})
        
        # If no data is found at this point, return None for both HGVS values
        if not inner_data:
            logger.warning(f"No data found in response for variant: {variant_str}")
            return None, None


        # --- Extract HGVS ---

        # Extract g. notation
        genomic_hgvs = inner_data.get("g_hgvs")
        
        if genomic_hgvs:
            logger.debug(f"Found genomic HGVS: {genomic_hgvs}")
        else:
            logger.warning("No genomic HGVS found in response")

        # Extract c. notation
        transcript_hgvs = None
        transcript_annotations = inner_data.get("hgvs_t_and_p", {})

        if transcript_annotations:
            # Loop through transcripts to find the MANE select entry
            for transcript_id, annotation in transcript_annotations.items():
                select_status = annotation.get("select_status", {})
                if select_status.get("mane_select", False):
                    c_notation = annotation.get("t_hgvs")  # transcript HGVS (c. notation)
                    if c_notation:
                        transcript_hgvs = c_notation
                        
                        logger.debug(
                            f"Found transcript HGVS: {transcript_hgvs} "
                            f"(transcript: {transcript_id})"
                        )
                        break  

            if not transcript_hgvs:
                logger.warning(
                    f"Skipping variant {variant_str} — no MANE Select transcript available "
                    f"(c. HGVS not found)"
                )
                return None, None  # Stop processing this variant entirely

        return genomic_hgvs, transcript_hgvs


    def convert_to_hgvs(self, variant_str: str) -> Tuple[Optional[str], Optional[str]]:
        """
        This method queries the VariantValidator API to convert genomic
        coordinates into standardized HGVS nomenclature. 

        Args:
            variant_str: "11:2164285:C:T"
            genome_build: GRCh38

        Returns:
            Tuple of (genomic_hgvs, transcript_hgvs)
            - genomic_hgvs: e.g., "NC_000011.10:g.2164285C>T"
            - transcript_hgvs: e.g., "NM_000088.4:c.589G>T"
        """
        
        # Try API endpoint
        for endpoint in self.api_endpoint:
            logger.debug(f"Attempting conversion using endpoint: {endpoint}")
            
            # Construct API URL
            api_url = self.construct_api_url(endpoint, variant_str, self.genome_build)

            try:
                # Execute GET request to VariantValidator API
                response = requests.get(api_url, timeout=self.request_timeout)
                
                # Raise exception for HTTP errors
                response.raise_for_status()
                
                # Parse JSON response
                response_data = response.json()
                
                logger.debug(
                    f"Received response from {endpoint}: "
                    f"{json.dumps(response_data, indent=2)}"
                )

                # Parse response to extract HGVS notations
                genomic_hgvs, transcript_hgvs = self.parse_validator_response(
                    response_data,
                    variant_str
                )

                # Only return if transcript_hgvs is present (MANE select required)
                if transcript_hgvs:
                    logger.info(
                        f"Successfully converted variant using {endpoint}: "
                        f"g_hgvs={genomic_hgvs}, c_hgvs={transcript_hgvs}"
                    )
                    return genomic_hgvs, transcript_hgvs
                else:
                    logger.warning(
                        f"Transcript HGVS (c.) missing — skipping {variant_str}"
                    )
                    return None, None  # Explicit skip
            
            # --- Handle possible errors during the API request and response parsing ---

            except requests.exceptions.Timeout:
                logger.error(
                    f"Request timed out after {self.request_timeout}s "
                    f"for {endpoint}"
                )
                
            except requests.exceptions.HTTPError as http_error:
                logger.error(
                    f"HTTP error from {endpoint}: {http_error} "
                    f"(status: {response.status_code})"
                )
                
            except requests.exceptions.RequestException as request_error:
                logger.error(f"Request failed for {endpoint}: {request_error}")
                
            except json.JSONDecodeError as json_error:
                logger.error(
                    f"Failed to parse JSON response from {endpoint}: {json_error}"
                )
                
            except Exception as unexpected_error:
                logger.error(
                    f"Unexpected error with {endpoint}: {unexpected_error}"
                )

        # Endpoint failure
        logger.error(
            f"API endpoint failed for variant: {variant_str}. "
        )

        return None, None


    def batch_convert(self, variant_list: List[str]) -> List[Dict]:
        """
        Convert a list of variant strings to HGVS notation using GRCh38 and MANE Select.
        This method processes multiple variants in one call by internally using
        the `convert_to_hgvs()` method for each input.
        """

        logger.info(f"Starting batch conversion for {len(variant_list)} variants")
        
        results = []
        
        for index, raw_variant in enumerate(variant_list, start=1):
            logger.debug(f"Converting variant {index}/{len(variant_list)}: {raw_variant}")
            
            # Convert single variant to HGVS format using GRCh38 and MANE Select
            genomic_hgvs, transcript_hgvs = self.convert_to_hgvs(raw_variant)

            # Store result in structured format
            result_entry = {
                "input_variant": raw_variant,
                "genomic_hgvs": genomic_hgvs,
                "transcript_hgvs": transcript_hgvs,
                "conversion_success": bool(genomic_hgvs or transcript_hgvs)  # True if at least one HGVS value was returned
            }

            results.append(result_entry)
            
            logger.debug(
                f"Variant {index}/{len(variant_list)} - "
                f"Success: {result_entry['conversion_success']}"
            )
        
        # Count and log the number of successful conversions
        successful = sum(1 for r in results if r["conversion_success"])
        logger.info(
            f"Batch conversion complete: {successful}/{len(variant_list)} successful"
        )
        
        return results
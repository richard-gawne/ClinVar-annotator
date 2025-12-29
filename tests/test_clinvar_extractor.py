"""
Unit tests for the ClinVarSearch module.
These tests validate the behavior of ClinVarSearch across its public API,
including:
- ClinVar search queries and error handling
- HGVS-based variant lookup workflows
- Retrieval and parsing of variant detail records
- HGNC identifier resolution
- Graceful handling of missing, incomplete, or invalid API responses
- Logging and output formatting
Network interactions with external services (NCBI E-utilities and related APIs)
are mocked to ensure that:
- No real HTTP requests are made
- Tests run deterministically and offline
- Failures indicate logic errors rather than network or service issues
"""

# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

from unittest.mock import Mock, patch

import pytest
import requests

from clinvar_anno_core.modules.clinvar_extractor import ClinVarSearch

@pytest.fixture
def clinvar_searcher():
    """Create a ClinVarSearch instance for use across test cases."""
    return ClinVarSearch()

# --------------------
# ClinVar search tests
# --------------------

def test_search_clinvar_valid(clinvar_searcher):
    """
    Test that searching ClinVar with a known valid HGVS notation returns results.
    Uses a BRCA1 variant that should exist in the ClinVar database.
    """
    results = clinvar_searcher.search_clinvar('"NM_007294.3:c.68_69del"')
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_clinvar_no_results(clinvar_searcher):
    """
    Test that searching with a nonsense query returns an empty list rather than
    crashing or returning None. The method should handle zero results gracefully.
    """
    results = clinvar_searcher.search_clinvar('"definitelynotrealvariant12345"')
    assert isinstance(results, list)
    assert len(results) == 0

@patch('requests.get')
def test_search_clinvar_handles_timeout(mock_get, clinvar_searcher):
    """
    Test: Handles network timeouts (e.g., server slow or unresponsive).
    Goal: Catch Timeout exception and return an empty list gracefully.
    """
    # Simulate a timeout by raising a Timeout exception when requests.get is called
    mock_get.side_effect = requests.exceptions.Timeout

    results = clinvar_searcher.search_clinvar("test_query")
    assert results == []

@patch('requests.get')
def test_search_clinvar_handles_connection_error(mock_get, clinvar_searcher):
    """
    Test: Handles network connection errors (e.g., no internet, bad DNS).
    Goal: Catch ConnectionError and return empty list without crashing.
    """
    # Simulate a connection error (like DNS failure)
    mock_get.side_effect = requests.exceptions.ConnectionError

    results = clinvar_searcher.search_clinvar("test_query")
    assert results == []

# ---------------------
# HGVS Search Workflow
# ---------------------

def test_search_by_hgvs_valid(clinvar_searcher):
    """
    Test the complete search workflow using a valid HGVS notation.
    This tests search_by_hgvs which internally calls search_clinvar and 
    fetch_variant_details, then returns a structured annotation dictionary.
    """
    hgvs = "NM_007294.3:c.68_69del"
    result = clinvar_searcher.search_by_hgvs(hgvs)
    assert isinstance(result, dict)
    assert "variation_name" in result
    assert "clinical_significance" in result

def test_search_by_hgvs_returns_none_when_no_variants_found(clinvar_searcher):
    """
    Test that search_by_hgvs returns None when ClinVar finds no matching variants.
    This verifies the method handles empty search results properly.
    """
    result = clinvar_searcher.search_by_hgvs("NM_999999.99:c.999999A>G")
    assert result is None

# ------------------------
# Variant detail fetching
# ------------------------

def test_fetch_variant_details_valid(clinvar_searcher):
    """
    Test fetching variant details using a known ClinVar ID.
    ID 17661 is a stable variant in the database that should return 
    complete annotation data.
    """
    result = clinvar_searcher.fetch_variant_details("17661")
    assert isinstance(result, dict)
    assert result["variation_name"] != "N/A"
    assert "clinical_significance" in result

def test_fetch_variant_details_with_nonexistent_id_returns_na_dict(clinvar_searcher):
    """
    Test that a non-existent variant ID returns a dict with 'N/A' placeholders.
    """
    result = clinvar_searcher.fetch_variant_details("999999999999")
    assert isinstance(result, dict)
    assert result["variation_name"] == "N/A"

@patch('requests.get')
def test_fetch_variant_details_handles_non_200_response(mock_get, clinvar_searcher):
    """
    Test: Handles non-200 responses for variant details (e.g., variant not found).
    Goal: Return None if HTTP request fails.
    """
    # Simulate HTTP 404 error
    mock_get.return_value.status_code = 404

    result = clinvar_searcher.fetch_variant_details("12345")
    assert result is None

# ---------------
# HGNC ID Lookup
# ---------------

def test_get_hgnc_id_valid(clinvar_searcher):
    """
    Test HGNC ID retrieval for a known NCBI Gene ID.
    Gene ID 672 corresponds to BRCA1, which should have a valid HGNC identifier.
    """
    hgnc_id = clinvar_searcher.get_hgnc_id("672")
    assert isinstance(hgnc_id, str)
    assert hgnc_id.startswith("HGNC:")

def test_get_hgnc_id_invalid(clinvar_searcher):
    """
    Test that requesting an invalid or non-existent gene ID returns None
    rather than raising an exception or returning invalid data.
    """
    hgnc_id = clinvar_searcher.get_hgnc_id("99999999")
    assert hgnc_id is None

@patch('requests.get')
def test_get_hgnc_id_handles_missing_hgnc_id_field(mock_get, clinvar_searcher):
    """
    Test that get_hgnc_id returns None when 'hgnc_id' is missing in the API response.
    Prevents KeyError and handles incomplete data gracefully.
    """
    # Create a fake response with HTTP 200 but missing 'hgnc_id'
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": {
            "docs": [{"symbol": "BRCA1"}]  # 'hgnc_id' key is intentionally missing
        }
    }
    mock_response.raise_for_status = Mock()  # Mock no HTTP error
    mock_get.return_value = mock_response   # requests.get() will return this mock

    # Run the method and check that it returns None
    hgnc_id = clinvar_searcher.get_hgnc_id("672")
    assert hgnc_id is None

# ----------------
# Variant Parsing
# ----------------

def test_parse_variant_summary_minimal(clinvar_searcher):
    """
    Test the parser with minimal required fields to ensure it handles
    sparse data gracefully. All missing fields should default to 'N/A'
    rather than causing KeyErrors or returning None.
    """
    minimal_data = {
        "uid": "1",
        "obj_type": "variation",
        "title": "Test Variant",
        "variation_id": "1",
        "genes": [],
        "variation_set": [],
        "germline_classification": {}
    }

    result = clinvar_searcher._parse_variant_summary(minimal_data, "1")
    assert result["variation_name"] == "Test Variant"
    assert result["clinical_significance"] == "N/A"

# --------------------
# Logging info summary
# --------------------

def test_display_annotations_logs_output(clinvar_searcher, caplog):
    """
    Test that display_annotations logs all expected sections.
    Verifies the formatted output includes key headers and data fields.
    """
    variant = clinvar_searcher.search_by_hgvs("NM_007294.3:c.68_69del")
    assert isinstance(variant, dict)

    with caplog.at_level("INFO"):
        clinvar_searcher.display_annotations(variant)
        assert "CLINVAR VARIANT SUMMARY" in caplog.text
        assert "GENOMIC LOCATION" in caplog.text
        assert "CLINICAL CLASSIFICATION" in caplog.text
        assert "ASSOCIATED GENES" in caplog.text
        assert "MOLECULAR CONSEQUENCES" in caplog.text

# ----------------------
# Initialisation Checks
# ----------------------

def test_clinvar_search_default_timeout():
    """
    Test that ClinVarSearch initializes with default 30 second timeout.
    """
    clinvar_searcher = ClinVarSearch()
    assert clinvar_searcher.search_timeout == 30

def test_clinvar_search_initializes_urls():
    """
    Test that ClinVarSearch sets up all required API endpoint URLs.
    """
    clinvar_searcher = ClinVarSearch()
    assert "eutils.ncbi.nlm.nih.gov" in clinvar_searcher.eutils_base_url
    assert "esummary.fcgi" in clinvar_searcher.clinvar_summary_url
    assert "gnomad.broadinstitute.org" in clinvar_searcher.gnomad_api_url

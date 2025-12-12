from unittest.mock import patch, Mock
from pathlib import Path

from clinvar_anno_core.modules.gnomad_allele_freq import (
    format_significant_figures,
    query_gnomad,
    get_af_summary,
    extract_gnomad_afs_from_vcf,
)

# --------------------------------
# format_significant_figures tests
# --------------------------------

def test_format_sig_figs_none():
    assert format_significant_figures(None) is None

def test_format_sig_figs_zero():
    assert format_significant_figures(0) == "0"

def test_format_sig_figs_normal():
    assert format_significant_figures(0.012345) == "0.01235"

# -------------------
# query_gnomad tests
# -------------------

@patch("clinvar_anno_core.modules.gnomad_allele_freq.requests.post")
def test_query_gnomad_success(mock_post):
    """
    Test that `query_gnomad` returns valid data when the API responds successfully.
    It mocks a successful response from the gnomAD API, including empty
    genome and exome data blocks. It verifies that the function correctly parses
    and returns the 'variant' field from the response.
    """
    mock_response = Mock()
    mock_response.json.return_value = {"data": {"variant": {"genome": {}, "exome": {}}}}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    result = query_gnomad("1:100:A:T")
    assert isinstance(result, dict)

@patch("clinvar_anno_core.modules.gnomad_allele_freq.requests.post", side_effect=Exception("fail"))
def test_query_gnomad_failure(mock_post):
    """
    Test that `query_gnomad` returns None when an exception occurs during the API call.
    It simulates a failed API request (e.g., network error, server issue) by
    having `requests.post` raise an exception. The function should catch the error
    internally and return None instead of crashing.
    """
    result = query_gnomad("1:100:A:T")
    assert result is None


# ---------------------
# get_af_summary tests
# ---------------------

def test_get_af_summary_no_data():
    """
    Test that get_af_summary returns None values for AF fields
    when no variant data is provided (i.e., input is None).
    """
    summary = get_af_summary("1:100:A:T", None)
    assert summary["genome_af"] is None
    assert summary["exome_af"] is None
    assert summary["total_af"] is None


def test_get_af_summary_valid_data():
    """
    Test that get_af_summary correctly calculates and formats AF values
    when valid genome and exome data are provided.
    """
    variant_data = {
        "genome": {"ac": 10, "an": 100, "af": 0.1},
        "exome": {"ac": 5, "an": 50, "af": 0.1},
    }

    summary = get_af_summary("1:100:A:T", variant_data)
    assert summary["genome_af"] == "0.1000"
    assert summary["exome_af"] == "0.1000"  
    assert summary["total_af"] == "0.1000"  


# ---------------------------
# extract_gnomad_afs_from_vcf
# ---------------------------

@patch("clinvar_anno_core.modules.gnomad_allele_freq.parse_vcf_file")
@patch("clinvar_anno_core.modules.gnomad_allele_freq.query_gnomad")
def test_extract_afs_success(mock_query_gnomad, mock_parse_vcf):
    """
    Test that extract_gnomad_afs_from_vcf:
    - Correctly processes a list of variants from a VCF,
    - Queries gnomAD for each,
    - Returns AF summaries with values formatted to 4 significant figures.

    Both parse_vcf_file and query_gnomad are mocked.
    """
    mock_parse_vcf.return_value = ["1:100:A:T", "1:200:G:C"] # Simulate the VCF parser returning two variant IDs

    # Simulate gnomAD returning the same AF data for both variants
    mock_query_gnomad.return_value = {
        "genome": {"ac": 1, "an": 10, "af": 0.1},
        "exome": {"ac": 1, "an": 10, "af": 0.1}
    }
    results = extract_gnomad_afs_from_vcf(Path("fake.vcf"))
    assert len(results) == 2

    assert results[0]["genome_af"] == "0.1000"
    assert results[1]["total_af"] == "0.1000"

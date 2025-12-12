
from unittest.mock import patch, MagicMock
from pathlib import Path

from clinvar_anno_core.modules.gnomad_allele_freq import (
    format_significant_figures,
    query_gnomad,
    get_af_summary,
    extract_gnomad_afs_from_vcf,
)


# ---------------------------
# format_significant_figures
# ---------------------------
def test_format_sig_figs_none():
    assert format_significant_figures(None) is None


def test_format_sig_figs_zero():
    assert format_significant_figures(0) == "0"


def test_format_sig_figs_normal():
    assert format_significant_figures(0.012345) == "0.01235"


# ---------------------------
# query_gnomad
# ---------------------------
@patch("clinvar_anno_core.modules.gnomad_allele_freq.requests.post")
def test_query_gnomad_success(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": {"variant": {"genome": {}, "exome": {}}}}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    result = query_gnomad("1:100:A:T")
    assert isinstance(result, dict)


@patch("clinvar_anno_core.modules.gnomad_allele_freq.requests.post", side_effect=Exception("fail"))
def test_query_gnomad_failure(mock_post):
    result = query_gnomad("1:100:A:T")
    assert result is None


# ---------------------------
# get_af_summary
# ---------------------------
def test_get_af_summary_no_data():
    summary = get_af_summary("1:100:A:T", None)
    assert summary["genome_af"] is None
    assert summary["exome_af"] is None
    assert summary["total_af"] is None


def test_get_af_summary_valid_data():
    variant_data = {
        "genome": {"ac": 10, "an": 100, "af": 0.1},
        "exome": {"ac": 5, "an": 50, "af": 0.1},
    }

    summary = get_af_summary("1:100:A:T", variant_data)
    assert summary["genome_af"] == "0.1000"
    assert summary["exome_af"] == "0.1000"  # Changed: should be 4 decimals
    assert summary["total_af"] == "0.1000"  # Changed: should be 4 decimals


# ---------------------------
# extract_gnomad_afs_from_vcf
# ---------------------------
@patch("clinvar_anno_core.modules.gnomad_allele_freq.parse_vcf_file")
@patch("clinvar_anno_core.modules.gnomad_allele_freq.query_gnomad")
def test_extract_afs_success(mock_query, mock_parse):
    mock_parse.return_value = ["1:100:A:T", "1:200:G:C"]
    mock_query.return_value = {
        "genome": {"ac": 1, "an": 10, "af": 0.1},
        "exome": {"ac": 1, "an": 10, "af": 0.1}
    }

    results = extract_gnomad_afs_from_vcf(Path("fake.vcf"))
    assert len(results) == 2
    assert results[0]["genome_af"] == "0.1000"  # Changed: 4 decimals


@patch("clinvar_anno_core.modules.gnomad_allele_freq.parse_vcf_file", side_effect=Exception("bad vcf"))
def test_extract_afs_vcf_failure(mock_parse):
    results = extract_gnomad_afs_from_vcf(Path("fake.vcf"))
    assert results == []
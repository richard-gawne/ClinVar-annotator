""" This test suite verifies the functionality of the HgvsConverter class from
clinvar_anno_core.modules.variant_validation. """

from unittest.mock import patch, MagicMock
import requests
from requests.exceptions import Timeout
from clinvar_anno_core.modules.variant_validation import HgvsConverter

# Variant string shared by all tests
VARIANT = "11:2164285:C:T"

def test_construct_api_url():
    """
    Test to check the API URL is correctly constructed with genome build,
    VARIANT string, and endpoint path.
    """
    converter = HgvsConverter()
    url = converter.construct_api_url(
        base_url="https://rest.variantvalidator.org",
        variant_str=VARIANT,
        genome_build="GRCh38"
    )
    assert "VariantFormatter" in url
    assert VARIANT in url
    assert "GRCh38" in url

def test_parse_validator_valid_response():
    """
    Test that a valid VariantValidator API response with MANE Select transcript
    returns the correct genomic (g.) and transcript (c.) HGVS notations.
    """
    converter = HgvsConverter()

    # Mock API response using the real VARIANT string as keys
    mock_response = {
        VARIANT: {
            VARIANT: {
                "g_hgvs": "NC_000011.10:g.2164285C>T",
                "hgvs_t_and_p": {
                    "NM_000088.4": {
                        "select_status": {"mane_select": True},
                        "t_hgvs": "NM_000088.4:c.589G>T",
                    }
                },
            }
        }
    }

    genomic, transcript = converter.parse_validator_response(mock_response, VARIANT)

    assert genomic == "NC_000011.10:g.2164285C>T"
    assert transcript == "NM_000088.4:c.589G>T"

@patch("clinvar_anno_core.modules.variant_validation.requests.get")
def test_convert_to_hgvs_success(mock_get):
    """
    Test successful conversion of a VARIANT using convert_to_hgvs,
    mocking the API response with valid HGVS entries.
    """
    converter = HgvsConverter()

    # Fake API response
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        VARIANT: {
            VARIANT: {
                "g_hgvs": "NC_000011.10:g.2164285C>T",
                "hgvs_t_and_p": {
                    "NM_000088.4": {
                        "select_status": {"mane_select": True},
                        "t_hgvs": "NM_000088.4:c.589G>T"
                    }
                }
            }
        }
    }

    mock_get.return_value = mock_resp

    genomic, transcript = converter.convert_to_hgvs(VARIANT)

    assert genomic == "NC_000011.10:g.2164285C>T"
    assert transcript == "NM_000088.4:c.589G>T"

def test_convert_to_hgvs_timeout():
    """
    Test that convert_to_hgvs correctly handles a requests Timeout exception
    and returns (None, None).
    """
    converter = HgvsConverter()

    # Patch requests.get to simulate a Timeout exception
    with patch("clinvar_anno_core.modules.variant_validation.requests.get") as mock_get:
        mock_get.side_effect = Timeout()
        genomic, transcript = converter.convert_to_hgvs(VARIANT)

    assert genomic is None
    assert transcript is None


@patch.object(HgvsConverter, "convert_to_hgvs")
def test_batch_convert(mock_convert):
    """
    Test batch conversion of multiple variants. Verifies that results
    are correctly structured and conversion success is correctly reported.
    """
    converter = HgvsConverter()
    variant2 = "1:55516888:A:T"

    # Simulate convert_to_hgvs results:
    # - First VARIANT succeeds
    # - Second VARIANT fails
    mock_convert.side_effect = [("NC_000011.10:g.2164285C>T", "NM_000088.4:c.589G>T"), (None, None)]

    results = converter.batch_convert([VARIANT, variant2])

    # Check the first VARIANT succeeded
    assert results[0]["conversion_success"] is True
    assert results[0]["genomic_hgvs"] == "NC_000011.10:g.2164285C>T"
    assert results[0]["transcript_hgvs"] == "NM_000088.4:c.589G>T"

    # Check the second VARIANT failed
    assert results[1]["conversion_success"] is False
    assert results[1]["genomic_hgvs"] is None
    assert results[1]["transcript_hgvs"] is None

def test_parse_validator_no_inner_data():
    """
    Test parse_validator_response when inner data is empty.
    Should return (None, None).
    """
    converter = HgvsConverter()
    mock_response = {VARIANT: {}}
    g, t = converter.parse_validator_response(mock_response, VARIANT)
    assert g is None
    assert t is None

def test_parse_validator_no_mane_select():
    """
    Test parse_validator_response when no MANE Select transcript is present.
    Should return (None, None) even if g_hgvs exists.
    """
    converter = HgvsConverter()
    mock_response = {
        VARIANT: {
            VARIANT: {
                "g_hgvs": "NC_000011.10:g.2164285C>T",
                "hgvs_t_and_p": {
                    "NM_000088.4": {
                        "select_status": {"mane_select": False},
                        "t_hgvs": "NM_000088.4:c.589G>T",
                    }
                },
            }
        }
    }
    g, t = converter.parse_validator_response(mock_response, VARIANT)
    assert g is None
    assert t is None

@patch("clinvar_anno_core.modules.variant_validation.requests.get")
def test_convert_to_hgvs_http_error(mock_get):
    """
    Test convert_to_hgvs handling of HTTPError from requests.
    Should return (None, None) and not raise an exception.
    """
    converter = HgvsConverter()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError()
    mock_get.return_value = mock_resp
    g, t = converter.convert_to_hgvs(VARIANT)
    assert g is None
    assert t is None

def test_batch_convert_empty_list():
    """
    Test batch_convert with an empty list.
    Should return an empty list without errors.
    """
    converter = HgvsConverter()
    results = converter.batch_convert([])
    assert results == []

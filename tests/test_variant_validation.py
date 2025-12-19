from unittest.mock import patch, MagicMock
import pytest
from requests.exceptions import Timeout
from clinvar_anno_core.modules.variant_validation import HgvsConverter

# Realistic variant string shared by all tests
variant = "11:2164285:C:T"

def test_construct_api_url():
    converter = HgvsConverter()
    url = converter.construct_api_url(
        base_url="https://rest.variantvalidator.org",
        variant_str=variant,
        genome_build="GRCh38"
    )
    assert "VariantFormatter" in url
    assert variant in url
    assert "GRCh38" in url

def test_parse_validator_valid_response():
    converter = HgvsConverter()

    # Mock API response using the real variant string as keys
    mock_response = {
        variant: {
            variant: {
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

    genomic, transcript = converter.parse_validator_response(mock_response, variant)

    assert genomic == "NC_000011.10:g.2164285C>T"
    assert transcript == "NM_000088.4:c.589G>T"

@patch("clinvar_anno_core.modules.variant_validation.requests.get")
def test_convert_to_hgvs_success(mock_get):
    converter = HgvsConverter()

    # Fake API response
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        variant: {
            variant: {
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

    genomic, transcript = converter.convert_to_hgvs(variant)

    assert genomic == "NC_000011.10:g.2164285C>T"
    assert transcript == "NM_000088.4:c.589G>T"

def test_convert_to_hgvs_timeout():
    converter = HgvsConverter()

    # Patch requests.get to simulate a Timeout exception
    with patch("clinvar_anno_core.modules.variant_validation.requests.get") as mock_get:
        mock_get.side_effect = Timeout()
        genomic, transcript = converter.convert_to_hgvs(variant)

    assert genomic is None
    assert transcript is None


@patch.object(HgvsConverter, "convert_to_hgvs")
def test_batch_convert(mock_convert):
    converter = HgvsConverter()
    variant2 = "1:55516888:A:T"

    # Simulate convert_to_hgvs results:
    # - First variant succeeds
    # - Second variant fails
    mock_convert.side_effect = [("NC_000011.10:g.2164285C>T", "NM_000088.4:c.589G>T"), (None, None)]

    results = converter.batch_convert([variant, variant2])

    # Check the first variant succeeded
    assert results[0]["conversion_success"] is True
    assert results[0]["genomic_hgvs"] == "NC_000011.10:g.2164285C>T"
    assert results[0]["transcript_hgvs"] == "NM_000088.4:c.589G>T"

    # Check the second variant failed
    assert results[1]["conversion_success"] is False
    assert results[1]["genomic_hgvs"] is None
    assert results[1]["transcript_hgvs"] is None

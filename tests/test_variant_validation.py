import pytest
from pathlib import Path
from clinvar_anno_core.modules.variant_validation import HgvsConverter

def test_construct_api_url():
    converter = HgvsConverter()
    url = converter.construct_api_url(
        base_url="https://rest.variantvalidator.org",
        variant_str="11:2164285:C:T",
        genome_build="GRCh38"
    )
    assert "VariantFormatter" in url
    assert "11:2164285:C:T" in url
    assert "GRCh38" in url


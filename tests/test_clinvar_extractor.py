def test_search_by_hgvs_no_results(monkeypatch, clinvar):
    """Should return None if no variant IDs found."""
    monkeypatch.setattr(clinvar, "_search_clinvar", lambda term: [])
    result = clinvar.search_by_hgvs("invalid_variant")
    assert result is None
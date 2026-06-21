"""
Tests for the NLQ (Natural Language Query) engine — regex fast path.
"""
import pytest


def test_parse_data_query_ranking():
    """Regex parser should recognize ranking queries."""
    from ai_insights import parse_data_query

    result = parse_data_query("top 5 zones by nrw")
    assert result is not None
    assert result["type"] == "ranking"
    assert result["metric"] == "nrw"


def test_parse_data_query_collection_ranking():
    """Regex parser should recognize collection efficiency rankings."""
    from ai_insights import parse_data_query

    result = parse_data_query("worst 3 zones by collection efficiency")
    assert result is not None
    assert result["type"] == "ranking"
    assert result["metric"] == "collection_efficiency"


def test_parse_data_query_comparison():
    """Regex parser should recognize compare queries."""
    from ai_insights import parse_data_query

    result = parse_data_query("Compare all zones")
    assert result is not None
    assert result["type"] == "comparison"


def test_parse_data_query_summary():
    """Regex parser should recognize summary queries."""
    from ai_insights import parse_data_query

    result = parse_data_query("Summary of all zones")
    assert result is not None
    assert result["type"] == "summary"


def test_parse_data_query_alerts():
    """Regex parser should recognize alert queries."""
    from ai_insights import parse_data_query

    result = parse_data_query("Show me any alerts")
    assert result is not None
    assert result["type"] == "alerts"


def test_parse_data_query_unknown_returns_none():
    """Unknown queries should return None (delegated to LLM)."""
    from ai_insights import parse_data_query

    result = parse_data_query("What is the meaning of life?")
    assert result is None


def test_parse_data_query_returns_raw_query():
    """Parsed result should include the original raw query."""
    from ai_insights import parse_data_query

    q = "Top 10 zones with NRW"
    result = parse_data_query(q)
    assert result is not None
    assert result["raw_query"] == q

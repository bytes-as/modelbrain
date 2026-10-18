"""G033: every applies_when operator and every check."""

from app.engine.clauses import applies, obligation_status

EU = {"DE", "FR"}
SCOPE = {
    "hq_country": "DE",
    "markets": ["DE", "US"],
    "commercial": True,
    "mau": 10,
    "distributes_weights": False,
    "end_user_only": False,
    "ancestor_multimodal": True,
}


def test_operators() -> None:
    assert applies({"always": True}, SCOPE, EU)
    assert applies({"always": False}, SCOPE, EU) is False
    assert applies({"hq_in": "EU"}, SCOPE, EU)
    assert applies({"hq_in": "US"}, SCOPE, EU) is False
    assert applies({"market_in": "EU"}, SCOPE, EU)
    assert applies({"market_in": "FR"}, {"markets": ["DE"]}, EU) is False
    assert applies({"commercial": True}, SCOPE, EU)
    assert applies({"commercial": False}, SCOPE, EU) is False
    assert applies({"mau_gt": 5}, SCOPE, EU)
    assert applies({"mau_gt": 10}, SCOPE, EU) is False
    assert applies({"distributes_weights": False}, SCOPE, EU)
    assert applies({"ancestor_multimodal": True}, SCOPE, EU)
    assert applies({"end_user_only": False}, SCOPE, EU)
    assert applies({"not": {"end_user_only": True}}, SCOPE, EU)
    assert applies({"all": [{"hq_in": "EU"}, {"commercial": True}]}, SCOPE, EU)
    assert applies({"all": [{"hq_in": "EU"}, {"commercial": False}]}, SCOPE, EU) is False
    assert applies({"any": [{"hq_in": "US"}, {"commercial": True}]}, SCOPE, EU)
    assert applies({"any": [{"hq_in": "US"}, {"mau_gt": 100}]}, SCOPE, EU) is False


def test_checks() -> None:
    model = {"name_starts_with": "Llama", "card_has_llama_notice": False, "has_license_file": True}
    assert obligation_status({"name_prefix": "Llama"}, model) == "SATISFIED"
    assert obligation_status({"name_prefix": "Qwen"}, model) == "NOT_SATISFIED"
    assert obligation_status({"card_mentions": "Built with Llama"}, model) == "NOT_SATISFIED"
    assert obligation_status({"license_file_present": True}, model) == "SATISFIED"
    assert obligation_status(None, model) == "NOT_CHECKABLE"

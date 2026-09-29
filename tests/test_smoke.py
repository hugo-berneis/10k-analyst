from report_qa.decision import Decision, DecisionClient
from report_qa.decision_mock import MockDecisionClient


def test_package_imports() -> None:
    import report_qa  # noqa: F401


def test_mock_decision_client_satisfies_protocol() -> None:
    client: DecisionClient = MockDecisionClient()
    assert isinstance(client, DecisionClient)


def test_mock_choice_returns_one_of_the_options() -> None:
    client = MockDecisionClient()
    decision = client.choice("some paragraph", "What risk topic is this?", ["liquidity", "credit"])
    assert isinstance(decision, Decision)
    assert decision.value in {"liquidity", "credit"}
    assert 0.0 <= decision.confidence <= 1.0


def test_mock_score_is_bounded() -> None:
    client = MockDecisionClient()
    decision = client.score("some paragraph", "How negative is the tone?")
    assert 0.0 <= decision.value <= 1.0


def test_mock_noul_is_boolean() -> None:
    client = MockDecisionClient()
    decision = client.noul("some paragraph", "Is this relevant to liquidity risk?")
    assert isinstance(decision.value, bool)


def test_mock_is_deterministic_for_the_same_input() -> None:
    client = MockDecisionClient()
    first = client.choice("paragraph A", "topic?", ["a", "b", "c"])
    second = client.choice("paragraph A", "topic?", ["a", "b", "c"])
    assert first == second

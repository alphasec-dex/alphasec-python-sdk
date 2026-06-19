from alphasec.agent import Agent


def _agent_with_signer(signer):
    agent = Agent.__new__(Agent)
    agent.api = type("API", (), {"signer": signer})()
    return agent


def test_agent_state_accessors():
    agent = _agent_with_signer(type("S", (), {"l1_address": "0xABC", "session_enabled": True})())
    assert agent.l1_address == "0xABC"
    assert agent.is_session_enabled() is True


def test_agent_accessors_no_signer():
    agent = _agent_with_signer(None)
    assert agent.l1_address is None
    assert agent.is_session_enabled() is False


def test_is_session_enabled_false_when_disabled():
    agent = _agent_with_signer(type("S", (), {"l1_address": "0xABC", "session_enabled": 0})())
    assert agent.is_session_enabled() is False

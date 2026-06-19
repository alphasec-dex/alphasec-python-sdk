from alphasec.agent import Agent


def test_withdraw_delegates_without_balance_check(monkeypatch):
    agent = Agent.__new__(Agent)                  # bypass __init__ (avoid network)
    calls = {"balance": 0, "withdraw": None}

    class FakeAPI:
        signer = type("S", (), {"l1_address": "0xabc"})()
        def withdraw_to_kaia(self, token, value):
            calls["withdraw"] = (token, value)
            return {"status": True, "error": None, "tx_hash": "0xdead"}
    agent.api = FakeAPI()
    monkeypatch.setattr(agent, "get_balance",
                        lambda addr: calls.__setitem__("balance", calls["balance"] + 1) or [])

    out = agent.withdraw("USDT", 10.0)
    assert calls["withdraw"] == ("USDT", 10.0)
    assert calls["balance"] == 0                  # balance is not queried
    assert out["tx_hash"] == "0xdead"

"""Tests for the C3 lazy-init guard in the facade layers.

After C3 made sync construction lazy, any facade method that reads the token map
before its first guarded HTTP call must call _ensure_initialized() first, or a
fresh client raises 'Unknown token symbol' (or sends a wrong token). These pin the
two regressions the review found: Agent.subscribe and PerpAgent.transfer.
"""
from alphasec.agent import Agent
from alphasec.perp.agent import PerpAgent
from alphasec.perp.constants import SPOT_TO_PERP


def test_agent_subscribe_lazy_inits_token_map():
    agent = Agent.__new__(Agent)

    class FakeAPI:
        def __init__(self):
            self.symbol_token_id_map = {}

        def _ensure_initialized(self):
            self.symbol_token_id_map = {"KAIA": "1", "USDT": "2"}

    agent.api = FakeAPI()

    captured = {}

    class FakeWS:
        def subscribe(self, channel, callback, timeout=None):
            captured["channel"] = channel
            return 7

    agent.ws = FakeWS()

    sub_id = agent.subscribe("trade@KAIA/USDT", lambda p: None)
    assert sub_id == 7
    assert captured["channel"] == "trade@1_2"   # resolved via lazy init, no ValueError


def test_perp_transfer_lazy_inits_token_map():
    captured = {}

    class FakeSigner:
        def create_perp_deposit_data(self, token_id, amount):
            captured["token_id"] = token_id
            return b"data"

        def generate_alphasec_transaction(self, nonce, data):
            return "0xtx"

    class FakeAPI:
        signer = FakeSigner()

        def __init__(self):
            self.symbol_token_id_map = {}

        def _ensure_initialized(self):
            self.symbol_token_id_map = {"USDT": "2"}

        def post(self, path, params):
            return {"code": 200, "errMsg": "", "result": "0xhash"}

    class FakeAgent:
        def __init__(self):
            self.api = FakeAPI()

    perp = PerpAgent(FakeAgent())
    tx = perp.transfer(SPOT_TO_PERP, "USDT", 10)
    assert tx == "0xhash"
    assert captured["token_id"] == "2"   # resolved via lazy init, NOT literal 'USDT'

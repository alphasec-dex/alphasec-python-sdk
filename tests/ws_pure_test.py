"""Offline unit tests for websocket pure functions (§3.5, perp excluded).

No socket/thread/event-loop I/O: only the pure identify/convert helpers and
is_ack are exercised. Covers the bool/int/float ACK trap, numeric-key
camel_to_snake asymmetry, nested convert_to_snake_case recursion,
channel_to_identifier format-violation exception types, ws_msg_to_identifier
depth-dict/empty/address handling, and the intentional sync(camel) vs
async(lower) userEvent tag-case divergence.
"""
import pytest

from alphasec.websocket import async_ws
from alphasec.websocket import ws as sync_ws
from alphasec.websocket.types import camel_to_snake, convert_to_snake_case

UE = "0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c"
UE_LOWER = UE.lower()


def _sync_mgr():
    return sync_ws.WebsocketManager("http://offline.test")


def _async_mgr():
    return async_ws.AsyncWebsocketManager("http://offline.test")


def test_is_ack_bool_int_float_classification():
    is_ack = _sync_mgr().is_ack
    # bool is an int subclass -> a bool id is still classified as an ACK (trap).
    assert is_ack({"jsonrpc": "2.0", "id": True, "result": "x"}) is True
    assert is_ack({"jsonrpc": "2.0", "id": False, "result": "x"}) is True
    assert is_ack({"jsonrpc": "2.0", "id": 1, "result": "x"}) is True
    # float id is NOT an int -> not an ACK (would otherwise fall to routing).
    assert is_ack({"jsonrpc": "2.0", "id": 1.0, "result": "x"}) is False
    # missing id, or non-str result -> not an ACK.
    assert is_ack({"jsonrpc": "2.0", "result": "x"}) is False
    assert is_ack({"jsonrpc": "2.0", "id": 1, "result": 5}) is False
    # async parity on the subclass trap.
    assert _async_mgr().is_ack({"jsonrpc": "2.0", "id": True, "result": "x"}) is True


def test_camel_to_snake_numeric_key_asymmetry():
    # digit-then-lowercase is NOT a boundary; an interior camel hump IS.
    assert camel_to_snake("high24h") == "high24h"
    assert camel_to_snake("volume24h") == "volume24h"
    assert camel_to_snake("open24h") == "open24h"
    assert camel_to_snake("quoteVolume24h") == "quote_volume24h"
    assert camel_to_snake("marketId") == "market_id"
    assert camel_to_snake("HTTPServer") == "http_server"
    assert camel_to_snake("ID") == "id"
    assert camel_to_snake("") == ""


def test_convert_to_snake_case_recurses_and_passes_scalars():
    src = {
        "marketId": "5_2",
        "tickerData": [{"quoteVolume24h": 10, "high24h": 9}, {"baseTokenId": "x"}],
        "innerObj": {"orderId": "o1", "deepList": [{"txHash": "h"}]},
    }
    assert convert_to_snake_case(src) == {
        "market_id": "5_2",
        "ticker_data": [{"quote_volume24h": 10, "high24h": 9}, {"base_token_id": "x"}],
        "inner_obj": {"order_id": "o1", "deep_list": [{"tx_hash": "h"}]},
    }
    # Boundaries: empty dict, None, and list-of-scalars pass through unchanged;
    # values (even strings) are never key-converted.
    assert convert_to_snake_case({}) == {}
    assert convert_to_snake_case(None) is None
    assert convert_to_snake_case(["aB", 1, None]) == ["aB", 1, None]
    assert convert_to_snake_case({"feeTokenId": None}) == {"fee_token_id": None}


def test_channel_to_identifier_format_violation_types():
    c2i = sync_ws.channel_to_identifier
    with pytest.raises(IndexError):
        c2i("trade")  # no '@' -> split("@")[1] out of range
    with pytest.raises(IndexError):
        c2i("depth")
    with pytest.raises(ValueError, match="Unknown channel"):
        c2i("unknown@channel")
    with pytest.raises(ValueError, match="Unknown channel"):
        c2i("aggTrade@1")  # 'trade' match is case-sensitive; 'aggTrade' misses it
    assert c2i("ticker@") == "ticker:"  # empty suffix is allowed, not an error


def test_ws_msg_to_identifier_depth_dict_empty_and_user_address():
    w2i = sync_ws.ws_msg_to_identifier

    def msg(channel, result):
        return {"jsonrpc": "2.0", "method": "subscription",
                "params": {"channel": channel, "result": result}}

    assert w2i(msg("trade@5_2", [{"marketId": "5_2"}])) == "trade:5_2"
    assert w2i(msg("trade@5_2", [])) is None
    # depth result is a dict (not a list) -> keyed access, not [0].
    assert w2i(msg("depth@5_2", {"marketId": "5_2"})) == "depth:5_2"
    assert w2i(msg("depth@5_2", {})) is None
    assert w2i(msg("userEvent@" + UE, [{"x": 1}])) == "userEvent:" + UE_LOWER
    assert w2i(msg("userEvent@" + UE, [])) is None
    assert w2i(msg("userEvent@notanaddr", [{"x": 1}])) is None
    assert w2i({"jsonrpc": "2.0", "method": "other", "params": {}}) is None


def test_subscribe_and_message_identifiers_agree():
    # The subscribe path (channel_to_identifier) and the message path
    # (ws_msg_to_identifier) must emit the SAME identifier for a channel, else
    # messages arrive under a key nobody subscribed to -> permanent silent drop.
    c2i = sync_ws.channel_to_identifier
    w2i = sync_ws.ws_msg_to_identifier

    def msg(channel, result):
        return {"jsonrpc": "2.0", "method": "subscription",
                "params": {"channel": channel, "result": result}}

    assert c2i("trade@5_2") == w2i(msg("trade@5_2", [{"marketId": "5_2"}])) == "trade:5_2"
    assert c2i("depth@5_2") == w2i(msg("depth@5_2", {"marketId": "5_2"})) == "depth:5_2"
    assert c2i("userEvent@" + UE) == w2i(msg("userEvent@" + UE, [{"x": 1}])) == "userEvent:" + UE_LOWER


def test_sync_async_userevent_tag_case_differs():
    # Intentional divergence: sync emits camelCase 'userEvent:', async emits
    # lowercase 'userevent:'. The async guard matches startswith("userevent:"),
    # so a camel drift in async would silently disable duplicate-sub rejection.
    ch = "userEvent@" + UE
    assert sync_ws.channel_to_identifier(ch) == "userEvent:" + UE_LOWER
    assert async_ws.channel_to_identifier(ch) == "userevent:" + UE_LOWER

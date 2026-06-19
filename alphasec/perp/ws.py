"""Perp WebSocket event classification.

The websocket managers deliver perp messages through the same callback path as
any other channel: the manager hands the callback ``params.result`` (the inner
payload), not the full envelope. Callers pass the channel string together with
that payload to :func:`decode_perp_event` to obtain a classified
:class:`PerpEvent`.

Channel routing (prefix match), mirroring the Rust SDK
(``src/perp/ws.rs`` ``decode_perp_event``):

  - ``perp_ticker``    -> kind ``"ticker"``    (payload: list of ticker snapshots)
  - ``perp_markPrice`` -> kind ``"markPrice"`` (payload: single mark-price dict)
  - ``perp_aggTrade``  -> kind ``"aggTrade"``  (payload: list of trade dicts)
  - ``perp_aggDepth``  -> kind ``"aggDepth"``  (payload: depth snapshot dict)
  - ``perp_candle``    -> kind ``"candle"``     (payload: candle update dict)
  - ``userEvent``      -> dispatch on the payload's ``topic`` field

``userEvent`` topics map to kinds, matching the Rust ``PerpEvent`` variants
(``UserOrder`` / ``UserPosition`` / ``UserFunding`` / ``UserAccount``):

  - ``PERP_ORDER``    -> ``"userOrder"``    (eventType NEW / TRADE / CANCEL)
  - ``PERP_POSITION`` -> ``"userPosition"``
  - ``PERP_FUNDING``  -> ``"userFunding"``
  - ``ACCOUNT``       -> ``"userAccount"``  (perp eventTypes, e.g. PERP_SET_LEVERAGE)

An unknown channel, a ``userEvent`` payload missing ``topic``, or an unknown
topic raises ``ValueError`` -- the decoder never silently returns ``None``.
"""
from typing import NamedTuple

# Classified perp websocket event: ``kind`` is the taxonomy tag (see module
# docstring) and ``data`` is the raw ``params.result`` payload unchanged.
PerpEvent = NamedTuple("PerpEvent", [("kind", str), ("data", dict)])

# Channel prefix -> event kind. Order does not matter (prefixes are disjoint),
# but using explicit prefix matching avoids the substring collisions that the
# generic spot router suffers from (e.g. "perp_ticker" containing "ticker").
_CHANNEL_PREFIX_KINDS = (
    ("perp_ticker", "ticker"),
    ("perp_markPrice", "markPrice"),
    ("perp_aggTrade", "aggTrade"),
    ("perp_aggDepth", "aggDepth"),
    ("perp_candle", "candle"),
)

# userEvent topic -> event kind.
_USER_TOPIC_KINDS = {
    "PERP_ORDER": "userOrder",
    "PERP_POSITION": "userPosition",
    "PERP_FUNDING": "userFunding",
    "ACCOUNT": "userAccount",
}


def decode_perp_event(channel: str, payload: dict) -> PerpEvent:
    """Classify a perp websocket payload by its channel name.

    Args:
        channel: The subscription channel string (e.g. ``"perp_markPrice@1"``,
            ``"perp_candle@1:60"``, ``"userEvent@0xabc..."``).
        payload: The ``params.result`` field of the websocket envelope. For
            market-data channels this is the inner result (a list for
            ticker/aggTrade, a dict otherwise); for ``userEvent`` it is the
            event dict carrying a ``topic`` field.

    Returns:
        A :class:`PerpEvent` whose ``kind`` identifies the stream and whose
        ``data`` is the same ``payload`` object you pass in (this function does
        not transform keys).

    Note:
        When the payload is delivered through the SDK WebSocket managers
        (sync ``WebsocketManager`` / async ``AsyncWebsocketManager``), its keys
        are already snake_cased (e.g. ``markPrice`` -> ``mark_price``,
        ``eventType`` -> ``event_type``), consistent with the spot streams.
        Classification is unaffected (it keys on the channel prefix and, for
        ``userEvent``, on the ``topic`` field, both of which survive
        snake_casing), but read ``data`` with snake_case field names at runtime.

    Raises:
        ValueError: If the channel is unrecognised, or a ``userEvent`` payload
            is missing its ``topic`` field or carries an unknown topic.
    """
    for prefix, kind in _CHANNEL_PREFIX_KINDS:
        if channel.startswith(prefix):
            return PerpEvent(kind, payload)

    if channel.startswith("userEvent"):
        return _decode_user_event(payload)

    raise ValueError(f"decode_perp_event: unrecognised channel '{channel}'")


def _decode_user_event(payload: dict) -> PerpEvent:
    """Dispatch a ``userEvent`` payload on its ``topic`` field."""
    topic = payload.get("topic") if isinstance(payload, dict) else None
    if not topic:
        raise ValueError("decode_perp_event: userEvent payload missing 'topic' field")

    kind = _USER_TOPIC_KINDS.get(topic)
    if kind is None:
        raise ValueError(f"decode_perp_event: unknown userEvent topic '{topic}'")

    return PerpEvent(kind, payload)

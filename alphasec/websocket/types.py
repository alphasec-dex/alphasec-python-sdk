from typing import Union, TypedDict, Literal, List
from eth_account.types import HexAddress

TradesSubscription = TypedDict("TradesSubscription", {"channels": List[str]})
DepthSubscription = TypedDict("DepthSubscription", {"channels": List[str]})
TickerSubscription = TypedDict("TickerSubscription", {"channels": List[str]})
UserEventsSubscription = TypedDict("UserEventsSubscription", {"channels": List[str]})
Subscription = Union[
    TradesSubscription,
    DepthSubscription,
    TickerSubscription,
    UserEventsSubscription,
]

Ack = TypedDict("Ack", {"jsonrpc":Literal["2.0"], "id": int, "result": str})

Side = Literal[0, 1] # 0: buy, 1: sell
Users = List[HexAddress]
TradeResult = TypedDict(
    "TradeResult", 
    {
        "hash": str, 
        "symbol": str, 
        "side": Side, 
        "px": str, 
        "sz": int, 
        "tid": str, 
        "time": int, 
        "users": Users
    }
)
TradeParams = TypedDict("TradeParams", {"channel": str, "result": TradeResult})
TradeMsg = TypedDict("TradeMsg", {"jsonrpc":Literal["2.0"], "method": Literal["subscription"], "params": TradeParams})

# Depth types
DepthResult = TypedDict(
    "DepthResult",
    {
        "marketId": str,
        "bids": List[List[str]],  # [[price, size], ...]
        "asks": List[List[str]],  # [[price, size], ...]
        "firstId": int,
        "finalId": int,
        "time": int,
    },
)
DepthParams = TypedDict("DepthParams", {"channel": str, "result": DepthResult})
DepthMsg = TypedDict("DepthMsg", {"jsonrpc":Literal["2.0"], "method": Literal["subscription"], "params": DepthParams})

# Ticker types
TickerEntry = TypedDict(
    "TickerEntry",
    {
        "marketId": str,
        "baseTokenId": str,
        "quoteTokenId": str,
        "price": str,
        "open24h": str,
        "high24h": str,
        "low24h": str,
        "volume24h": str,
        "quoteVolume24h": str,
    },
)
TickerParams = TypedDict("TickerParams", {"channel": str, "result": List[TickerEntry]})
TickerMsg = TypedDict("TickerMsg", {"jsonrpc":Literal["2.0"], "method": Literal["subscription"], "params": TickerParams})

# User event types
UserEventType = Literal["NEW", "TRADE", "CANCELED", "PARTIALLY_FILLED", "REJECTED", "EXPIRED", "FILLED"]
OrderSideStr = Literal["BUY", "SELL"]
OrderTypeStr = Literal["LIMIT", "MARKET"]
OrderStatusStr = Literal["NEW", "PARTIALLY_FILLED", "FILLED", "CANCELED", "REJECTED", "EXPIRED"]

UserEventResult = TypedDict(
    "UserEventResult",
    {
        "eventType": UserEventType,
        "eventTime": int,
        "accountId": int,
        "orderId": str,
        "txHash": str,
        "marketId": str,
        "side": OrderSideStr,
        "orderType": OrderTypeStr,
        "origPrice": str,
        "origQty": str,
        "origQuoteOrderQty": str,
        "status": OrderStatusStr,
        "createdAt": int,
        "executedQty": str,
        "executedQuoteQty": str,
        "lastPrice": str,
        "lastQty": str,
        "fee": str,
        "feeTokenId": str | None,
        "tradeId": str,
        "isMaker": bool,
    },
)
UserEventParams = TypedDict("UserEventParams", {"channel": str, "result": UserEventResult})
UserEventMsg = TypedDict("UserEventMsg", {"jsonrpc":Literal["2.0"], "method": Literal["subscription"], "params": UserEventParams})


WsMsg = Union[
    Ack,
    TradeMsg,
    DepthMsg,
    TickerMsg,
    UserEventMsg,
]
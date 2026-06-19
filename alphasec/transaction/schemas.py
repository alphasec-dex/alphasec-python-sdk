from typing import Optional, Literal
import re
from pydantic import BaseModel, Field, field_validator


HEX_ADDR_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


class AddressStr(str):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source, _handler):  # type: ignore
        from pydantic import GetCoreSchemaHandler
        from pydantic_core import core_schema
        assert isinstance(_handler, GetCoreSchemaHandler)
        def validate(v):
            if not isinstance(v, str) or not HEX_ADDR_RE.fullmatch(v):
                raise ValueError("expected 0x-prefixed 20-byte hex address")
            return v
        return core_schema.no_info_plain_validator_function(validate)


class StopOrderModel(BaseModel):
    l1owner: AddressStr
    base_token: str = Field(min_length=1)
    quote_token: str = Field(min_length=1)
    stop_price: float
    price: float
    quantity: float
    side: Literal[0, 1]
    order_type: Literal[0, 1]
    order_mode: Literal[0, 1]

    @field_validator("base_token", "quote_token")
    @classmethod
    def strip_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("must be a non-empty string")
        return s

    def to_wire(self) -> dict:
        return {
            "l1owner": self.l1owner,
            "baseToken": self.base_token,
            "quoteToken": self.quote_token,
            "stopPrice": str(self.stop_price),
            "price": str(self.price),
            "quantity": str(self.quantity),
            "side": int(self.side),
            "orderType": int(self.order_type),
            "orderMode": int(self.order_mode),
        }


class ValueTransferModel(BaseModel):
    l1owner: AddressStr
    to: AddressStr
    value: float

    def to_wire(self) -> dict:
        return {
            "l1owner": self.l1owner,
            "to": self.to,
            "value": str(self.value),
        }


class TokenTransferModel(BaseModel):
    l1owner: AddressStr
    to: AddressStr
    value: float
    token: str = Field(min_length=1)

    @field_validator("token")
    @classmethod
    def strip_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("must be a non-empty string")
        return s

    def to_wire(self) -> dict:
        return {
            "l1owner": self.l1owner,
            "to": self.to,
            "value": str(self.value),
            "token": self.token,
        }


class TpslModel(BaseModel):
    tp_limit: Optional[str] = Field(default=None)
    sl_trigger: Optional[str] = Field(default=None)
    sl_limit: Optional[str] = Field(default=None)

    def to_wire(self) -> dict:
        out = {}
        if self.tp_limit is not None:
            out["tpLimit"] = self.tp_limit
        if self.sl_trigger is not None:
            out["slTrigger"] = self.sl_trigger
        if self.sl_limit is not None:
            out["slLimit"] = self.sl_limit
        return out


class OrderModel(BaseModel):
    l1owner: AddressStr
    base_token: str = Field(min_length=1)
    quote_token: str = Field(min_length=1)
    side: Literal[0, 1]
    price: float
    quantity: float
    order_type: Literal[0, 1]
    order_mode: Literal[0, 1]
    tpsl: Optional[TpslModel] = None

    @field_validator("base_token", "quote_token")
    @classmethod
    def strip_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("must be a non-empty string")
        return s

    def to_wire(self) -> dict:
        out = {
            "l1owner": self.l1owner,
            "baseToken": self.base_token,
            "quoteToken": self.quote_token,
            "side": int(self.side),
            "price": str(self.price),
            "quantity": str(self.quantity),
            "orderType": int(self.order_type),
            "orderMode": int(self.order_mode),
        }
        if self.tpsl is not None:
            t = self.tpsl.to_wire()
            if t:
                out["tpsl"] = t
        return out


class CancelModel(BaseModel):
    l1owner: AddressStr
    order_id: str = Field(min_length=1)

    @field_validator("order_id")
    @classmethod
    def strip_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("must be a non-empty string")
        return s

    def to_wire(self) -> dict:
        return {
            "l1owner": self.l1owner,
            "orderId": self.order_id,
        }


class CancelAllModel(BaseModel):
    l1owner: AddressStr

    def to_wire(self) -> dict:
        return {"l1owner": self.l1owner}


class ModifyModel(BaseModel):
    l1owner: AddressStr
    order_id: str = Field(min_length=1)
    new_price: Optional[float]
    new_qty: Optional[float]
    order_mode: Literal[0, 1]

    @field_validator("order_id")
    @classmethod
    def strip_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("must be a non-empty string")
        return s

    @field_validator("new_price", "new_qty")
    @classmethod
    def allow_none(cls, v: float) -> Optional[float]:
        return v

    @field_validator("order_mode")
    @classmethod
    def ensure_any_change(cls, v: int, info):  # type: ignore
        # Ensure at least one of new_price/new_qty present
        data = info.data
        if data.get("new_price") is None and data.get("new_qty") is None:
            raise ValueError("new_price or new_qty must be provided")
        return v

    def to_wire(self) -> dict:
        out = {
            "l1owner": self.l1owner,
            "orderId": self.order_id,
            "orderMode": int(self.order_mode),
        }
        if self.new_price is not None:
            out["newPrice"] = str(self.new_price)
        if self.new_qty is not None:
            out["newQty"] = str(self.new_qty)
        return out


# ---------------------------------------------------------------------------
# Perp (perpetual futures) wire models
#
# Byte-for-byte compatible with alphasec-rust-sdk src/signer/perp_transaction.rs.
# Two key-ordering rules are reproduced exactly by the insertion order in each
# ``to_wire()`` (Python's ``json.dumps`` preserves dict insertion order):
#   - PerpOrder / PerpModify: rust builds the base object through a serde_json::Map
#     (alphabetically sorted keys), then splices price/quantity (or newPrice/
#     newQuantity) LAST as raw JSON integers. Reproduced below.
#   - Cancel / CancelAll / SetLeverage / Deposit / Withdraw: rust serializes the
#     struct in declaration order.
# price/quantity/newPrice/newQuantity are JSON integers (10^18-scaled, see
# ``perp_scale``); deposit/withdraw ``amount`` is a JSON string. l1owner is the
# lowercase hex address (lowercased by the caller in ``sign.py``).
# ---------------------------------------------------------------------------


class PerpOrderModel(BaseModel):
    l1owner: str
    market_id: int = Field(ge=0)
    side: Literal[0, 1]
    price: int  # already 10^18-scaled integer
    quantity: int  # already 10^18-scaled integer
    is_reduce_only: bool
    time_in_force: Literal[0, 1, 2, 3]
    client_order_id: Optional[str] = None

    def to_wire(self) -> dict:
        out: dict = {}
        if self.client_order_id is not None:
            out["clientOrderId"] = self.client_order_id
        out["isReduceOnly"] = self.is_reduce_only
        out["l1owner"] = self.l1owner
        out["marketId"] = self.market_id
        out["side"] = self.side
        out["timeInForce"] = self.time_in_force
        out["price"] = self.price
        out["quantity"] = self.quantity
        return out


class PerpCancelModel(BaseModel):
    l1owner: str
    market_id: int = Field(ge=0)
    order_id: str

    def to_wire(self) -> dict:
        return {
            "l1owner": self.l1owner,
            "marketId": self.market_id,
            "orderId": self.order_id,
        }


class PerpCancelAllModel(BaseModel):
    l1owner: str
    market_id: int = Field(ge=0)  # 0 = all markets

    def to_wire(self) -> dict:
        return {
            "l1owner": self.l1owner,
            "marketId": self.market_id,
        }


class PerpSetLeverageModel(BaseModel):
    l1owner: str
    market_id: int = Field(ge=0)
    leverage: int = Field(ge=1, le=125)

    def to_wire(self) -> dict:
        return {
            "l1owner": self.l1owner,
            "marketId": self.market_id,
            "leverage": self.leverage,
        }


class PerpModifyModel(BaseModel):
    l1owner: str
    market_id: int = Field(ge=0)
    order_id: str
    new_price: Optional[int] = None  # already 10^18-scaled integer; None -> key omitted
    new_quantity: Optional[int] = None  # already 10^18-scaled integer; None -> key omitted
    client_order_id: Optional[str] = None  # "" included, None omitted

    def to_wire(self) -> dict:
        out: dict = {}
        if self.client_order_id is not None:
            out["clientOrderId"] = self.client_order_id
        out["l1owner"] = self.l1owner
        out["marketId"] = self.market_id
        out["orderId"] = self.order_id
        if self.new_price is not None:
            out["newPrice"] = self.new_price
        if self.new_quantity is not None:
            out["newQuantity"] = self.new_quantity
        return out


class PerpDepositModel(BaseModel):
    l1owner: str
    token: str
    amount: str  # raw integer as string (value x 10^18)

    def to_wire(self) -> dict:
        return {
            "l1owner": self.l1owner,
            "token": self.token,
            "amount": self.amount,
        }


class PerpWithdrawModel(BaseModel):
    l1owner: str
    token: str
    amount: str  # raw integer as string (value x 10^18)

    def to_wire(self) -> dict:
        return {
            "l1owner": self.l1owner,
            "token": self.token,
            "amount": self.amount,
        }


class SessionContextModel(BaseModel):
    type: int = Field(ge=1, le=3)
    publickey: AddressStr
    expiresAt: int = Field(ge=0)
    nonce: int = Field(ge=0)
    l1owner: AddressStr
    l1signature: str = Field(min_length=1)
    metadata: Optional[str] = None

    def to_wire(self) -> dict:
        out = {
            "type": int(self.type),
            "publickey": self.publickey,
            "expiresAt": int(self.expiresAt),
            "nonce": int(self.nonce),
            "l1owner": self.l1owner,
            "l1signature": self.l1signature,
        }
        if self.metadata is not None:
            out["metadata"] = self.metadata
        return out



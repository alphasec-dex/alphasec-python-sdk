import time
from decimal import Decimal, ROUND_DOWN, localcontext, InvalidOperation
from ens.ens import default
from eth_account import Account
from eth_account.messages import encode_typed_data
import json
import base64
from typing import Literal, Optional, Union
from eth_utils.address import is_address
from web3 import Web3

from alphasec.api.constants import ALPHASEC_KAIROS_URL, ALPHASEC_MAINNET_URL, KAIROS_URL, MAINNET_URL

from .schemas import (
    StopOrderModel,
    ValueTransferModel,
    TokenTransferModel,
    OrderModel,
    TpslModel,
    CancelModel,
    CancelAllModel,
    ModifyModel,
    SessionContextModel,
    PerpOrderModel,
    PerpCancelModel,
    PerpCancelAllModel,
    PerpSetLeverageModel,
    PerpModifyModel,
    PerpDepositModel,
    PerpWithdrawModel,
)

from .constants import (
    ALPHASEC_GATEWAY_ROUTER_CONTRACT_ADDR,
    ALPHASEC_MAINNET_CHAIN_ID,
    ALPHASEC_ORDER_CONTRACT_ADDR,
    ALPHASEC_SYSTEM_CONTRACT_ADDR,
    ALPHASEC_TESTNET_CHAIN_ID,
    ALPHASEC_ZK_INTERFACE_CONTRACT_ADDR,
    ALPHASEC_NATIVE_TOKEN_ID,
    KAIROS_ERC20_GATEWAY_CONTRACT_ADDR,
    KAIROS_ERC20_ROUTER_CONTRACT_ADDR,
    KAIROS_INBOX_CONTRACT_ADDR,
    KAIROS_OUTBOX_CONTRACT_ADDR,
    MAINNET_ERC20_GATEWAY_CONTRACT_ADDR,
    MAINNET_ERC20_ROUTER_CONTRACT_ADDR,
    MAINNET_INBOX_CONTRACT_ADDR,
    MAINNET_OUTBOX_CONTRACT_ADDR,
    DexCommandSession,
    DexCommandTransfer,
    DexCommandTokenTransfer,
    DexCommandOrder,
    DexCommandCancel,
    DexCommandCancelAll,
    DexCommandModify,
    DexCommandStopOrder,
    DexCommandPerpOrder,
    DexCommandPerpCancel,
    DexCommandPerpCancelAll,
    DexCommandPerpWithdraw,
    DexCommandPerpSetLeverage,
    DexCommandPerpModify,
    DexCommandPerpDeposit,
)

from .abi import (
    L2_ERC20_ROUTER_ABI,
    NATIVE_L1_ABI,
    L2_SYSTEM_ABI,
    ERC20_ABI,
    ERC20_ROUTER_ABI,
    ZK_INTERFACE_ABI,
    L1_OUTBOX_ABI,
)

def address_to_bytes(address):
    return bytes.fromhex(address[2:] if address.startswith("0x") else address)


# Perp wire scaling factor: all perp tokens use flat x10^18 scaling.
_PERP_SCALE = 10 ** 18
# rust_decimal's max value (2^96 - 1). The rust SDK's perp_scale rejects any value
# whose x10^18 product exceeds this; matched here for cross-SDK behavioral parity.
_PERP_SCALED_MAX = 79228162514264337593543950335

PerpAmount = Union[Decimal, str, int]


def perp_scale(value: PerpAmount) -> int:
    """Scale a perp deposit/withdraw amount to a 10^18 integer (truncate, no rounding).

    Order/modify price/quantity no longer use this (they send decimal strings via
    ``perp_decimal_str``); only deposit/withdraw ``amount`` stays 10^18-scaled.

    Mirrors alphasec-rust-sdk ``src/signer/utils.rs::perp_scale``: multiply by 10^18
    then truncate toward zero. ``float`` is rejected (0.1-style values produce wrong
    bytes); pass ``Decimal`` or ``str``. Negative values are rejected (``-0`` is
    allowed as ``0``). Values whose scaled magnitude exceeds rust_decimal's max are
    rejected for cross-SDK parity.

    Parity note: the overflow guard is checked on the truncated integer (rust checks
    the pre-truncation product). The two agree on every realistic value and on the
    economic ceiling (~7.92e28 scaled units); they differ only for pathological inputs
    with >28 significant fractional digits, where this emits the correct
    floor(value * 10^18) that rust would instead refuse to build.
    """
    if isinstance(value, float):
        raise TypeError("float is not allowed for perp amounts; use Decimal or str")
    if isinstance(value, Decimal):
        d = value
    else:
        try:
            d = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError(f"perp amount must be a numeric Decimal or str, got {value!r}")
    if not d.is_finite():
        raise ValueError(f"perp amount must be finite, got {value!r}")
    if d < 0:
        raise ValueError("amount cannot be negative")
    with localcontext() as ctx:
        ctx.prec = 60
        scaled = (d * _PERP_SCALE).to_integral_value(rounding=ROUND_DOWN)
    result = int(scaled)
    if result > _PERP_SCALED_MAX:
        raise ValueError("amount too large (overflow in x10^18 scale)")
    return result


def perp_decimal_str(value: PerpAmount) -> str:
    """Format a perp price/quantity as the node's decimal string (fixed-point).

    Order (0x41) and modify (0x4A) send the human-readable decimal as a JSON
    *string* (e.g. ``"50000"``, ``"0.5"``); the node scales by 10^18 internally.
    This replaces the old client-side ``perp_scale`` for those fields. Validation
    mirrors ``perp_scale``: ``float`` is rejected (0.1-style values produce wrong
    digits; pass ``Decimal``/``str``/``int``), negative and non-finite are rejected.
    Output is fixed-point so the node parser never sees scientific notation
    (``Decimal("5E+4")`` -> ``"50000"``). Magnitude/precision limits are enforced by
    the node (no client-side x10^18 overflow cap, unlike ``perp_scale``).
    """
    if isinstance(value, float):
        raise TypeError("float is not allowed for perp amounts; use Decimal or str")
    if isinstance(value, Decimal):
        d = value
    else:
        try:
            d = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError(f"perp amount must be a numeric Decimal or str, got {value!r}")
    if not d.is_finite():
        raise ValueError(f"perp amount must be finite, got {value!r}")
    if d < 0:
        raise ValueError("amount cannot be negative")
    return format(d, "f")


class AlphasecSigner:
    l1_address: str
    l1_wallet: Account
    l2_wallet: Account
    session_enabled: bool
    network: Literal["mainnet", "kairos"]
    alphasec_endpoint_url: str
    chain_id: int

    def __init__(self, config: dict):
        default_chain_id = ALPHASEC_TESTNET_CHAIN_ID if config["network"] == "kairos" else ALPHASEC_MAINNET_CHAIN_ID
        if not "l1_address" in config:
            raise ValueError("l1_address should be set")
        self.l1_address = config["l1_address"]
        # [D1] Default to None so the `if self.l1_wallet is None` guards in
        # deposit/withdraw raise the intended ValueError instead of an
        # AttributeError when the signer is created without an l1_wallet
        # (e.g. an l2/session-only config).
        self.l1_wallet = None
        self.l2_wallet = None
        if "l1_wallet" in config:
            self.l1_wallet = Account.from_key(config["l1_wallet"])
        if "l2_wallet" in config:
            self.l2_wallet = Account.from_key(config["l2_wallet"])
        if "session_enabled" in config:
            self.session_enabled = config["session_enabled"]
        if "network" in config:
            self.network = config["network"]
        if "chain_id" in config:
            self.chain_id = config["chain_id"]
        else:
            self.chain_id = default_chain_id


    def get_wallet(self):
        if self.session_enabled:
            return self.l2_wallet
        return self.l1_wallet

    def session_register_typed_data(self, session_addr: str, nonce: int, expiry: int):
        return {
            "domain": {
                "name": "DEXSignTransaction",
                "version": "1",
                "chainId": self.chain_id,
                "verifyingContract": "0x0000000000000000000000000000000000000000",
            },
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "RegisterSessionWallet": [
                    {"name": "sessionWallet", "type": "address"},
                    {"name": "expiry", "type": "uint64"},
                    {"name": "nonce", "type": "uint64"},
                ],
            },
            "primaryType": "RegisterSessionWallet",
            "message": {
                "sessionWallet": session_addr,
                "expiry": str(int(expiry)),
                "nonce": str(int(nonce)),
            },
        }


    def create_session_data(self, cmd: int, session_addr: str, timestamp_ms: int, expires_at: int, metadata: bytes = b"") -> bytes:
        if self.l1_wallet is None:
            raise ValueError("l1_wallet is not set")

        # Build and sign EIP-712 typed data
        typed = self.session_register_typed_data(session_addr, timestamp_ms, expires_at)
        signable = encode_typed_data(full_message=typed)
        signed = self.l1_wallet.sign_message(signable)
        signature_b64 = base64.b64encode(bytes(signed.signature)).decode("ascii")

        model = SessionContextModel(
            type=cmd,
            publickey=session_addr,
            expiresAt=expires_at,
            nonce=timestamp_ms,
            l1owner=self.l1_address,
            l1signature=signature_b64,
            metadata=metadata.decode("utf-8") if isinstance(metadata, (bytes, bytearray)) and metadata else None,
        )
        payload_bytes = json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")
        return bytes([DexCommandSession]) + payload_bytes


    def create_value_transfer_data(self, to: str, value: float) -> bytes:
        model = ValueTransferModel(l1owner=self.l1_address, to=to, value=value)
        return bytes([DexCommandTransfer]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")


    def create_token_transfer_data(self, to: str, value: float, token: str) -> bytes:
        model = TokenTransferModel(l1owner=self.l1_address, to=to, value=value, token=token)
        return bytes([DexCommandTokenTransfer]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")


    def create_order_data(
        self,
        base_token: str,
        quote_token: str,
        side: int,
        price: float,
        quantity: float,
        order_type: int,
        order_mode: int,
        tp_limit: Optional[float] = None,
        sl_trigger: Optional[float] = None,
        sl_limit: Optional[float] = None,
    ) -> bytes:
        # Format decimal values to strings with 3 decimal places precision
        
        tpsl_model = None
        if tp_limit is not None or sl_trigger is not None:
            tp_limit_str = str(tp_limit) if tp_limit is not None else None
            sl_trigger_str = str(sl_trigger) if sl_trigger is not None else None
            sl_limit_str = str(sl_limit) if sl_limit is not None else None
            tpsl_model = TpslModel(tp_limit=tp_limit_str, sl_trigger=sl_trigger_str, sl_limit=sl_limit_str)

        model = OrderModel(
            l1owner=self.l1_address,
            base_token=base_token,
            quote_token=quote_token,
            side=side,
            price=price,
            quantity=quantity,
            order_type=order_type,
            order_mode=order_mode,
            tpsl=tpsl_model,
        )
        return bytes([DexCommandOrder]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")


    def create_cancel_data(self, order_id: str) -> bytes:
        model = CancelModel(l1owner=self.l1_address, order_id=order_id)
        return bytes([DexCommandCancel]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")
        

    def create_cancel_all_data(self) -> bytes:
        model = CancelAllModel(l1owner=self.l1_address)
        return bytes([DexCommandCancelAll]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")
        

    def create_modify_data(self, order_id: str, new_price: float = None, new_qty: float = None, order_mode: int = None) -> bytes:
        model = ModifyModel(l1owner=self.l1_address, order_id=order_id, new_price=new_price, new_qty=new_qty, order_mode=order_mode)
        return bytes([DexCommandModify]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")


    def create_stop_order_data(self, base_token: str, quote_token: str, stop_price: float, price: float, quantity: float, side: int, order_type: int, order_mode: int) -> bytes:
        model = StopOrderModel(
            l1owner=self.l1_address,
            base_token=base_token,
            quote_token=quote_token,
            stop_price=stop_price,
            price=price,
            quantity=quantity,
            side=side,
            order_type=order_type,
            order_mode=order_mode,
        )
        payload = model.to_wire()
        return bytes([DexCommandStopOrder]) + json.dumps(payload, separators=(",", ":")).encode("utf-8")


    # -----------------------------------------------------------------------
    # Perp (perpetual futures) wire builders
    #
    # Each returns ``command_byte + JSON(UTF-8)`` bytes, fed to
    # ``generate_alphasec_transaction`` exactly like spot. nonce = timestamp_ms,
    # identical signing flow. l1owner is lowercased to match the wire contract.
    # -----------------------------------------------------------------------

    def create_perp_order_data(
        self,
        market_id: int,
        side: int,
        price: PerpAmount,
        quantity: PerpAmount,
        reduce_only: bool,
        time_in_force: int,
        client_order_id: Optional[str] = None,
    ) -> bytes:
        from alphasec.perp.constants import MARKET   # local import: avoid perp<->sign import cycle
        if time_in_force == MARKET and price is None:
            price = 0   # server ignores price for market orders; default a deterministic 0
                        # when caller omits it. An explicit price is preserved to keep the
                        # cross-SDK golden-hex wire contract (tests/perp_wire_test.py).
        model = PerpOrderModel(
            l1owner=self.l1_address.lower(),
            market_id=market_id,
            side=side,
            price=perp_decimal_str(price),
            quantity=perp_decimal_str(quantity),
            is_reduce_only=reduce_only,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
        )
        return bytes([DexCommandPerpOrder]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")

    def create_perp_cancel_data(self, market_id: int, order_id: str) -> bytes:
        model = PerpCancelModel(l1owner=self.l1_address.lower(), market_id=market_id, order_id=order_id)
        return bytes([DexCommandPerpCancel]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")

    def create_perp_cancel_all_data(self, market_id: int) -> bytes:
        model = PerpCancelAllModel(l1owner=self.l1_address.lower(), market_id=market_id)
        return bytes([DexCommandPerpCancelAll]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")

    def create_perp_modify_data(
        self,
        market_id: int,
        order_id: str,
        new_price: Optional[PerpAmount] = None,
        new_quantity: Optional[PerpAmount] = None,
        client_order_id: Optional[str] = None,
    ) -> bytes:
        model = PerpModifyModel(
            l1owner=self.l1_address.lower(),
            market_id=market_id,
            order_id=order_id,
            new_price=perp_decimal_str(new_price) if new_price is not None else None,
            new_quantity=perp_decimal_str(new_quantity) if new_quantity is not None else None,
            client_order_id=client_order_id,
        )
        return bytes([DexCommandPerpModify]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")

    def create_perp_set_leverage_data(self, market_id: int, leverage: int) -> bytes:
        model = PerpSetLeverageModel(l1owner=self.l1_address.lower(), market_id=market_id, leverage=leverage)
        return bytes([DexCommandPerpSetLeverage]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")

    def create_perp_deposit_data(self, token: str, amount: PerpAmount) -> bytes:
        model = PerpDepositModel(l1owner=self.l1_address.lower(), token=token, amount=str(perp_scale(amount)))
        return bytes([DexCommandPerpDeposit]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")

    def create_perp_withdraw_data(self, token: str, amount: PerpAmount) -> bytes:
        model = PerpWithdrawModel(l1owner=self.l1_address.lower(), token=token, amount=str(perp_scale(amount)))
        return bytes([DexCommandPerpWithdraw]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")

    def generate_alphasec_transaction(self, timestamp_ms: int, data: bytes, wallet: Account = None) -> str:
        if wallet is None:
            wallet = self.get_wallet()

        tx = {
            "to": ALPHASEC_ORDER_CONTRACT_ADDR,
            "gas": 1000000,
            "maxFeePerGas": 0,
            "maxPriorityFeePerGas": 0,
            "value": 0,
            "nonce": timestamp_ms if timestamp_ms is not None else 0,
            "data": data,
            "chainId": self.chain_id,
        }

        signed = wallet.sign_transaction(tx)
        raw = signed.raw_transaction
        return "0x" + raw.hex()

    def generate_deposit_transaction(self, l1_provider: Web3, token_id, value: float, token_l1_address: Optional[str] = None, token_l1_decimals: int = 18) -> str:
        if self.l1_wallet is None:
            raise ValueError("l1_wallet is not set, deposit is only available for l1 wallet")

        value_onchain_unit = int(value * 10 ** token_l1_decimals)

        if token_id == ALPHASEC_NATIVE_TOKEN_ID:
            inbox_addr = MAINNET_INBOX_CONTRACT_ADDR if self.network == "mainnet" else KAIROS_INBOX_CONTRACT_ADDR
            contract = l1_provider.eth.contract(address=inbox_addr, abi=NATIVE_L1_ABI)
            tx = contract.functions.depositEth().build_transaction({
                "value": value_onchain_unit,
                "from": self.l1_address,
                "gas": 1000000,
                "nonce": l1_provider.eth.get_transaction_count(self.l1_address),
            })
            signed = self.l1_wallet.sign_transaction(tx)
            return "0x" + signed.raw_transaction.hex()
        else:
            if token_l1_address is None or not is_address(token_l1_address):
                raise ValueError("token_l1_address is invalid")

            erc20_gateway_addr = MAINNET_ERC20_GATEWAY_CONTRACT_ADDR if self.network == "mainnet" else KAIROS_ERC20_GATEWAY_CONTRACT_ADDR
            erc20_contract = l1_provider.eth.contract(address=token_l1_address, abi=ERC20_ABI)
            allowance = erc20_contract.functions.allowance(self.l1_address, erc20_gateway_addr).call()
            if allowance < value_onchain_unit: # value should be trading unit, not onchain unit (onchain unit == value * 10**decimals in kaia)
                tx = erc20_contract.functions.approve(erc20_gateway_addr, value_onchain_unit).build_transaction({
                    "from": self.l1_address,
                    "gas": 1000000,
                    "nonce": l1_provider.eth.get_transaction_count(self.l1_address),
                })
                signed = self.l1_wallet.sign_transaction(tx)
                try:
                    tx_hash = l1_provider.eth.send_raw_transaction(signed.raw_transaction)
                    l1_provider.eth.wait_for_transaction_receipt(tx_hash)
                except Exception as e:
                    raise ValueError("allowance approve failed")
            
            L2_GAS_LIMIT = 1000000
            L2_GAS_PRICE = 1000000
            MAX_SUBMISSION_COST = int(0.01 * 10**18)
            VALUE = int(0.02 * 10**18)
            data = l1_provider.codec.encode(['uint256', 'bytes'], [MAX_SUBMISSION_COST, '0x'])
            erc20_router_addr = MAINNET_ERC20_ROUTER_CONTRACT_ADDR if self.network == "mainnet" else KAIROS_ERC20_ROUTER_CONTRACT_ADDR
            contract = l1_provider.eth.contract(address=erc20_router_addr, abi=ERC20_ROUTER_ABI)
            tx = contract.functions.outboundTransfer(token_l1_address, self.l1_address, value_onchain_unit, L2_GAS_LIMIT, L2_GAS_PRICE, data).build_transaction({
                "from": self.l1_address,
                "value": VALUE,
                "gas": 1000000,
                "nonce": l1_provider.eth.get_transaction_count(self.l1_address),
            })
            signed = self.l1_wallet.sign_transaction(tx)
            return "0x" + signed.raw_transaction.hex()

    def generate_withdraw_transaction(self, l2_provider: Web3, token_id: str, value: float, token_l1_address: Optional[str] = None) -> str:
        if self.l1_wallet is None:
            raise ValueError("l1_wallet is not set, withdraw is only available for l1 wallet")

        endpoint_url = ALPHASEC_MAINNET_URL if self.network == "mainnet" else ALPHASEC_KAIROS_URL
        if l2_provider.provider.endpoint_uri != endpoint_url:
            raise ValueError("withdraw is only available for l2 provider")

        # All of the tokens have 18 decimals in Alphasec l2 chain
        value_onchain_unit = int(value * 10 ** 18)

        if token_id == ALPHASEC_NATIVE_TOKEN_ID:
            system_contract_addr = ALPHASEC_SYSTEM_CONTRACT_ADDR
            contract = l2_provider.eth.contract(address=system_contract_addr, abi=L2_SYSTEM_ABI)
            tx = contract.functions.withdrawEth(self.l1_address).build_transaction({
                "from": self.l1_address,
                "value": value_onchain_unit,
                "gas": 1000000,
                "nonce": int(time.time() * 1000),
            })
        else:
            erc20_router_addr = ALPHASEC_GATEWAY_ROUTER_CONTRACT_ADDR
            contract = l2_provider.eth.contract(address=erc20_router_addr, abi=L2_ERC20_ROUTER_ABI)
            tx = contract.functions.outboundTransfer(token_l1_address, self.l1_address, value_onchain_unit, '0x').build_transaction({
                "from": self.l1_address,
                "gas": 1000000,
                "nonce": int(time.time() * 1000),
            })

        signed = self.l1_wallet.sign_transaction(tx)
        return "0x" + signed.raw_transaction.hex()

    ## only for testing
    def get_withdraw_info_on_l2(self, l2_provider: Web3, block_num_on_l2: int) -> tuple[int, bytes, list[str], dict[str, any]]:
        if self.l1_wallet is None:
            raise ValueError("l1_wallet is not set, withdraw is only available for l1 wallet")

        endpoint_url = ALPHASEC_MAINNET_URL if self.network == "mainnet" else ALPHASEC_KAIROS_URL
        if l2_provider.provider.endpoint_uri != endpoint_url:
            raise ValueError("withdraw is only available for l2 provider")

        l2_system_contract = l2_provider.eth.contract(address=ALPHASEC_SYSTEM_CONTRACT_ADDR, abi=L2_SYSTEM_ABI)
        logs = l2_system_contract.events.L2ToL1Tx().get_logs(from_block=block_num_on_l2, to_block=block_num_on_l2)
        l2_to_l1_event = None
        for log in logs:
            if log.args.destination == MAINNET_ERC20_GATEWAY_CONTRACT_ADDR if self.network == "mainnet" else KAIROS_ERC20_GATEWAY_CONTRACT_ADDR or \
                log.args.destination == self.l1_address:
                l2_to_l1_event = log.args
                break

        if l2_to_l1_event is None:
            raise ValueError("l2 to l1 event for withdraw is not found")

        system_contract = l2_provider.eth.contract(address=ALPHASEC_SYSTEM_CONTRACT_ADDR, abi=L2_SYSTEM_ABI)
        merkle_tree_state = system_contract.functions.sendMerkleTreeState().call(block_identifier=block_num_on_l2)

        zk_interface_contract = l2_provider.eth.contract(address=ALPHASEC_ZK_INTERFACE_CONTRACT_ADDR, abi=ZK_INTERFACE_ABI)
        proof_data = zk_interface_contract.functions.constructOutboxProof(merkle_tree_state[0], l2_to_l1_event.position).call()

        return proof_data[0], proof_data[1], proof_data[2], l2_to_l1_event

    ## only for testing
    def is_withdraw_proof_registered(self, l1_provider: Web3, root: bytes) -> bool:
        endpoint_url = MAINNET_URL if self.network == "mainnet" else KAIROS_URL
        if l1_provider.provider.endpoint_uri != endpoint_url:
            raise ValueError("withdraw proof registration should be executed on the l1 provider")

        outbox_addr = MAINNET_OUTBOX_CONTRACT_ADDR if self.network == "mainnet" else KAIROS_OUTBOX_CONTRACT_ADDR
        contract = l1_provider.eth.contract(address=outbox_addr, abi=L1_OUTBOX_ABI)
        roots = contract.functions.roots(root).call()
        return roots.hex() != "0000000000000000000000000000000000000000000000000000000000000000"

    ## only for testing
    def generate_withdraw_transaction_on_l1(self, l1_provider: Web3, proof: list[str], l2_to_l1_event: dict[str, any]) -> str:
        if self.l1_wallet is None:
            raise ValueError("l1_wallet is not set, withdraw is only available for l1 wallet")

        endpoint_url = MAINNET_URL if self.network == "mainnet" else KAIROS_URL
        if l1_provider.provider.endpoint_uri != endpoint_url:
            raise ValueError("withdraw on l1 should be executed on the l1 provider")

        # check the proof is spent
        outbox_addr = MAINNET_OUTBOX_CONTRACT_ADDR if self.network == "mainnet" else KAIROS_OUTBOX_CONTRACT_ADDR
        contract = l1_provider.eth.contract(address=outbox_addr, abi=L1_OUTBOX_ABI)
        is_spent = contract.functions.isSpent(l2_to_l1_event.position).call()
        if is_spent:
            raise ValueError("withdraw proof is already spent")

        tx = contract.functions.executeTransaction(proof, l2_to_l1_event.position, l2_to_l1_event.caller, l2_to_l1_event.destination, l2_to_l1_event.arbBlockNum, l2_to_l1_event.ethBlockNum, l2_to_l1_event.timestamp, l2_to_l1_event.callvalue, l2_to_l1_event.data).build_transaction({
            "from": self.l1_address,
            "nonce": l1_provider.eth.get_transaction_count(self.l1_address),
            "gas": 1000000,
        })
        signed = self.l1_wallet.sign_transaction(tx)
        return "0x" + signed.raw_transaction.hex()
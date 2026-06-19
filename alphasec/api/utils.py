
def _split_market(market: str, symbol_token_id_map: dict):
    symbols = market.split("/")
    if len(symbols) != 2 or not symbols[0] or not symbols[1]:
        raise ValueError(f"Invalid market format '{market}'; expected 'BASE/QUOTE'")
    base, quote = symbols
    try:
        return symbol_token_id_map[base], symbol_token_id_map[quote]
    except KeyError as e:
        raise ValueError(f"Unknown token symbol: {e.args[0]}")

def market_to_market_id(market: str, symbol_token_id_map: dict):
    base_token_id, quote_token_id = _split_market(market, symbol_token_id_map)
    return f"{base_token_id}_{quote_token_id}"

def split_base_quote_token(market: str, symbol_token_id_map: dict):
    return _split_market(market, symbol_token_id_map)

def _clean_params(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}

def market_to_market_id(market: str, symbol_token_id_map: dict):
    symbols = market.split("/")
    base_token = symbols[0]
    quote_token = symbols[1]
    base_token_id = symbol_token_id_map[base_token]
    quote_token_id = symbol_token_id_map[quote_token]
    market_id = f"{base_token_id}_{quote_token_id}"
    return market_id

def split_base_quote_token(market: str, symbol_token_id_map: dict):
    symbols = market.split("/")
    base_token = symbols[0]
    quote_token = symbols[1]
    base_token_id = symbol_token_id_map[base_token]
    quote_token_id = symbol_token_id_map[quote_token]
    return base_token_id, quote_token_id

def _clean_params(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}
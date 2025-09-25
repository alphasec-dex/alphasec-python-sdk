"""
Basic example showing how to get ticker information.
This example only requires a base_url, no signer needed.
"""
import os

from alphasec import Agent, load_config

def main():
    # Load config using alphasec's load_config function
    config = load_config(os.path.dirname(__file__) + "/../config")
    
    # Initialize agent without signer for read-only operations
    agent = Agent(config['api_url'])
    
    print("=== Getting All Tickers ===")
    tickers = agent.get_tickers()
    print(tickers)
    
    print("\n=== Getting Single Ticker (KAIA/USDT) ===")
    ticker = agent.get_ticker("KAIA/USDT")
    print(ticker)
    
    print("\n=== Getting Market List ===")
    markets = agent.get_market_list()
    print(markets)

if __name__ == "__main__":
    main()

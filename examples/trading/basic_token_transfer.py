"""
Basic example showing how to transfer ERC-20 tokens.
This example requires a signer (private key).
"""
import os

from alphasec import Agent, load_config, AlphasecSigner

def main():
    # Load config using alphasec's load_config function
    config = load_config(os.path.dirname(__file__) + "/../config")
    
    # Create signer with config
    signer = AlphasecSigner(config)
    
    # Initialize agent with signer for trading operations
    agent = Agent(config['api_url'], signer=signer)
    
    # Use recipient address from tests
    recipient = "0x4D3cF56fB96c287387606862df55005d52FEa89b"
    
    # Transfer 1 unit of USDT (like in tests)
    token_symbol = "USDT"
    value = 1
    
    print(f"=== Transferring {value} {token_symbol} to {recipient} ===")
    result = agent.token_transfer(recipient, value, token_symbol)
    print(f"Transfer result: {result}")
    
    if result:
        print("Token transfer completed successfully!")
    else:
        print("Token transfer failed")

if __name__ == "__main__":
    main()

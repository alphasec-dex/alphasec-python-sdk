"""
Basic example showing how to manage sessions.
This example requires a signer (private key).
"""
import os
import sys
import time
from eth_account import Account

# Add parent directory to path to import alphasec
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from alphasec import Agent, load_config, AlphasecSigner

def main():
    # Load config using alphasec's load_config function
    config = load_config(os.path.dirname(os.path.dirname(__file__)))
    
    # Create signer with config
    signer = AlphasecSigner(config)
    
    # Initialize agent with signer for trading operations
    agent = Agent(config['api_url'], signer=signer)
    
    # Create a new session wallet
    sess_wallet = Account.create()
    session_id = "test-session-1"
    nonce = int(time.time() * 1000)
    expiry = int(time.time() * 1000) + 3600  # 1 hour from now
    
    print(f"=== Creating Session ===")
    print(f"Session ID: {session_id}")
    print(f"Session wallet address: {sess_wallet.address}")
    
    # Create session
    result = agent.create_session(session_id, sess_wallet, expiry, nonce)
    print(f"Create session result: {result}")
    
    if result:
        print("Session created successfully!")
        
        # Update session with new expiry
        print(f"\n=== Updating Session ===")
        new_nonce = int(time.time() * 1000)
        new_expiry = int(time.time() * 1000) + 7200  # 2 hours from now
        
        update_result = agent.update_session(session_id, sess_wallet, new_expiry, new_nonce)
        print(f"Update session result: {update_result}")
        
        # Delete session
        print(f"\n=== Deleting Session ===")
        delete_result = agent.delete_session(sess_wallet)
        print(f"Delete session result: {delete_result}")
        
    else:
        print("Failed to create session")

if __name__ == "__main__":
    main()

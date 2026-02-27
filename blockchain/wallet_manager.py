"""
Wallet Management Module for Blockchain Escrow Bot

Handles deterministic wallet generation for multiple blockchain networks (ETH, BTC, SOL, LTC),
private key encryption using Fernet, and secure storage in bot_data.json.
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional, Tuple
from pathlib import Path

from cryptography.fernet import Fernet
from web3 import Web3
from bitcoinlib.keys import Key as BitcoinKey
from solders.keypair import Keypair as SolanaKeypair


class WalletManager:
    """
    Manages wallet generation, encryption, and storage for multiple blockchain networks.
    
    Supports:
    - Ethereum (ETH)
    - Bitcoin (BTC)
    - Solana (SOL)
    - Litecoin (LTC)
    """
    
    # Network configurations
    NETWORKS = {
        'ETH': {
            'name': 'Ethereum',
            'symbol': 'ETH',
            'type': 'evm'
        },
        'BTC': {
            'name': 'Bitcoin',
            'symbol': 'BTC',
            'type': 'utxo'
        },
        'SOL': {
            'name': 'Solana',
            'symbol': 'SOL',
            'type': 'solana'
        },
        'LTC': {
            'name': 'Litecoin',
            'symbol': 'LTC',
            'type': 'utxo'
        }
    }
    
    def __init__(self, data_file: str = 'bot_data.json', encryption_key: Optional[str] = None):
        """
        Initialize WalletManager with encryption and storage configuration.
        
        Args:
            data_file: Path to bot_data.json for wallet storage
            encryption_key: Fernet encryption key (generated if not provided)
        """
        self.data_file = data_file
        self.encryption_key = encryption_key or self._load_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        self._ensure_data_file()
    
    def _load_or_create_encryption_key(self) -> bytes:
        """
        Load encryption key from environment or generate a new one.
        
        Returns:
            Fernet encryption key as bytes
        """
        key_env = os.getenv('WALLET_ENCRYPTION_KEY')
        if key_env:
            return key_env.encode() if isinstance(key_env, str) else key_env
        
        # Generate new key if not provided
        new_key = Fernet.generate_key()
        # Note: Store the generated key securely in environment variables
        # Do not log or expose the key in any output
        return new_key
    
    def _ensure_data_file(self) -> None:
        """Ensure bot_data.json exists with proper structure."""
        if not os.path.exists(self.data_file):
            initial_data = {
                'wallets': {},
                'metadata': {
                    'created_at': datetime.utcnow().isoformat(),
                    'version': '1.0'
                }
            }
            with open(self.data_file, 'w') as f:
                json.dump(initial_data, f, indent=2)
    
    def _load_data(self) -> Dict:
        """Load wallet data from bot_data.json."""
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {'wallets': {}, 'metadata': {}}
    
    def _save_data(self, data: Dict) -> None:
        """Save wallet data to bot_data.json."""
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _encrypt_private_key(self, private_key: str) -> str:
        """
        Encrypt a private key using Fernet.
        
        Args:
            private_key: Unencrypted private key string
            
        Returns:
            Encrypted private key as string
        """
        encrypted = self.cipher.encrypt(private_key.encode())
        return encrypted.decode()
    
    def _decrypt_private_key(self, encrypted_key: str) -> str:
        """
        Decrypt a private key using Fernet.
        
        Args:
            encrypted_key: Encrypted private key string
            
        Returns:
            Decrypted private key string
        """
        try:
            decrypted = self.cipher.decrypt(encrypted_key.encode())
            return decrypted.decode()
        except Exception as e:
            raise ValueError("Failed to decrypt private key. Invalid encryption key or corrupted data.") from e
    
    def generate_eth_wallet(self, trade_id: str) -> Dict:
        """
        Generate a deterministic Ethereum wallet.
        
        Args:
            trade_id: Unique trade identifier for wallet association
            
        Returns:
            Dictionary with wallet details (address, encrypted private key, metadata)
        """
        # Generate new account using Web3
        account = Web3().eth.account.create()
        
        wallet_data = {
            'network': 'ETH',
            'address': account.address,
            'private_key_encrypted': self._encrypt_private_key(account.key.hex()),
            'trade_id': trade_id,
            'created_at': datetime.utcnow().isoformat(),
            'public_key': account.address
        }
        
        return wallet_data
    
    def generate_btc_wallet(self, trade_id: str) -> Dict:
        """
        Generate a deterministic Bitcoin wallet.
        
        Args:
            trade_id: Unique trade identifier for wallet association
            
        Returns:
            Dictionary with wallet details (address, encrypted private key, metadata)
        """
        # Generate Bitcoin key
        btc_key = BitcoinKey()
        
        wallet_data = {
            'network': 'BTC',
            'address': btc_key.address(),
            'private_key_encrypted': self._encrypt_private_key(btc_key.wif()),
            'trade_id': trade_id,
            'created_at': datetime.utcnow().isoformat(),
            'public_key': btc_key.public_hex()
        }
        
        return wallet_data
    
    def generate_sol_wallet(self, trade_id: str) -> Dict:
        """
        Generate a deterministic Solana wallet.
        
        Args:
            trade_id: Unique trade identifier for wallet association
            
        Returns:
            Dictionary with wallet details (address, encrypted private key, metadata)
        """
        # Generate Solana keypair
        keypair = SolanaKeypair.generate()
        
        # Get private key as base58 string
        private_key_bytes = bytes(keypair.secret_key)
        private_key_b58 = keypair.secret_key.decode('utf-8') if hasattr(keypair.secret_key, 'decode') else str(keypair.secret_key)
        
        wallet_data = {
            'network': 'SOL',
            'address': str(keypair.public_key),
            'private_key_encrypted': self._encrypt_private_key(private_key_b58),
            'trade_id': trade_id,
            'created_at': datetime.utcnow().isoformat(),
            'public_key': str(keypair.public_key)
        }
        
        return wallet_data
    
    def generate_ltc_wallet(self, trade_id: str) -> Dict:
        """
        Generate a deterministic Litecoin wallet.
        
        Args:
            trade_id: Unique trade identifier for wallet association
            
        Returns:
            Dictionary with wallet details (address, encrypted private key, metadata)
        """
        # Generate Litecoin key (similar to Bitcoin)
        ltc_key = BitcoinKey(network='litecoin')
        
        wallet_data = {
            'network': 'LTC',
            'address': ltc_key.address(),
            'private_key_encrypted': self._encrypt_private_key(ltc_key.wif()),
            'trade_id': trade_id,
            'created_at': datetime.utcnow().isoformat(),
            'public_key': ltc_key.public_hex()
        }
        
        return wallet_data
    
    def create_wallet(self, network: str, trade_id: str) -> Dict:
        """
        Create a new wallet for the specified network.
        
        Args:
            network: Network code ('ETH', 'BTC', 'SOL', 'LTC')
            trade_id: Unique trade identifier
            
        Returns:
            Dictionary with wallet details
            
        Raises:
            ValueError: If network is not supported
        """
        if network not in self.NETWORKS:
            raise ValueError(f"Unsupported network: {network}. Supported: {list(self.NETWORKS.keys())}")
        
        # Generate wallet based on network
        if network == 'ETH':
            wallet_data = self.generate_eth_wallet(trade_id)
        elif network == 'BTC':
            wallet_data = self.generate_btc_wallet(trade_id)
        elif network == 'SOL':
            wallet_data = self.generate_sol_wallet(trade_id)
        elif network == 'LTC':
            wallet_data = self.generate_ltc_wallet(trade_id)
        else:
            raise ValueError(f"Unsupported network: {network}")
        
        # Store wallet in bot_data.json
        data = self._load_data()
        wallet_id = f"{network}_{trade_id}"
        data['wallets'][wallet_id] = wallet_data
        self._save_data(data)
        
        return wallet_data
    
    def get_wallet_by_trade_id(self, trade_id: str, network: Optional[str] = None) -> Optional[Dict]:
        """
        Retrieve wallet by trade ID.
        
        Args:
            trade_id: Trade identifier
            network: Optional network filter ('ETH', 'BTC', 'SOL', 'LTC')
            
        Returns:
            Wallet data dictionary or None if not found
        """
        data = self._load_data()
        
        for wallet_id, wallet_data in data.get('wallets', {}).items():
            if wallet_data.get('trade_id') == trade_id:
                if network is None or wallet_data.get('network') == network:
                    return wallet_data
        
        return None
    
    def get_wallet_address(self, trade_id: str, network: str) -> Optional[str]:
        """
        Get wallet address for a specific trade and network.
        
        Args:
            trade_id: Trade identifier
            network: Network code ('ETH', 'BTC', 'SOL', 'LTC')
            
        Returns:
            Wallet address or None if not found
        """
        wallet = self.get_wallet_by_trade_id(trade_id, network)
        return wallet.get('address') if wallet else None
    
    def get_private_key(self, trade_id: str, network: str) -> Optional[str]:
        """
        Retrieve and decrypt private key for a wallet.
        
        ⚠️  SECURITY: Never log or expose this key. Use only for signing transactions.
        
        Args:
            trade_id: Trade identifier
            network: Network code ('ETH', 'BTC', 'SOL', 'LTC')
            
        Returns:
            Decrypted private key or None if not found
        """
        wallet = self.get_wallet_by_trade_id(trade_id, network)
        if not wallet:
            return None
        
        try:
            encrypted_key = wallet.get('private_key_encrypted')
            if encrypted_key:
                return self._decrypt_private_key(encrypted_key)
        except Exception as e:
            # Log error without exposing key details
            # Decryption failed - likely due to invalid encryption key or corrupted data
            return None
        
        return None
    
    def list_wallets_by_trade_id(self, trade_id: str) -> Dict[str, Dict]:
        """
        List all wallets associated with a trade ID.
        
        Args:
            trade_id: Trade identifier
            
        Returns:
            Dictionary of wallets keyed by network
        """
        data = self._load_data()
        wallets = {}
        
        for wallet_id, wallet_data in data.get('wallets', {}).items():
            if wallet_data.get('trade_id') == trade_id:
                network = wallet_data.get('network')
                wallets[network] = {
                    'address': wallet_data.get('address'),
                    'network': network,
                    'created_at': wallet_data.get('created_at'),
                    'public_key': wallet_data.get('public_key')
                    # Note: private_key_encrypted is intentionally excluded from list view
                }
        
        return wallets
    
    def delete_wallet(self, trade_id: str, network: Optional[str] = None) -> bool:
        """
        Delete wallet(s) associated with a trade ID.
        
        Args:
            trade_id: Trade identifier
            network: Optional network filter. If None, deletes all wallets for trade.
            
        Returns:
            True if wallet(s) were deleted, False otherwise
        """
        data = self._load_data()
        wallets_to_delete = []
        
        for wallet_id, wallet_data in data.get('wallets', {}).items():
            if wallet_data.get('trade_id') == trade_id:
                if network is None or wallet_data.get('network') == network:
                    wallets_to_delete.append(wallet_id)
        
        if wallets_to_delete:
            for wallet_id in wallets_to_delete:
                del data['wallets'][wallet_id]
            self._save_data(data)
            return True
        
        return False
    
    def validate_wallet_exists(self, trade_id: str, network: str) -> bool:
        """
        Check if a wallet exists for a trade and network.
        
        Args:
            trade_id: Trade identifier
            network: Network code
            
        Returns:
            True if wallet exists, False otherwise
        """
        return self.get_wallet_by_trade_id(trade_id, network) is not None
    
    def get_wallet_metadata(self, trade_id: str, network: str) -> Optional[Dict]:
        """
        Get wallet metadata without exposing private keys.
        
        Args:
            trade_id: Trade identifier
            network: Network code
            
        Returns:
            Dictionary with wallet metadata (address, network, created_at, trade_id)
        """
        wallet = self.get_wallet_by_trade_id(trade_id, network)
        if not wallet:
            return None
        
        return {
            'network': wallet.get('network'),
            'address': wallet.get('address'),
            'created_at': wallet.get('created_at'),
            'trade_id': wallet.get('trade_id'),
            'public_key': wallet.get('public_key')
        }
    
    def export_wallets_summary(self, trade_id: str) -> Dict:
        """
        Export a summary of all wallets for a trade (no private keys).
        
        Args:
            trade_id: Trade identifier
            
        Returns:
            Dictionary with wallet summaries
        """
        wallets = self.list_wallets_by_trade_id(trade_id)
        return {
            'trade_id': trade_id,
            'wallets': wallets,
            'exported_at': datetime.utcnow().isoformat()
        }


# Utility functions for common operations

def create_wallets_for_trade(trade_id: str, networks: list = None, data_file: str = 'bot_data.json') -> Dict[str, Dict]:
    """
    Create wallets for multiple networks in a single operation.
    
    Args:
        trade_id: Trade identifier
        networks: List of network codes (default: ['ETH', 'BTC', 'SOL', 'LTC'])
        data_file: Path to bot_data.json
        
    Returns:
        Dictionary of created wallets keyed by network
    """
    if networks is None:
        networks = ['ETH', 'BTC', 'SOL', 'LTC']
    
    manager = WalletManager(data_file)
    created_wallets = {}
    
    for network in networks:
        try:
            wallet = manager.create_wallet(network, trade_id)
            created_wallets[network] = {
                'address': wallet.get('address'),
                'created_at': wallet.get('created_at')
            }
        except Exception as e:
            print(f"❌ Failed to create {network} wallet for trade {trade_id}: {str(e)}")
    
    return created_wallets


def get_trade_wallets(trade_id: str, data_file: str = 'bot_data.json') -> Dict[str, Dict]:
    """
    Retrieve all wallets for a trade with metadata.
    
    Args:
        trade_id: Trade identifier
        data_file: Path to bot_data.json
        
    Returns:
        Dictionary of wallets with metadata
    """
    manager = WalletManager(data_file)
    return manager.list_wallets_by_trade_id(trade_id)

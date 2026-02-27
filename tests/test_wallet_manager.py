"""Test specifications for Wallet Manager.

Covers:
- Wallet generation for each network (ETH, BTC, SOL, LTC)
- Key encryption/decryption with Fernet
- Wallet storage and retrieval by trade ID
- Metadata validation
- Security (no private key exposure in logs)
"""

import pytest
import json
import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from cryptography.fernet import Fernet
from web3 import Web3

# Import the WalletManager and utility functions
from blockchain.wallet_manager import (
    WalletManager,
    create_wallets_for_trade,
    get_trade_wallets,
)


# ==================== FIXTURES ====================

@pytest.fixture
def temp_data_file():
    """Create a temporary data file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    yield temp_path
    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def encryption_key():
    """Generate a test encryption key."""
    return Fernet.generate_key()


@pytest.fixture
def wallet_manager(temp_data_file, encryption_key):
    """Create a WalletManager instance with test configuration."""
    manager = WalletManager(data_file=temp_data_file, encryption_key=encryption_key)
    return manager


@pytest.fixture
def wallet_manager_no_key(temp_data_file):
    """Create a WalletManager instance without providing encryption key."""
    manager = WalletManager(data_file=temp_data_file)
    return manager


# ==================== INITIALIZATION TESTS ====================

class TestWalletManagerInitialization:
    """Test WalletManager initialization and setup."""

    def test_init_with_custom_encryption_key(self, temp_data_file, encryption_key):
        """Test initialization with custom encryption key."""
        manager = WalletManager(data_file=temp_data_file, encryption_key=encryption_key)
        assert manager.encryption_key == encryption_key
        assert manager.data_file == temp_data_file
        assert manager.cipher is not None

    def test_init_generates_encryption_key_if_not_provided(self, temp_data_file):
        """Test that encryption key is generated if not provided."""
        manager = WalletManager(data_file=temp_data_file)
        assert manager.encryption_key is not None
        assert isinstance(manager.encryption_key, bytes)
        # Key should be valid Fernet key
        assert len(manager.encryption_key) > 0

    def test_init_creates_data_file_if_not_exists(self, temp_data_file, encryption_key):
        """Test that data file is created with proper structure."""
        # Ensure file doesn't exist
        if os.path.exists(temp_data_file):
            os.remove(temp_data_file)
        
        manager = WalletManager(data_file=temp_data_file, encryption_key=encryption_key)
        
        # File should be created
        assert os.path.exists(temp_data_file)
        
        # File should have proper structure
        with open(temp_data_file, 'r') as f:
            data = json.load(f)
        
        assert 'wallets' in data
        assert 'metadata' in data
        assert isinstance(data['wallets'], dict)
        assert data['metadata']['version'] == '1.0'

    def test_init_preserves_existing_data_file(self, temp_data_file, encryption_key):
        """Test that existing data file is not overwritten."""
        # Create initial data
        initial_data = {
            'wallets': {'ETH_trade1': {'address': '0x123'}},
            'metadata': {'version': '1.0'}
        }
        with open(temp_data_file, 'w') as f:
            json.dump(initial_data, f)
        
        manager = WalletManager(data_file=temp_data_file, encryption_key=encryption_key)
        
        # Data should be preserved
        with open(temp_data_file, 'r') as f:
            data = json.load(f)
        
        assert 'ETH_trade1' in data['wallets']

    def test_cipher_initialized_correctly(self, wallet_manager, encryption_key):
        """Test that Fernet cipher is initialized with correct key."""
        # Cipher should be able to encrypt/decrypt
        test_message = "test_private_key"
        encrypted = wallet_manager.cipher.encrypt(test_message.encode())
        decrypted = wallet_manager.cipher.decrypt(encrypted).decode()
        assert decrypted == test_message

    def test_networks_constant_defined(self, wallet_manager):
        """Test that NETWORKS constant is properly defined."""
        assert hasattr(WalletManager, 'NETWORKS')
        assert 'ETH' in WalletManager.NETWORKS
        assert 'BTC' in WalletManager.NETWORKS
        assert 'SOL' in WalletManager.NETWORKS
        assert 'LTC' in WalletManager.NETWORKS
        
        # Each network should have required fields
        for network_code, network_info in WalletManager.NETWORKS.items():
            assert 'name' in network_info
            assert 'symbol' in network_info
            assert 'type' in network_info


# ==================== ENCRYPTION/DECRYPTION TESTS ====================

class TestEncryptionDecryption:
    """Test private key encryption and decryption."""

    def test_encrypt_private_key(self, wallet_manager):
        """Test that private key is encrypted."""
        private_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        encrypted = wallet_manager._encrypt_private_key(private_key)
        
        # Encrypted key should be different from original
        assert encrypted != private_key
        # Encrypted key should be a string
        assert isinstance(encrypted, str)
        # Encrypted key should be non-empty
        assert len(encrypted) > 0

    def test_decrypt_private_key(self, wallet_manager):
        """Test that encrypted private key can be decrypted."""
        original_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        encrypted = wallet_manager._encrypt_private_key(original_key)
        decrypted = wallet_manager._decrypt_private_key(encrypted)
        
        assert decrypted == original_key

    def test_encrypt_decrypt_roundtrip(self, wallet_manager):
        """Test encrypt/decrypt roundtrip for various key formats."""
        test_keys = [
            "0x1234567890abcdef",
            "5KN7MzqK5wt2TP1fQCYyHBtDrXdJuXbUzm4A9rKAteYV3qi5CVh",  # Bitcoin WIF
            "4vJ9JU1bJJE24JPnKnyQcK7Kn2HA5UZR2Ag6tkQP6f5DJrnZWZN",  # Solana key
            "T8rR4u6aB2r5s4t3u2v1w0x9y8z7a6b5c4d3e2f1g0h9i8j7k6l5m4n3o2p1q0r",
        ]
        
        for key in test_keys:
            encrypted = wallet_manager._encrypt_private_key(key)
            decrypted = wallet_manager._decrypt_private_key(encrypted)
            assert decrypted == key

    def test_decrypt_with_wrong_key_raises_error(self, temp_data_file, encryption_key):
        """Test that decryption with wrong key raises ValueError."""
        manager1 = WalletManager(data_file=temp_data_file, encryption_key=encryption_key)
        
        # Encrypt with first key
        private_key = "0x1234567890abcdef"
        encrypted = manager1._encrypt_private_key(private_key)
        
        # Try to decrypt with different key
        wrong_key = Fernet.generate_key()
        manager2 = WalletManager(data_file=temp_data_file, encryption_key=wrong_key)
        
        with pytest.raises(ValueError):
            manager2._decrypt_private_key(encrypted)

    def test_decrypt_corrupted_data_raises_error(self, wallet_manager):
        """Test that decrypting corrupted data raises ValueError."""
        corrupted_data = "not_a_valid_encrypted_string"
        
        with pytest.raises(ValueError):
            wallet_manager._decrypt_private_key(corrupted_data)

    def test_encrypt_empty_string(self, wallet_manager):
        """Test encryption of empty string."""
        encrypted = wallet_manager._encrypt_private_key("")
        decrypted = wallet_manager._decrypt_private_key(encrypted)
        assert decrypted == ""

    def test_encrypt_special_characters(self, wallet_manager):
        """Test encryption of keys with special characters."""
        special_key = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        encrypted = wallet_manager._encrypt_private_key(special_key)
        decrypted = wallet_manager._decrypt_private_key(encrypted)
        assert decrypted == special_key


# ==================== ETHEREUM WALLET GENERATION TESTS ====================

class TestEthereumWalletGeneration:
    """Test Ethereum wallet generation."""

    def test_generate_eth_wallet_returns_dict(self, wallet_manager):
        """Test that generate_eth_wallet returns a dictionary."""
        wallet = wallet_manager.generate_eth_wallet("trade_123")
        assert isinstance(wallet, dict)

    def test_generate_eth_wallet_has_required_fields(self, wallet_manager):
        """Test that generated ETH wallet has all required fields."""
        wallet = wallet_manager.generate_eth_wallet("trade_123")
        
        required_fields = [
            'network', 'address', 'private_key_encrypted', 'trade_id',
            'created_at', 'public_key'
        ]
        for field in required_fields:
            assert field in wallet

    def test_generate_eth_wallet_network_is_eth(self, wallet_manager):
        """Test that network field is set to ETH."""
        wallet = wallet_manager.generate_eth_wallet("trade_123")
        assert wallet['network'] == 'ETH'

    def test_generate_eth_wallet_trade_id_matches(self, wallet_manager):
        """Test that trade_id is correctly stored."""
        trade_id = "trade_123"
        wallet = wallet_manager.generate_eth_wallet(trade_id)
        assert wallet['trade_id'] == trade_id

    def test_generate_eth_wallet_address_is_valid(self, wallet_manager):
        """Test that generated address is a valid Ethereum address."""
        wallet = wallet_manager.generate_eth_wallet("trade_123")
        address = wallet['address']
        
        # Should start with 0x
        assert address.startswith('0x')
        # Should be 42 characters (0x + 40 hex chars)
        assert len(address) == 42
        # Should be valid hex
        try:
            int(address, 16)
        except ValueError:
            pytest.fail("Address is not valid hex")

    def test_generate_eth_wallet_private_key_encrypted(self, wallet_manager):
        """Test that private key is encrypted."""
        wallet = wallet_manager.generate_eth_wallet("trade_123")
        encrypted_key = wallet['private_key_encrypted']
        
        # Should not be empty
        assert encrypted_key
        # Should be a string
        assert isinstance(encrypted_key, str)
        # Should be decryptable
        decrypted = wallet_manager._decrypt_private_key(encrypted_key)
        assert decrypted.startswith('0x')

    def test_generate_eth_wallet_created_at_is_iso_format(self, wallet_manager):
        """Test that created_at is in ISO format."""
        wallet = wallet_manager.generate_eth_wallet("trade_123")
        created_at = wallet['created_at']
        
        # Should be parseable as ISO format
        try:
            datetime.fromisoformat(created_at)
        except ValueError:
            pytest.fail("created_at is not in ISO format")

    def test_generate_eth_wallet_public_key_matches_address(self, wallet_manager):
        """Test that public_key matches address."""
        wallet = wallet_manager.generate_eth_wallet("trade_123")
        assert wallet['public_key'] == wallet['address']

    def test_generate_eth_wallet_unique_addresses(self, wallet_manager):
        """Test that multiple calls generate different addresses."""
        wallet1 = wallet_manager.generate_eth_wallet("trade_1")
        wallet2 = wallet_manager.generate_eth_wallet("trade_2")
        
        assert wallet1['address'] != wallet2['address']

    def test_generate_eth_wallet_unique_private_keys(self, wallet_manager):
        """Test that multiple calls generate different private keys."""
        wallet1 = wallet_manager.generate_eth_wallet("trade_1")
        wallet2 = wallet_manager.generate_eth_wallet("trade_2")
        
        key1 = wallet_manager._decrypt_private_key(wallet1['private_key_encrypted'])
        key2 = wallet_manager._decrypt_private_key(wallet2['private_key_encrypted'])
        
        assert key1 != key2


# ==================== BITCOIN WALLET GENERATION TESTS ====================

class TestBitcoinWalletGeneration:
    """Test Bitcoin wallet generation."""

    def test_generate_btc_wallet_returns_dict(self, wallet_manager):
        """Test that generate_btc_wallet returns a dictionary."""
        wallet = wallet_manager.generate_btc_wallet("trade_123")
        assert isinstance(wallet, dict)

    def test_generate_btc_wallet_has_required_fields(self, wallet_manager):
        """Test that generated BTC wallet has all required fields."""
        wallet = wallet_manager.generate_btc_wallet("trade_123")
        
        required_fields = [
            'network', 'address', 'private_key_encrypted', 'trade_id',
            'created_at', 'public_key'
        ]
        for field in required_fields:
            assert field in wallet

    def test_generate_btc_wallet_network_is_btc(self, wallet_manager):
        """Test that network field is set to BTC."""
        wallet = wallet_manager.generate_btc_wallet("trade_123")
        assert wallet['network'] == 'BTC'

    def test_generate_btc_wallet_address_is_valid(self, wallet_manager):
        """Test that generated address is a valid Bitcoin address."""
        wallet = wallet_manager.generate_btc_wallet("trade_123")
        address = wallet['address']
        
        # Bitcoin addresses start with 1, 3, or bc1
        assert address[0] in ['1', '3', 'b']
        # Should be non-empty
        assert len(address) > 0

    def test_generate_btc_wallet_private_key_encrypted(self, wallet_manager):
        """Test that private key is encrypted."""
        wallet = wallet_manager.generate_btc_wallet("trade_123")
        encrypted_key = wallet['private_key_encrypted']
        
        # Should not be empty
        assert encrypted_key
        # Should be decryptable
        decrypted = wallet_manager._decrypt_private_key(encrypted_key)
        assert decrypted  # Should be non-empty

    def test_generate_btc_wallet_public_key_present(self, wallet_manager):
        """Test that public_key is present."""
        wallet = wallet_manager.generate_btc_wallet("trade_123")
        assert 'public_key' in wallet
        assert wallet['public_key']

    def test_generate_btc_wallet_unique_addresses(self, wallet_manager):
        """Test that multiple calls generate different addresses."""
        wallet1 = wallet_manager.generate_btc_wallet("trade_1")
        wallet2 = wallet_manager.generate_btc_wallet("trade_2")
        
        assert wallet1['address'] != wallet2['address']


# ==================== SOLANA WALLET GENERATION TESTS ====================

class TestSolanaWalletGeneration:
    """Test Solana wallet generation."""

    def test_generate_sol_wallet_returns_dict(self, wallet_manager):
        """Test that generate_sol_wallet returns a dictionary."""
        wallet = wallet_manager.generate_sol_wallet("trade_123")
        assert isinstance(wallet, dict)

    def test_generate_sol_wallet_has_required_fields(self, wallet_manager):
        """Test that generated SOL wallet has all required fields."""
        wallet = wallet_manager.generate_sol_wallet("trade_123")
        
        required_fields = [
            'network', 'address', 'private_key_encrypted', 'trade_id',
            'created_at', 'public_key'
        ]
        for field in required_fields:
            assert field in wallet

    def test_generate_sol_wallet_network_is_sol(self, wallet_manager):
        """Test that network field is set to SOL."""
        wallet = wallet_manager.generate_sol_wallet("trade_123")
        assert wallet['network'] == 'SOL'

    def test_generate_sol_wallet_address_is_valid(self, wallet_manager):
        """Test that generated address is a valid Solana address."""
        wallet = wallet_manager.generate_sol_wallet("trade_123")
        address = wallet['address']
        
        # Solana addresses are base58 encoded, typically 44 characters
        assert len(address) > 0
        assert isinstance(address, str)

    def test_generate_sol_wallet_private_key_encrypted(self, wallet_manager):
        """Test that private key is encrypted."""
        wallet = wallet_manager.generate_sol_wallet("trade_123")
        encrypted_key = wallet['private_key_encrypted']
        
        # Should not be empty
        assert encrypted_key
        # Should be decryptable
        decrypted = wallet_manager._decrypt_private_key(encrypted_key)
        assert decrypted

    def test_generate_sol_wallet_public_key_matches_address(self, wallet_manager):
        """Test that public_key matches address."""
        wallet = wallet_manager.generate_sol_wallet("trade_123")
        assert wallet['public_key'] == wallet['address']

    def test_generate_sol_wallet_unique_addresses(self, wallet_manager):
        """Test that multiple calls generate different addresses."""
        wallet1 = wallet_manager.generate_sol_wallet("trade_1")
        wallet2 = wallet_manager.generate_sol_wallet("trade_2")
        
        assert wallet1['address'] != wallet2['address']


# ==================== LITECOIN WALLET GENERATION TESTS ====================

class TestLitecoinWalletGeneration:
    """Test Litecoin wallet generation."""

    def test_generate_ltc_wallet_returns_dict(self, wallet_manager):
        """Test that generate_ltc_wallet returns a dictionary."""
        wallet = wallet_manager.generate_ltc_wallet("trade_123")
        assert isinstance(wallet, dict)

    def test_generate_ltc_wallet_has_required_fields(self, wallet_manager):
        """Test that generated LTC wallet has all required fields."""
        wallet = wallet_manager.generate_ltc_wallet("trade_123")
        
        required_fields = [
            'network', 'address', 'private_key_encrypted', 'trade_id',
            'created_at', 'public_key'
        ]
        for field in required_fields:
            assert field in wallet

    def test_generate_ltc_wallet_network_is_ltc(self, wallet_manager):
        """Test that network field is set to LTC."""
        wallet = wallet_manager.generate_ltc_wallet("trade_123")
        assert wallet['network'] == 'LTC'

    def test_generate_ltc_wallet_address_is_valid(self, wallet_manager):
        """Test that generated address is a valid Litecoin address."""
        wallet = wallet_manager.generate_ltc_wallet("trade_123")
        address = wallet['address']
        
        # Litecoin addresses start with L or M
        assert address[0] in ['L', 'M', '3']
        assert len(address) > 0

    def test_generate_ltc_wallet_private_key_encrypted(self, wallet_manager):
        """Test that private key is encrypted."""
        wallet = wallet_manager.generate_ltc_wallet("trade_123")
        encrypted_key = wallet['private_key_encrypted']
        
        # Should not be empty
        assert encrypted_key
        # Should be decryptable
        decrypted = wallet_manager._decrypt_private_key(encrypted_key)
        assert decrypted

    def test_generate_ltc_wallet_unique_addresses(self, wallet_manager):
        """Test that multiple calls generate different addresses."""
        wallet1 = wallet_manager.generate_ltc_wallet("trade_1")
        wallet2 = wallet_manager.generate_ltc_wallet("trade_2")
        
        assert wallet1['address'] != wallet2['address']


# ==================== WALLET CREATION TESTS ====================

class TestWalletCreation:
    """Test wallet creation and storage."""

    def test_create_wallet_eth(self, wallet_manager):
        """Test creating an Ethereum wallet."""
        wallet = wallet_manager.create_wallet('ETH', 'trade_123')
        
        assert wallet['network'] == 'ETH'
        assert wallet['trade_id'] == 'trade_123'
        assert 'address' in wallet
        assert 'private_key_encrypted' in wallet

    def test_create_wallet_btc(self, wallet_manager):
        """Test creating a Bitcoin wallet."""
        wallet = wallet_manager.create_wallet('BTC', 'trade_123')
        
        assert wallet['network'] == 'BTC'
        assert wallet['trade_id'] == 'trade_123'

    def test_create_wallet_sol(self, wallet_manager):
        """Test creating a Solana wallet."""
        wallet = wallet_manager.create_wallet('SOL', 'trade_123')
        
        assert wallet['network'] == 'SOL'
        assert wallet['trade_id'] == 'trade_123'

    def test_create_wallet_ltc(self, wallet_manager):
        """Test creating a Litecoin wallet."""
        wallet = wallet_manager.create_wallet('LTC', 'trade_123')
        
        assert wallet['network'] == 'LTC'
        assert wallet['trade_id'] == 'trade_123'

    def test_create_wallet_invalid_network_raises_error(self, wallet_manager):
        """Test that invalid network raises ValueError."""
        with pytest.raises(ValueError):
            wallet_manager.create_wallet('INVALID', 'trade_123')

    def test_create_wallet_stores_in_data_file(self, wallet_manager, temp_data_file):
        """Test that created wallet is stored in data file."""
        wallet = wallet_manager.create_wallet('ETH', 'trade_123')
        
        # Load data file and verify wallet is stored
        with open(temp_data_file, 'r') as f:
            data = json.load(f)
        
        wallet_id = f"ETH_trade_123"
        assert wallet_id in data['wallets']
        assert data['wallets'][wallet_id]['address'] == wallet['address']

    def test_create_wallet_multiple_networks_same_trade(self, wallet_manager):
        """Test creating wallets for multiple networks with same trade ID."""
        eth_wallet = wallet_manager.create_wallet('ETH', 'trade_123')
        btc_wallet = wallet_manager.create_wallet('BTC', 'trade_123')
        sol_wallet = wallet_manager.create_wallet('SOL', 'trade_123')
        
        assert eth_wallet['network'] == 'ETH'
        assert btc_wallet['network'] == 'BTC'
        assert sol_wallet['network'] == 'SOL'
        assert eth_wallet['trade_id'] == btc_wallet['trade_id'] == sol_wallet['trade_id']


# ==================== WALLET RETRIEVAL TESTS ====================

class TestWalletRetrieval:
    """Test wallet retrieval by trade ID."""

    def test_get_wallet_by_trade_id(self, wallet_manager):
        """Test retrieving wallet by trade ID."""
        created_wallet = wallet_manager.create_wallet('ETH', 'trade_123')
        retrieved_wallet = wallet_manager.get_wallet_by_trade_id('trade_123', 'ETH')
        
        assert retrieved_wallet is not None
        assert retrieved_wallet['address'] == created_wallet['address']
        assert retrieved_wallet['trade_id'] == 'trade_123'

    def test_get_wallet_by_trade_id_without_network_filter(self, wallet_manager):
        """Test retrieving wallet by trade ID without network filter."""
        wallet = wallet_manager.create_wallet('ETH', 'trade_123')
        retrieved = wallet_manager.get_wallet_by_trade_id('trade_123')
        
        assert retrieved is not None
        assert retrieved['address'] == wallet['address']

    def test_get_wallet_by_trade_id_not_found(self, wallet_manager):
        """Test that None is returned for non-existent wallet."""
        result = wallet_manager.get_wallet_by_trade_id('nonexistent_trade')
        assert result is None

    def test_get_wallet_by_trade_id_wrong_network(self, wallet_manager):
        """Test that None is returned when network doesn't match."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        result = wallet_manager.get_wallet_by_trade_id('trade_123', 'BTC')
        assert result is None

    def test_get_wallet_address(self, wallet_manager):
        """Test getting wallet address by trade ID and network."""
        created_wallet = wallet_manager.create_wallet('ETH', 'trade_123')
        address = wallet_manager.get_wallet_address('trade_123', 'ETH')
        
        assert address == created_wallet['address']

    def test_get_wallet_address_not_found(self, wallet_manager):
        """Test that None is returned for non-existent wallet address."""
        address = wallet_manager.get_wallet_address('nonexistent', 'ETH')
        assert address is None

    def test_list_wallets_by_trade_id(self, wallet_manager):
        """Test listing all wallets for a trade ID."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        wallet_manager.create_wallet('BTC', 'trade_123')
        wallet_manager.create_wallet('SOL', 'trade_123')
        
        wallets = wallet_manager.list_wallets_by_trade_id('trade_123')
        
        assert len(wallets) == 3
        assert 'ETH' in wallets
        assert 'BTC' in wallets
        assert 'SOL' in wallets

    def test_list_wallets_excludes_private_keys(self, wallet_manager):
        """Test that list_wallets_by_trade_id excludes private keys."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        wallets = wallet_manager.list_wallets_by_trade_id('trade_123')
        
        eth_wallet = wallets['ETH']
        assert 'private_key_encrypted' not in eth_wallet
        assert 'address' in eth_wallet
        assert 'network' in eth_wallet

    def test_list_wallets_empty_trade_id(self, wallet_manager):
        """Test listing wallets for non-existent trade ID."""
        wallets = wallet_manager.list_wallets_by_trade_id('nonexistent')
        assert wallets == {}


# ==================== PRIVATE KEY RETRIEVAL TESTS ====================

class TestPrivateKeyRetrieval:
    """Test private key retrieval and security."""

    def test_get_private_key(self, wallet_manager):
        """Test retrieving and decrypting private key."""
        created_wallet = wallet_manager.create_wallet('ETH', 'trade_123')
        private_key = wallet_manager.get_private_key('trade_123', 'ETH')
        
        assert private_key is not None
        assert private_key.startswith('0x')
        # Should be decryptable and valid
        assert len(private_key) > 0

    def test_get_private_key_not_found(self, wallet_manager):
        """Test that None is returned for non-existent wallet."""
        private_key = wallet_manager.get_private_key('nonexistent', 'ETH')
        assert private_key is None

    def test_get_private_key_wrong_network(self, wallet_manager):
        """Test that None is returned for wrong network."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        private_key = wallet_manager.get_private_key('trade_123', 'BTC')
        assert private_key is None

    def test_get_private_key_returns_decrypted_value(self, wallet_manager):
        """Test that get_private_key returns decrypted value."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        private_key = wallet_manager.get_private_key('trade_123', 'ETH')
        
        # Should be able to use the key (not encrypted)
        assert not private_key.startswith('gAAAAAA')  # Fernet encrypted strings start with this


# ==================== METADATA VALIDATION TESTS ====================

class TestMetadataValidation:
    """Test metadata validation and retrieval."""

    def test_get_wallet_metadata(self, wallet_manager):
        """Test retrieving wallet metadata."""
        created_wallet = wallet_manager.create_wallet('ETH', 'trade_123')
        metadata = wallet_manager.get_wallet_metadata('trade_123', 'ETH')
        
        assert metadata is not None
        assert metadata['network'] == 'ETH'
        assert metadata['address'] == created_wallet['address']
        assert metadata['trade_id'] == 'trade_123'
        assert 'created_at' in metadata
        assert 'public_key' in metadata

    def test_get_wallet_metadata_excludes_private_key(self, wallet_manager):
        """Test that metadata does not include private key."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        metadata = wallet_manager.get_wallet_metadata('trade_123', 'ETH')
        
        assert 'private_key_encrypted' not in metadata

    def test_get_wallet_metadata_not_found(self, wallet_manager):
        """Test that None is returned for non-existent wallet."""
        metadata = wallet_manager.get_wallet_metadata('nonexistent', 'ETH')
        assert metadata is None

    def test_wallet_metadata_has_iso_timestamp(self, wallet_manager):
        """Test that wallet metadata has ISO format timestamp."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        metadata = wallet_manager.get_wallet_metadata('trade_123', 'ETH')
        
        # Should be parseable as ISO format
        try:
            datetime.fromisoformat(metadata['created_at'])
        except ValueError:
            pytest.fail("created_at is not in ISO format")

    def test_export_wallets_summary(self, wallet_manager):
        """Test exporting wallet summary."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        wallet_manager.create_wallet('BTC', 'trade_123')
        
        summary = wallet_manager.export_wallets_summary('trade_123')
        
        assert summary['trade_id'] == 'trade_123'
        assert 'wallets' in summary
        assert 'exported_at' in summary
        assert len(summary['wallets']) == 2

    def test_export_wallets_summary_excludes_private_keys(self, wallet_manager):
        """Test that export summary excludes private keys."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        summary = wallet_manager.export_wallets_summary('trade_123')
        
        eth_wallet = summary['wallets']['ETH']
        assert 'private_key_encrypted' not in eth_wallet


# ==================== WALLET DELETION TESTS ====================

class TestWalletDeletion:
    """Test wallet deletion."""

    def test_delete_wallet_by_network(self, wallet_manager):
        """Test deleting a specific wallet by network."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        wallet_manager.create_wallet('BTC', 'trade_123')
        
        result = wallet_manager.delete_wallet('trade_123', 'ETH')
        
        assert result is True
        assert wallet_manager.get_wallet_by_trade_id('trade_123', 'ETH') is None
        assert wallet_manager.get_wallet_by_trade_id('trade_123', 'BTC') is not None

    def test_delete_all_wallets_for_trade(self, wallet_manager):
        """Test deleting all wallets for a trade ID."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        wallet_manager.create_wallet('BTC', 'trade_123')
        wallet_manager.create_wallet('SOL', 'trade_123')
        
        result = wallet_manager.delete_wallet('trade_123')
        
        assert result is True
        wallets = wallet_manager.list_wallets_by_trade_id('trade_123')
        assert len(wallets) == 0

    def test_delete_nonexistent_wallet_returns_false(self, wallet_manager):
        """Test that deleting non-existent wallet returns False."""
        result = wallet_manager.delete_wallet('nonexistent')
        assert result is False

    def test_delete_wallet_removes_from_storage(self, wallet_manager, temp_data_file):
        """Test that deleted wallet is removed from storage."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        wallet_manager.delete_wallet('trade_123', 'ETH')
        
        with open(temp_data_file, 'r') as f:
            data = json.load(f)
        
        wallet_id = "ETH_trade_123"
        assert wallet_id not in data['wallets']


# ==================== WALLET VALIDATION TESTS ====================

class TestWalletValidation:
    """Test wallet validation."""

    def test_validate_wallet_exists(self, wallet_manager):
        """Test checking if wallet exists."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        
        assert wallet_manager.validate_wallet_exists('trade_123', 'ETH') is True
        assert wallet_manager.validate_wallet_exists('trade_123', 'BTC') is False
        assert wallet_manager.validate_wallet_exists('nonexistent', 'ETH') is False

    def test_validate_wallet_exists_multiple_networks(self, wallet_manager):
        """Test validating wallets across multiple networks."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        wallet_manager.create_wallet('BTC', 'trade_123')
        wallet_manager.create_wallet('SOL', 'trade_123')
        
        assert wallet_manager.validate_wallet_exists('trade_123', 'ETH') is True
        assert wallet_manager.validate_wallet_exists('trade_123', 'BTC') is True
        assert wallet_manager.validate_wallet_exists('trade_123', 'SOL') is True
        assert wallet_manager.validate_wallet_exists('trade_123', 'LTC') is False


# ==================== SECURITY TESTS ====================

class TestSecurityNoPrivateKeyExposure:
    """Test security: no private key exposure in logs or outputs."""

    def test_private_key_not_in_wallet_list(self, wallet_manager):
        """Test that private key is not included in wallet list."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        wallets = wallet_manager.list_wallets_by_trade_id('trade_123')
        
        wallet_str = str(wallets)
        # Should not contain encrypted private key
        assert 'private_key_encrypted' not in wallet_str

    def test_private_key_not_in_metadata(self, wallet_manager):
        """Test that private key is not included in metadata."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        metadata = wallet_manager.get_wallet_metadata('trade_123', 'ETH')
        
        assert 'private_key_encrypted' not in metadata

    def test_private_key_not_in_export_summary(self, wallet_manager):
        """Test that private key is not included in export summary."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        summary = wallet_manager.export_wallets_summary('trade_123')
        
        summary_str = str(summary)
        assert 'private_key_encrypted' not in summary_str

    def test_get_private_key_requires_explicit_call(self, wallet_manager):
        """Test that private key requires explicit get_private_key call."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        
        # Should not be accessible through list_wallets
        wallets = wallet_manager.list_wallets_by_trade_id('trade_123')
        assert 'private_key_encrypted' not in wallets['ETH']
        
        # Should only be accessible through explicit get_private_key
        private_key = wallet_manager.get_private_key('trade_123', 'ETH')
        assert private_key is not None

    def test_encryption_key_not_exposed_in_error_messages(self, wallet_manager):
        """Test that encryption key is not exposed in error messages."""
        try:
            wallet_manager._decrypt_private_key("invalid_encrypted_data")
        except ValueError as e:
            error_msg = str(e)
            # Should not contain the actual encryption key
            assert wallet_manager.encryption_key.decode() not in error_msg

    def test_private_key_not_in_json_dump(self, wallet_manager):
        """Test that private key is not exposed when dumping to JSON."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        wallets = wallet_manager.list_wallets_by_trade_id('trade_123')
        
        json_str = json.dumps(wallets)
        # Should not contain encrypted private key
        assert 'private_key_encrypted' not in json_str


# ==================== UTILITY FUNCTION TESTS ====================

class TestUtilityFunctions:
    """Test utility functions."""

    def test_create_wallets_for_trade_all_networks(self, temp_data_file, encryption_key):
        """Test creating wallets for all networks."""
        created = create_wallets_for_trade('trade_123', data_file=temp_data_file)
        
        assert 'ETH' in created
        assert 'BTC' in created
        assert 'SOL' in created
        assert 'LTC' in created

    def test_create_wallets_for_trade_specific_networks(self, temp_data_file):
        """Test creating wallets for specific networks."""
        created = create_wallets_for_trade(
            'trade_123',
            networks=['ETH', 'BTC'],
            data_file=temp_data_file
        )
        
        assert 'ETH' in created
        assert 'BTC' in created
        assert 'SOL' not in created
        assert 'LTC' not in created

    def test_create_wallets_for_trade_returns_addresses(self, temp_data_file):
        """Test that created wallets include addresses."""
        created = create_wallets_for_trade('trade_123', data_file=temp_data_file)
        
        for network, wallet_info in created.items():
            assert 'address' in wallet_info
            assert 'created_at' in wallet_info

    def test_get_trade_wallets(self, temp_data_file):
        """Test retrieving trade wallets."""
        create_wallets_for_trade('trade_123', data_file=temp_data_file)
        wallets = get_trade_wallets('trade_123', data_file=temp_data_file)
        
        assert len(wallets) == 4
        assert 'ETH' in wallets
        assert 'BTC' in wallets
        assert 'SOL' in wallets
        assert 'LTC' in wallets

    def test_get_trade_wallets_excludes_private_keys(self, temp_data_file):
        """Test that get_trade_wallets excludes private keys."""
        create_wallets_for_trade('trade_123', data_file=temp_data_file)
        wallets = get_trade_wallets('trade_123', data_file=temp_data_file)
        
        for network, wallet_info in wallets.items():
            assert 'private_key_encrypted' not in wallet_info


# ==================== DATA PERSISTENCE TESTS ====================

class TestDataPersistence:
    """Test wallet data persistence."""

    def test_wallet_persists_across_manager_instances(self, temp_data_file, encryption_key):
        """Test that wallet data persists across manager instances."""
        # Create wallet with first manager
        manager1 = WalletManager(data_file=temp_data_file, encryption_key=encryption_key)
        wallet1 = manager1.create_wallet('ETH', 'trade_123')
        address1 = wallet1['address']
        
        # Retrieve with second manager
        manager2 = WalletManager(data_file=temp_data_file, encryption_key=encryption_key)
        wallet2 = manager2.get_wallet_by_trade_id('trade_123', 'ETH')
        address2 = wallet2['address']
        
        assert address1 == address2

    def test_multiple_trades_stored_separately(self, wallet_manager):
        """Test that multiple trades are stored separately."""
        wallet_manager.create_wallet('ETH', 'trade_1')
        wallet_manager.create_wallet('ETH', 'trade_2')
        
        wallet1 = wallet_manager.get_wallet_by_trade_id('trade_1', 'ETH')
        wallet2 = wallet_manager.get_wallet_by_trade_id('trade_2', 'ETH')
        
        assert wallet1['address'] != wallet2['address']
        assert wallet1['trade_id'] == 'trade_1'
        assert wallet2['trade_id'] == 'trade_2'

    def test_data_file_json_valid(self, wallet_manager, temp_data_file):
        """Test that data file contains valid JSON."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        
        with open(temp_data_file, 'r') as f:
            data = json.load(f)
        
        assert isinstance(data, dict)
        assert 'wallets' in data
        assert 'metadata' in data


# ==================== EDGE CASE TESTS ====================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_trade_id_with_special_characters(self, wallet_manager):
        """Test trade ID with special characters."""
        special_trade_id = "trade_123-456_789.abc"
        wallet = wallet_manager.create_wallet('ETH', special_trade_id)
        
        assert wallet['trade_id'] == special_trade_id
        retrieved = wallet_manager.get_wallet_by_trade_id(special_trade_id, 'ETH')
        assert retrieved is not None

    def test_trade_id_with_unicode(self, wallet_manager):
        """Test trade ID with unicode characters."""
        unicode_trade_id = "trade_🚀_123"
        wallet = wallet_manager.create_wallet('ETH', unicode_trade_id)
        
        assert wallet['trade_id'] == unicode_trade_id
        retrieved = wallet_manager.get_wallet_by_trade_id(unicode_trade_id, 'ETH')
        assert retrieved is not None

    def test_very_long_trade_id(self, wallet_manager):
        """Test with very long trade ID."""
        long_trade_id = "trade_" + "x" * 1000
        wallet = wallet_manager.create_wallet('ETH', long_trade_id)
        
        assert wallet['trade_id'] == long_trade_id
        retrieved = wallet_manager.get_wallet_by_trade_id(long_trade_id, 'ETH')
        assert retrieved is not None

    def test_empty_trade_id(self, wallet_manager):
        """Test with empty trade ID."""
        wallet = wallet_manager.create_wallet('ETH', "")
        assert wallet['trade_id'] == ""

    def test_case_sensitive_network_codes(self, wallet_manager):
        """Test that network codes are case-sensitive."""
        wallet_manager.create_wallet('ETH', 'trade_123')
        
        # Lowercase should not match
        result = wallet_manager.get_wallet_by_trade_id('trade_123', 'eth')
        assert result is None

    def test_case_sensitive_trade_ids(self, wallet_manager):
        """Test that trade IDs are case-sensitive."""
        wallet_manager.create_wallet('ETH', 'Trade_123')
        
        # Different case should not match
        result = wallet_manager.get_wallet_by_trade_id('trade_123', 'ETH')
        assert result is None

    def test_concurrent_wallet_creation(self, wallet_manager):
        """Test creating multiple wallets in sequence."""
        wallets = []
        for i in range(10):
            wallet = wallet_manager.create_wallet('ETH', f'trade_{i}')
            wallets.append(wallet)
        
        # All wallets should have unique addresses
        addresses = [w['address'] for w in wallets]
        assert len(addresses) == len(set(addresses))

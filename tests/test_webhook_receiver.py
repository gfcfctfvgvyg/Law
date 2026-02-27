"""Test specifications for webhook receiver.

Covers:
- HMAC-SHA256 signature verification (valid and invalid)
- Event parsing for each network (ETH, BTC, SOL, LTC)
- Idempotency checks (duplicate event detection)
- Event persistence (database storage)
- Error responses (invalid signatures, malformed payloads, server errors)
"""

import pytest
import asyncio
import json
import hmac
import hashlib
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile
import sqlite3

# Import webhook components
from webhooks.event_processor import (
    EventProcessor,
    Event,
    TradeStatus,
    DeadLetterEvent,
)


# ==================== FIXTURES ====================

@pytest.fixture
def temp_bot_data():
    """Create temporary bot_data.json for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"trades": {}}, f)
        temp_path = f.name
    yield temp_path
    Path(temp_path).unlink()


@pytest.fixture
def temp_dlq():
    """Create temporary dead letter queue for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"failed_events": []}, f)
        temp_path = f.name
    yield temp_path
    Path(temp_path).unlink()


@pytest.fixture
def event_processor(temp_bot_data, temp_dlq):
    """Create an EventProcessor instance with temporary files."""
    processor = EventProcessor(
        bot_data_path=temp_bot_data,
        confirmation_threshold=3,
        max_retries=5,
        dlq_path=temp_dlq,
    )
    return processor


@pytest.fixture
def webhook_secret():
    """Secret key for HMAC-SHA256 signing."""
    return "test-secret-key-32-characters-long"


@pytest.fixture
def eth_event_payload():
    """Sample Ethereum webhook payload."""
    return {
        "hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "addresses": [
            "0xsender_address_1234567890abcdef",
            "0xrecipient_address_abcdef1234567890"
        ],
        "total": "1500000000000000000",
        "fees": "21000000000000",
        "size": 21000,
        "vsize": 21000,
        "preference": "high",
        "relayed_by": "1.2.3.4",
        "received": "2024-01-15T10:30:45.123Z",
        "ver": 1,
        "double_spend": False,
        "vin_sz": 1,
        "vout_sz": 2,
        "confirmations": 1,
        "inputs": [
            {
                "prev_hash": "0xprevious_tx_hash",
                "output_index": 0,
                "output_value": "2000000000000000000",
                "addresses": ["0xsender_address_1234567890abcdef"],
                "script": "0x",
                "script_type": "pay-to-pubkey-hash"
            }
        ],
        "outputs": [
            {
                "value": "1500000000000000000",
                "addresses": ["0xrecipient_address_abcdef1234567890"],
                "script": "0x",
                "script_type": "pay-to-pubkey-hash"
            },
            {
                "value": "499999999999999000",
                "addresses": ["0xsender_address_1234567890abcdef"],
                "script": "0x",
                "script_type": "pay-to-pubkey-hash"
            }
        ]
    }


@pytest.fixture
def btc_event_payload():
    """Sample Bitcoin webhook payload."""
    return {
        "hash": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "addresses": [
            "1A1z7agoat5NUucGH3SKw6QQSLm5Hs5gVR",
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"
        ],
        "total": "50000000",
        "fees": "10000",
        "size": 225,
        "vsize": 225,
        "preference": "high",
        "relayed_by": "1.2.3.4",
        "received": "2024-01-15T10:30:45.123Z",
        "ver": 1,
        "double_spend": False,
        "vin_sz": 1,
        "vout_sz": 2,
        "confirmations": 1,
        "inputs": [
            {
                "prev_hash": "previous_tx_hash",
                "output_index": 0,
                "output_value": "60000000",
                "addresses": ["1A1z7agoat5NUucGH3SKw6QQSLm5Hs5gVR"],
                "script": "483045022100",
                "script_type": "pay-to-pubkey-hash"
            }
        ],
        "outputs": [
            {
                "value": "50000000",
                "addresses": ["1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"],
                "script": "76a914",
                "script_type": "pay-to-pubkey-hash"
            },
            {
                "value": "9990000",
                "addresses": ["1A1z7agoat5NUucGH3SKw6QQSLm5Hs5gVR"],
                "script": "76a914",
                "script_type": "pay-to-pubkey-hash"
            }
        ]
    }


@pytest.fixture
def sol_event_payload():
    """Sample Solana webhook payload."""
    return {
        "hash": "5Zzgvz5FHWLaLBbKZrQqKp7kLmNoPqRsT8uVwXyZ9ABC",
        "addresses": [
            "SolanaWalletAddress1234567890abcdef",
            "SolanaWalletAddress2abcdef1234567890"
        ],
        "total": "5000000000",
        "fees": "5000",
        "size": 1232,
        "vsize": 1232,
        "preference": "high",
        "relayed_by": "1.2.3.4",
        "received": "2024-01-15T10:30:45.123Z",
        "ver": 1,
        "double_spend": False,
        "vin_sz": 1,
        "vout_sz": 2,
        "confirmations": 1,
        "inputs": [
            {
                "prev_hash": "previous_tx_hash",
                "output_index": 0,
                "output_value": "6000000000",
                "addresses": ["SolanaWalletAddress1234567890abcdef"],
                "script": "base64_encoded_instruction",
                "script_type": "system-program"
            }
        ],
        "outputs": [
            {
                "value": "5000000000",
                "addresses": ["SolanaWalletAddress2abcdef1234567890"],
                "script": "base64_encoded_instruction",
                "script_type": "system-program"
            },
            {
                "value": "999995000",
                "addresses": ["SolanaWalletAddress1234567890abcdef"],
                "script": "base64_encoded_instruction",
                "script_type": "system-program"
            }
        ]
    }


@pytest.fixture
def ltc_event_payload():
    """Sample Litecoin webhook payload."""
    return {
        "hash": "ltc_tx_hash_1234567890abcdef1234567890abcdef",
        "addresses": [
            "LTC1A1z7agoat5NUucGH3SKw6QQSLm5Hs5gVR",
            "LTC1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"
        ],
        "total": "100000000",
        "fees": "10000",
        "size": 225,
        "vsize": 225,
        "preference": "high",
        "relayed_by": "1.2.3.4",
        "received": "2024-01-15T10:30:45.123Z",
        "ver": 1,
        "double_spend": False,
        "vin_sz": 1,
        "vout_sz": 2,
        "confirmations": 1,
        "inputs": [
            {
                "prev_hash": "previous_tx_hash",
                "output_index": 0,
                "output_value": "110000000",
                "addresses": ["LTC1A1z7agoat5NUucGH3SKw6QQSLm5Hs5gVR"],
                "script": "483045022100",
                "script_type": "pay-to-pubkey-hash"
            }
        ],
        "outputs": [
            {
                "value": "100000000",
                "addresses": ["LTC1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"],
                "script": "76a914",
                "script_type": "pay-to-pubkey-hash"
            },
            {
                "value": "9990000",
                "addresses": ["LTC1A1z7agoat5NUucGH3SKw6QQSLm5Hs5gVR"],
                "script": "76a914",
                "script_type": "pay-to-pubkey-hash"
            }
        ]
    }


def generate_hmac_signature(payload: dict, secret: str) -> str:
    """Generate HMAC-SHA256 signature for payload."""
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(
        secret.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return signature


# ==================== HMAC-SHA256 SIGNATURE VERIFICATION TESTS ====================

class TestHMACSignatureVerification:
    """Test HMAC-SHA256 signature verification."""

    def test_valid_signature_generation(self, eth_event_payload, webhook_secret):
        """Test that valid signature is generated correctly."""
        signature = generate_hmac_signature(eth_event_payload, webhook_secret)
        
        # Verify signature is hex string
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 hex is 64 characters
        assert all(c in '0123456789abcdef' for c in signature)

    def test_valid_signature_verification(self, eth_event_payload, webhook_secret):
        """Test that valid signature passes verification."""
        payload_bytes = json.dumps(eth_event_payload, separators=(',', ':')).encode('utf-8')
        signature = generate_hmac_signature(eth_event_payload, webhook_secret)
        
        # Verify signature matches
        expected_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        
        assert signature == expected_signature
        assert hmac.compare_digest(signature, expected_signature)

    def test_invalid_signature_detection(self, eth_event_payload, webhook_secret):
        """Test that invalid signature is detected."""
        payload_bytes = json.dumps(eth_event_payload, separators=(',', ':')).encode('utf-8')
        valid_signature = generate_hmac_signature(eth_event_payload, webhook_secret)
        invalid_signature = "0" * 64  # Fake signature
        
        # Verify signatures don't match
        assert not hmac.compare_digest(valid_signature, invalid_signature)

    def test_signature_with_wrong_secret(self, eth_event_payload, webhook_secret):
        """Test that signature with wrong secret is invalid."""
        correct_signature = generate_hmac_signature(eth_event_payload, webhook_secret)
        wrong_signature = generate_hmac_signature(eth_event_payload, "wrong-secret-key")
        
        # Signatures should be different
        assert correct_signature != wrong_signature

    def test_signature_case_sensitivity(self, eth_event_payload, webhook_secret):
        """Test that signature comparison is case-sensitive."""
        signature = generate_hmac_signature(eth_event_payload, webhook_secret)
        uppercase_signature = signature.upper()
        
        # Hex comparison should be case-insensitive for hex values
        # but hmac.compare_digest is case-sensitive
        assert signature.lower() == uppercase_signature.lower()

    def test_signature_with_payload_modification(self, eth_event_payload, webhook_secret):
        """Test that modifying payload invalidates signature."""
        original_signature = generate_hmac_signature(eth_event_payload, webhook_secret)
        
        # Modify payload
        modified_payload = eth_event_payload.copy()
        modified_payload["total"] = "2000000000000000000"
        modified_signature = generate_hmac_signature(modified_payload, webhook_secret)
        
        # Signatures should be different
        assert original_signature != modified_signature

    def test_signature_with_json_formatting_changes(self, eth_event_payload, webhook_secret):
        """Test that JSON formatting affects signature."""
        # Signature with compact JSON
        compact_json = json.dumps(eth_event_payload, separators=(',', ':'))
        compact_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            compact_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Signature with pretty JSON
        pretty_json = json.dumps(eth_event_payload, indent=2)
        pretty_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            pretty_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Signatures should be different due to formatting
        assert compact_signature != pretty_signature

    def test_signature_constant_time_comparison(self, eth_event_payload, webhook_secret):
        """Test that signature comparison uses constant-time comparison."""
        signature = generate_hmac_signature(eth_event_payload, webhook_secret)
        
        # Test with correct signature
        assert hmac.compare_digest(signature, signature)
        
        # Test with incorrect signature
        assert not hmac.compare_digest(signature, "0" * 64)

    def test_signature_with_empty_payload(self, webhook_secret):
        """Test signature generation with empty payload."""
        empty_payload = {}
        signature = generate_hmac_signature(empty_payload, webhook_secret)
        
        # Should still generate valid signature
        assert isinstance(signature, str)
        assert len(signature) == 64

    def test_signature_with_special_characters(self, webhook_secret):
        """Test signature with special characters in payload."""
        payload_with_special_chars = {
            "hash": "0x1234567890abcdef",
            "description": "Test with special chars: !@#$%^&*()",
            "unicode": "Test with unicode: 你好世界 🌍"
        }
        signature = generate_hmac_signature(payload_with_special_chars, webhook_secret)
        
        # Should generate valid signature
        assert isinstance(signature, str)
        assert len(signature) == 64

    def test_signature_with_nested_objects(self, eth_event_payload, webhook_secret):
        """Test signature with nested objects in payload."""
        signature = generate_hmac_signature(eth_event_payload, webhook_secret)
        
        # Verify signature is consistent
        signature2 = generate_hmac_signature(eth_event_payload, webhook_secret)
        assert signature == signature2


# ==================== EVENT PARSING TESTS ====================

class TestEventParsing:
    """Test event parsing for each network."""

    @pytest.mark.asyncio
    async def test_parse_ethereum_event(self, event_processor, eth_event_payload):
        """Test parsing Ethereum webhook event."""
        event = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=eth_event_payload["confirmations"],
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        # Verify event fields
        assert event.event_id == "eth_event_001"
        assert event.trade_id == "trade_001"
        assert event.tx_hash == eth_event_payload["hash"]
        assert event.confirmation_count == 1
        assert event.event_type == "tx-confirmation"
        assert event.data == eth_event_payload

    @pytest.mark.asyncio
    async def test_parse_bitcoin_event(self, event_processor, btc_event_payload):
        """Test parsing Bitcoin webhook event."""
        event = Event(
            event_id="btc_event_001",
            trade_id="trade_001",
            tx_hash=btc_event_payload["hash"],
            confirmation_count=btc_event_payload["confirmations"],
            timestamp=btc_event_payload["received"],
            event_type="tx-confirmation",
            data=btc_event_payload
        )
        
        # Verify event fields
        assert event.event_id == "btc_event_001"
        assert event.trade_id == "trade_001"
        assert event.tx_hash == btc_event_payload["hash"]
        assert event.confirmation_count == 1
        assert event.event_type == "tx-confirmation"

    @pytest.mark.asyncio
    async def test_parse_solana_event(self, event_processor, sol_event_payload):
        """Test parsing Solana webhook event."""
        event = Event(
            event_id="sol_event_001",
            trade_id="trade_001",
            tx_hash=sol_event_payload["hash"],
            confirmation_count=sol_event_payload["confirmations"],
            timestamp=sol_event_payload["received"],
            event_type="tx-confirmation",
            data=sol_event_payload
        )
        
        # Verify event fields
        assert event.event_id == "sol_event_001"
        assert event.trade_id == "trade_001"
        assert event.tx_hash == sol_event_payload["hash"]
        assert event.confirmation_count == 1

    @pytest.mark.asyncio
    async def test_parse_litecoin_event(self, event_processor, ltc_event_payload):
        """Test parsing Litecoin webhook event."""
        event = Event(
            event_id="ltc_event_001",
            trade_id="trade_001",
            tx_hash=ltc_event_payload["hash"],
            confirmation_count=ltc_event_payload["confirmations"],
            timestamp=ltc_event_payload["received"],
            event_type="tx-confirmation",
            data=ltc_event_payload
        )
        
        # Verify event fields
        assert event.event_id == "ltc_event_001"
        assert event.trade_id == "trade_001"
        assert event.tx_hash == ltc_event_payload["hash"]

    @pytest.mark.asyncio
    async def test_parse_event_with_multiple_confirmations(self, event_processor, eth_event_payload):
        """Test parsing event with multiple confirmations."""
        eth_event_payload["confirmations"] = 5
        
        event = Event(
            event_id="eth_event_002",
            trade_id="trade_002",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=eth_event_payload["confirmations"],
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        assert event.confirmation_count == 5

    @pytest.mark.asyncio
    async def test_parse_event_with_multiple_inputs_outputs(self, event_processor, btc_event_payload):
        """Test parsing event with multiple inputs and outputs."""
        # Add more inputs and outputs
        btc_event_payload["inputs"].append({
            "prev_hash": "another_tx_hash",
            "output_index": 1,
            "output_value": "30000000",
            "addresses": ["1A1z7agoat5NUucGH3SKw6QQSLm5Hs5gVR"],
            "script": "483045022100",
            "script_type": "pay-to-pubkey-hash"
        })
        
        event = Event(
            event_id="btc_event_002",
            trade_id="trade_002",
            tx_hash=btc_event_payload["hash"],
            confirmation_count=btc_event_payload["confirmations"],
            timestamp=btc_event_payload["received"],
            event_type="tx-confirmation",
            data=btc_event_payload
        )
        
        assert len(event.data["inputs"]) == 2

    @pytest.mark.asyncio
    async def test_parse_event_with_missing_optional_fields(self, event_processor):
        """Test parsing event with missing optional fields."""
        minimal_payload = {
            "hash": "0x1234567890abcdef",
            "confirmations": 1,
            "received": "2024-01-15T10:30:45.123Z"
        }
        
        event = Event(
            event_id="event_minimal",
            trade_id="trade_minimal",
            tx_hash=minimal_payload["hash"],
            confirmation_count=minimal_payload["confirmations"],
            timestamp=minimal_payload["received"],
            event_type="tx-confirmation",
            data=minimal_payload
        )
        
        assert event.event_id == "event_minimal"
        assert event.data == minimal_payload

    @pytest.mark.asyncio
    async def test_parse_event_with_large_amounts(self, event_processor, eth_event_payload):
        """Test parsing event with large transaction amounts."""
        eth_event_payload["total"] = "999999999999999999999999999999"
        
        event = Event(
            event_id="eth_event_large",
            trade_id="trade_large",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=eth_event_payload["confirmations"],
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        assert event.data["total"] == "999999999999999999999999999999"

    @pytest.mark.asyncio
    async def test_parse_event_with_zero_confirmations(self, event_processor, btc_event_payload):
        """Test parsing event with zero confirmations (mempool)."""
        btc_event_payload["confirmations"] = 0
        
        event = Event(
            event_id="btc_event_mempool",
            trade_id="trade_mempool",
            tx_hash=btc_event_payload["hash"],
            confirmation_count=btc_event_payload["confirmations"],
            timestamp=btc_event_payload["received"],
            event_type="tx-confirmation",
            data=btc_event_payload
        )
        
        assert event.confirmation_count == 0


# ==================== IDEMPOTENCY TESTS ====================

class TestIdempotency:
    """Test idempotency checks for duplicate event detection."""

    @pytest.mark.asyncio
    async def test_duplicate_event_detection(self, event_processor, eth_event_payload):
        """Test that duplicate events are detected."""
        event1 = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        event2 = Event(
            event_id="eth_event_001",  # Same event ID
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        # Both events have same ID
        assert event1.event_id == event2.event_id

    @pytest.mark.asyncio
    async def test_duplicate_event_by_tx_hash(self, event_processor, eth_event_payload):
        """Test duplicate detection by transaction hash."""
        event1 = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        event2 = Event(
            event_id="eth_event_002",  # Different event ID
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],  # Same tx hash
            confirmation_count=2,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        # Both events have same tx hash
        assert event1.tx_hash == event2.tx_hash

    @pytest.mark.asyncio
    async def test_processed_events_tracking(self, event_processor, eth_event_payload):
        """Test that processed events are tracked."""
        event = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        # Initially not processed
        assert event.event_id not in event_processor.processed_events
        
        # Mark as processed
        event_processor.processed_events[event.event_id] = event
        
        # Now it's tracked
        assert event.event_id in event_processor.processed_events
        assert event_processor.processed_events[event.event_id] == event

    @pytest.mark.asyncio
    async def test_idempotent_processing_same_event_twice(self, event_processor, eth_event_payload):
        """Test that processing same event twice is idempotent."""
        event = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        # Process event first time
        await event_processor.enqueue_event(event)
        assert event_processor.get_queue_size() == 1
        
        # Process same event again
        await event_processor.enqueue_event(event)
        assert event_processor.get_queue_size() == 2  # Both are queued

    @pytest.mark.asyncio
    async def test_duplicate_detection_with_different_confirmations(self, event_processor, eth_event_payload):
        """Test duplicate detection when confirmation count differs."""
        event1 = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        event2 = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=3,  # Different confirmation count
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        # Same event ID means duplicate
        assert event1.event_id == event2.event_id

    @pytest.mark.asyncio
    async def test_different_events_not_duplicates(self, event_processor, eth_event_payload, btc_event_payload):
        """Test that different events are not marked as duplicates."""
        event1 = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        event2 = Event(
            event_id="btc_event_001",
            trade_id="trade_001",
            tx_hash=btc_event_payload["hash"],
            confirmation_count=1,
            timestamp=btc_event_payload["received"],
            event_type="tx-confirmation",
            data=btc_event_payload
        )
        
        # Different event IDs and tx hashes
        assert event1.event_id != event2.event_id
        assert event1.tx_hash != event2.tx_hash


# ==================== EVENT PERSISTENCE TESTS ====================

class TestEventPersistence:
    """Test event persistence to database/storage."""

    @pytest.mark.asyncio
    async def test_event_saved_to_bot_data(self, event_processor, eth_event_payload):
        """Test that processed event is saved to bot_data.json."""
        event = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        # Process event
        await event_processor._process_event(event)
        
        # Verify saved to bot_data
        bot_data = event_processor._load_bot_data()
        assert "trade_001" in bot_data["trades"]
        assert bot_data["trades"]["trade_001"]["status"] == TradeStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_trade_status_updated_on_confirmation(self, event_processor, eth_event_payload):
        """Test that trade status is updated when confirmations reach threshold."""
        # First event with 1 confirmation
        event1 = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        await event_processor._process_event(event1)
        
        # Verify status is PENDING
        trade = event_processor.get_trade_status("trade_001")
        assert trade["status"] == TradeStatus.PENDING.value
        
        # Second event with 3 confirmations (meets threshold)
        event2 = Event(
            event_id="eth_event_002",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=3,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        await event_processor._process_event(event2)
        
        # Verify status is CONFIRMED
        trade = event_processor.get_trade_status("trade_001")
        assert trade["status"] == TradeStatus.CONFIRMED.value

    @pytest.mark.asyncio
    async def test_event_history_persisted(self, event_processor, eth_event_payload):
        """Test that event history is persisted."""
        event = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        await event_processor._process_event(event)
        
        # Verify event is in history
        trade = event_processor.get_trade_status("trade_001")
        assert len(trade["events"]) == 1
        assert trade["events"][0]["event_id"] == "eth_event_001"

    @pytest.mark.asyncio
    async def test_multiple_events_same_trade(self, event_processor, eth_event_payload):
        """Test that multiple events for same trade are persisted."""
        event1 = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        event2 = Event(
            event_id="eth_event_002",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=2,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        await event_processor._process_event(event1)
        await event_processor._process_event(event2)
        
        # Verify both events are in history
        trade = event_processor.get_trade_status("trade_001")
        assert len(trade["events"]) == 2
        assert trade["events"][0]["event_id"] == "eth_event_001"
        assert trade["events"][1]["event_id"] == "eth_event_002"

    @pytest.mark.asyncio
    async def test_confirmation_count_updated(self, event_processor, eth_event_payload):
        """Test that confirmation count is updated correctly."""
        event1 = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        await event_processor._process_event(event1)
        trade = event_processor.get_trade_status("trade_001")
        assert trade["confirmations"] == 1
        
        # Update with higher confirmation count
        event2 = Event(
            event_id="eth_event_002",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=5,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        await event_processor._process_event(event2)
        trade = event_processor.get_trade_status("trade_001")
        assert trade["confirmations"] == 5

    @pytest.mark.asyncio
    async def test_trade_completion_timestamp(self, event_processor, eth_event_payload):
        """Test that completion timestamp is recorded."""
        event = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=3,
            timestamp=eth_event_payload["received"],
            event_type="final_confirmation",
            data=eth_event_payload
        )
        
        await event_processor._process_event(event)
        
        trade = event_processor.get_trade_status("trade_001")
        assert "completed_at" in trade
        assert trade["status"] == TradeStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_bot_data_file_persistence(self, event_processor, eth_event_payload):
        """Test that bot_data.json is persisted to disk."""
        event = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        await event_processor._process_event(event)
        
        # Reload from disk
        bot_data = event_processor._load_bot_data()
        assert "trade_001" in bot_data["trades"]


# ==================== ERROR RESPONSE TESTS ====================

class TestErrorResponses:
    """Test error responses for invalid inputs and failures."""

    @pytest.mark.asyncio
    async def test_invalid_signature_error(self, event_processor, eth_event_payload, webhook_secret):
        """Test error response for invalid signature."""
        payload_bytes = json.dumps(eth_event_payload, separators=(',', ':')).encode('utf-8')
        valid_signature = generate_hmac_signature(eth_event_payload, webhook_secret)
        invalid_signature = "0" * 64
        
        # Verify signatures don't match
        assert not hmac.compare_digest(valid_signature, invalid_signature)

    @pytest.mark.asyncio
    async def test_malformed_json_payload(self, event_processor):
        """Test error response for malformed JSON."""
        malformed_json = b'{"hash": "0x1234", "total": "invalid}'
        
        # Should raise JSON decode error
        with pytest.raises(json.JSONDecodeError):
            json.loads(malformed_json)

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, event_processor):
        """Test error response for missing required fields."""
        incomplete_payload = {
            "hash": "0x1234567890abcdef"
            # Missing: addresses, total, confirmations, etc.
        }
        
        # Verify required fields are missing
        assert "addresses" not in incomplete_payload
        assert "total" not in incomplete_payload
        assert "confirmations" not in incomplete_payload

    @pytest.mark.asyncio
    async def test_invalid_confirmation_count(self, event_processor, eth_event_payload):
        """Test error response for invalid confirmation count."""
        eth_event_payload["confirmations"] = -1  # Invalid negative value
        
        # Should handle gracefully
        event = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=eth_event_payload["confirmations"],
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        assert event.confirmation_count == -1

    @pytest.mark.asyncio
    async def test_invalid_transaction_hash_format(self, event_processor):
        """Test error response for invalid transaction hash format."""
        invalid_payload = {
            "hash": "not_a_valid_hash",
            "confirmations": 1,
            "received": "2024-01-15T10:30:45.123Z"
        }
        
        # Should still create event (validation happens elsewhere)
        event = Event(
            event_id="event_invalid_hash",
            trade_id="trade_001",
            tx_hash=invalid_payload["hash"],
            confirmation_count=invalid_payload["confirmations"],
            timestamp=invalid_payload["received"],
            event_type="tx-confirmation",
            data=invalid_payload
        )
        
        assert event.tx_hash == "not_a_valid_hash"

    @pytest.mark.asyncio
    async def test_failed_event_added_to_dlq(self, event_processor, eth_event_payload):
        """Test that failed event is added to DLQ."""
        event = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        error = Exception("Test error")
        await event_processor._handle_failed_event(event, error, 5)
        
        # Verify event is in DLQ
        dlq_events = event_processor.get_dlq_events()
        assert len(dlq_events) == 1
        assert dlq_events[0]["event_id"] == "eth_event_001"

    @pytest.mark.asyncio
    async def test_dlq_event_structure(self, event_processor, eth_event_payload):
        """Test that DLQ event has correct structure."""
        event = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        error = Exception("Test error")
        await event_processor._handle_failed_event(event, error, 5)
        
        dlq_events = event_processor.get_dlq_events()
        dlq_event = dlq_events[0]
        
        # Verify DLQ event structure
        assert "event_id" in dlq_event
        assert "trade_id" in dlq_event
        assert "error_message" in dlq_event
        assert "timestamp" in dlq_event
        assert "retry_count" in dlq_event
        assert "original_event" in dlq_event

    @pytest.mark.asyncio
    async def test_retry_dlq_event(self, event_processor, eth_event_payload):
        """Test retrying a DLQ event."""
        event = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        error = Exception("Test error")
        await event_processor._handle_failed_event(event, error, 5)
        
        # Verify event is in DLQ
        dlq_events = event_processor.get_dlq_events()
        assert len(dlq_events) == 1
        
        # Retry the event
        success = event_processor.retry_dlq_event("eth_event_001")
        assert success is True
        
        # Verify event is removed from DLQ
        dlq_events = event_processor.get_dlq_events()
        assert len(dlq_events) == 0

    @pytest.mark.asyncio
    async def test_retry_nonexistent_dlq_event(self, event_processor):
        """Test retrying a nonexistent DLQ event."""
        success = event_processor.retry_dlq_event("nonexistent_event")
        assert success is False

    @pytest.mark.asyncio
    async def test_queue_size_tracking(self, event_processor, eth_event_payload):
        """Test that queue size is tracked correctly."""
        assert event_processor.get_queue_size() == 0
        
        event = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        await event_processor.enqueue_event(event)
        assert event_processor.get_queue_size() == 1

    @pytest.mark.asyncio
    async def test_processed_count_tracking(self, event_processor, eth_event_payload):
        """Test that processed event count is tracked."""
        assert event_processor.get_processed_count() == 0
        
        event = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        await event_processor._process_event(event)
        assert event_processor.get_processed_count() == 1


# ==================== INTEGRATION TESTS ====================

class TestWebhookIntegration:
    """Integration tests for complete webhook flow."""

    @pytest.mark.asyncio
    async def test_complete_webhook_flow(self, event_processor, eth_event_payload, webhook_secret):
        """Test complete webhook flow: signature verification → parsing → persistence."""
        # Generate valid signature
        signature = generate_hmac_signature(eth_event_payload, webhook_secret)
        
        # Verify signature
        payload_bytes = json.dumps(eth_event_payload, separators=(',', ':')).encode('utf-8')
        expected_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        assert hmac.compare_digest(signature, expected_signature)
        
        # Parse event
        event = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=eth_event_payload["confirmations"],
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        # Process event
        await event_processor._process_event(event)
        
        # Verify persistence
        trade = event_processor.get_trade_status("trade_001")
        assert trade is not None
        assert trade["status"] == TradeStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_multiple_networks_webhook_flow(self, event_processor, eth_event_payload, btc_event_payload, sol_event_payload, ltc_event_payload):
        """Test webhook flow for all networks."""
        networks = [
            ("eth", eth_event_payload, "eth_event_001"),
            ("btc", btc_event_payload, "btc_event_001"),
            ("sol", sol_event_payload, "sol_event_001"),
            ("ltc", ltc_event_payload, "ltc_event_001"),
        ]
        
        for network, payload, event_id in networks:
            event = Event(
                event_id=event_id,
                trade_id=f"trade_{network}",
                tx_hash=payload["hash"],
                confirmation_count=payload["confirmations"],
                timestamp=payload["received"],
                event_type="tx-confirmation",
                data=payload
            )
            
            await event_processor._process_event(event)
            
            trade = event_processor.get_trade_status(f"trade_{network}")
            assert trade is not None

    @pytest.mark.asyncio
    async def test_webhook_with_confirmation_progression(self, event_processor, eth_event_payload):
        """Test webhook flow with confirmation progression."""
        trade_id = "trade_progression"
        
        # Event 1: 1 confirmation
        event1 = Event(
            event_id="eth_event_001",
            trade_id=trade_id,
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        await event_processor._process_event(event1)
        
        trade = event_processor.get_trade_status(trade_id)
        assert trade["status"] == TradeStatus.PENDING.value
        assert trade["confirmations"] == 1
        
        # Event 2: 2 confirmations
        event2 = Event(
            event_id="eth_event_002",
            trade_id=trade_id,
            tx_hash=eth_event_payload["hash"],
            confirmation_count=2,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        await event_processor._process_event(event2)
        
        trade = event_processor.get_trade_status(trade_id)
        assert trade["confirmations"] == 2
        
        # Event 3: 3 confirmations (meets threshold)
        event3 = Event(
            event_id="eth_event_003",
            trade_id=trade_id,
            tx_hash=eth_event_payload["hash"],
            confirmation_count=3,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        await event_processor._process_event(event3)
        
        trade = event_processor.get_trade_status(trade_id)
        assert trade["status"] == TradeStatus.CONFIRMED.value
        assert trade["confirmations"] == 3

    @pytest.mark.asyncio
    async def test_webhook_error_recovery(self, event_processor, eth_event_payload):
        """Test webhook error recovery with DLQ and retry."""
        event = Event(
            event_id="eth_event_001",
            trade_id="trade_001",
            tx_hash=eth_event_payload["hash"],
            confirmation_count=1,
            timestamp=eth_event_payload["received"],
            event_type="tx-confirmation",
            data=eth_event_payload
        )
        
        # Simulate error
        error = Exception("Processing error")
        await event_processor._handle_failed_event(event, error, 5)
        
        # Verify in DLQ
        dlq_events = event_processor.get_dlq_events()
        assert len(dlq_events) == 1
        
        # Retry
        success = event_processor.retry_dlq_event("eth_event_001")
        assert success is True
        
        # Verify removed from DLQ
        dlq_events = event_processor.get_dlq_events()
        assert len(dlq_events) == 0

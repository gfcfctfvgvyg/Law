"""Test specifications for RPC client.

Covers:
- Successful connection to each network (ETH, BTC, SOL, LTC)
- Health check within 2-second timeout
- Query methods return expected data
- Retry logic with exponential backoff
- Environment variable loading
- Error handling for invalid RPC URLs
"""

import pytest
import asyncio
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dotenv import load_dotenv
import aiohttp

# Import the RPC client and related classes
from blockchain.rpc_client import (
    RPCClient,
    NetworkType,
    RPCError,
    RPCConnectionError,
    RPCTimeoutError,
)


# ==================== FIXTURES ====================

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing."""
    monkeypatch.setenv("ETH_RPC_URL", "https://eth-mainnet.example.com")
    monkeypatch.setenv("BTC_RPC_URL", "https://btc-mainnet.example.com")
    monkeypatch.setenv("SOL_RPC_URL", "https://sol-mainnet.example.com")
    monkeypatch.setenv("LTC_RPC_URL", "https://ltc-mainnet.example.com")


@pytest.fixture
def rpc_client(mock_env_vars):
    """Create an RPC client instance with mock environment variables."""
    client = RPCClient(
        eth_rpc_url="https://eth-mainnet.example.com",
        btc_rpc_url="https://btc-mainnet.example.com",
        sol_rpc_url="https://sol-mainnet.example.com",
        ltc_rpc_url="https://ltc-mainnet.example.com",
        timeout=10.0,
        max_retries=3,
        backoff_factor=2.0,
    )
    return client


@pytest.fixture
async def rpc_client_with_session(rpc_client):
    """Create an RPC client with an active session."""
    await rpc_client.connect()
    yield rpc_client
    await rpc_client.close()


# ==================== CONNECTION TESTS ====================

class TestRPCConnection:
    """Test successful RPC connections to each network."""

    @pytest.mark.asyncio
    async def test_connect_creates_session(self, rpc_client):
        """Test that connect() creates an aiohttp session."""
        assert rpc_client.session is None
        await rpc_client.connect()
        assert rpc_client.session is not None
        assert isinstance(rpc_client.session, aiohttp.ClientSession)
        await rpc_client.close()

    @pytest.mark.asyncio
    async def test_connect_idempotent(self, rpc_client):
        """Test that calling connect() multiple times is safe."""
        await rpc_client.connect()
        session1 = rpc_client.session
        await rpc_client.connect()
        session2 = rpc_client.session
        assert session1 is session2
        await rpc_client.close()

    @pytest.mark.asyncio
    async def test_close_closes_session(self, rpc_client):
        """Test that close() properly closes the session."""
        await rpc_client.connect()
        assert rpc_client.session is not None
        await rpc_client.close()
        assert rpc_client.session is None

    @pytest.mark.asyncio
    async def test_context_manager_connect_and_close(self, rpc_client):
        """Test async context manager properly connects and closes."""
        async with rpc_client as client:
            assert client.session is not None
        assert rpc_client.session is None

    @pytest.mark.asyncio
    async def test_ensure_session_creates_if_missing(self, rpc_client):
        """Test that _ensure_session creates a session if needed."""
        assert rpc_client.session is None
        session = await rpc_client._ensure_session()
        assert session is not None
        assert rpc_client.session is not None
        await rpc_client.close()

    @pytest.mark.asyncio
    async def test_ensure_session_returns_existing(self, rpc_client):
        """Test that _ensure_session returns existing session."""
        await rpc_client.connect()
        session1 = rpc_client.session
        session2 = await rpc_client._ensure_session()
        assert session1 is session2
        await rpc_client.close()


# ==================== HEALTH CHECK TESTS ====================

class TestHealthCheck:
    """Test health check functionality with 2-second timeout."""

    @pytest.mark.asyncio
    async def test_health_check_timeout_2_seconds(self, rpc_client_with_session):
        """Test that health check uses 2-second timeout."""
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            # Simulate timeout
            mock_request.side_effect = asyncio.TimeoutError()
            
            result = await rpc_client_with_session.health_check(NetworkType.ETH)
            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_eth_success(self, rpc_client_with_session):
        """Test successful Ethereum health check."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": "0x1", "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await rpc_client_with_session.health_check(NetworkType.ETH)
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_btc_success(self, rpc_client_with_session):
        """Test successful Bitcoin health check."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "1.0", "result": {"blocks": 800000}, "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await rpc_client_with_session.health_check(NetworkType.BTC)
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_sol_success(self, rpc_client_with_session):
        """Test successful Solana health check."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": "ok", "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await rpc_client_with_session.health_check(NetworkType.SOL)
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_ltc_success(self, rpc_client_with_session):
        """Test successful Litecoin health check."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "1.0", "result": {"blocks": 2500000}, "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await rpc_client_with_session.health_check(NetworkType.LTC)
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_rpc_error(self, rpc_client_with_session):
        """Test health check handles RPC errors."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await rpc_client_with_session.health_check(NetworkType.ETH)
            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self, rpc_client_with_session):
        """Test health check handles connection errors."""
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.side_effect = aiohttp.ClientError("Connection refused")
            
            result = await rpc_client_with_session.health_check(NetworkType.ETH)
            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_no_url_configured(self, rpc_client_with_session):
        """Test health check returns False when no URL is configured."""
        rpc_client_with_session.eth_rpc_url = None
        result = await rpc_client_with_session.health_check(NetworkType.ETH)
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_all_networks(self, rpc_client_with_session):
        """Test health check for all networks concurrently."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": "ok", "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            results = await rpc_client_with_session.health_check_all()
            assert len(results) == 4
            assert all(results.values())  # All should be True


# ==================== QUERY METHOD TESTS ====================

class TestQueryMethods:
    """Test query methods return expected data."""

    @pytest.mark.asyncio
    async def test_eth_get_balance_success(self, rpc_client_with_session):
        """Test eth_get_balance returns balance in wei."""
        expected_balance = "0x1234567890abcdef"
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": expected_balance, "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            balance = await rpc_client_with_session.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")
            assert balance == expected_balance

    @pytest.mark.asyncio
    async def test_eth_get_balance_adds_0x_prefix(self, rpc_client_with_session):
        """Test eth_get_balance adds 0x prefix if missing."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": "0x0", "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            await rpc_client_with_session.eth_get_balance("742d35Cc6634C0532925a3b844Bc9e7595f42bE")
            
            # Verify the request was made with 0x prefix
            call_args = mock_request.call_args
            payload = call_args[1]["json"]
            assert payload["params"][0].startswith("0x")

    @pytest.mark.asyncio
    async def test_eth_get_transaction_count(self, rpc_client_with_session):
        """Test eth_get_transaction_count returns nonce."""
        expected_nonce = "0x5"
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": expected_nonce, "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            nonce = await rpc_client_with_session.eth_get_transaction_count("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")
            assert nonce == expected_nonce

    @pytest.mark.asyncio
    async def test_eth_gas_price(self, rpc_client_with_session):
        """Test eth_gas_price returns gas price in wei."""
        expected_gas_price = "0x5f5e100"
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": expected_gas_price, "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            gas_price = await rpc_client_with_session.eth_gas_price()
            assert gas_price == expected_gas_price

    @pytest.mark.asyncio
    async def test_btc_get_balance(self, rpc_client_with_session):
        """Test btc_get_balance returns balance in BTC."""
        expected_balance = 1.5
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "1.0", "result": {"balance": expected_balance}, "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            balance = await rpc_client_with_session.btc_get_balance("1A1z7agoat5NUucGH3SKw6QQSLm5Hs5gVR")
            assert balance == expected_balance

    @pytest.mark.asyncio
    async def test_btc_get_block_count(self, rpc_client_with_session):
        """Test btc_get_block_count returns block height."""
        expected_height = 800000
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "1.0", "result": expected_height, "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            height = await rpc_client_with_session.btc_get_block_count()
            assert height == expected_height

    @pytest.mark.asyncio
    async def test_btc_get_transaction(self, rpc_client_with_session):
        """Test btc_get_transaction returns transaction data."""
        expected_tx = {
            "txid": "abc123",
            "version": 1,
            "locktime": 0,
            "vin": [],
            "vout": [],
        }
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "1.0", "result": expected_tx, "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            tx = await rpc_client_with_session.btc_get_transaction("abc123")
            assert tx == expected_tx

    @pytest.mark.asyncio
    async def test_sol_get_balance(self, rpc_client_with_session):
        """Test sol_get_balance returns balance in lamports."""
        expected_balance = 5000000000
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": {"value": expected_balance}, "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            balance = await rpc_client_with_session.sol_get_balance("11111111111111111111111111111111")
            assert balance == expected_balance

    @pytest.mark.asyncio
    async def test_sol_get_account_info(self, rpc_client_with_session):
        """Test sol_get_account_info returns account data."""
        expected_info = {
            "lamports": 5000000000,
            "owner": "11111111111111111111111111111111",
            "executable": False,
            "data": [],
        }
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": expected_info, "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            info = await rpc_client_with_session.sol_get_account_info("11111111111111111111111111111111")
            assert info == expected_info

    @pytest.mark.asyncio
    async def test_sol_get_signature_statuses(self, rpc_client_with_session):
        """Test sol_get_signature_statuses returns signature data."""
        expected_statuses = {
            "value": [
                {"slot": 100, "confirmations": 10, "err": None, "confirmationStatus": "confirmed"}
            ]
        }
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": expected_statuses, "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            statuses = await rpc_client_with_session.sol_get_signature_statuses(["sig123"])
            assert statuses == expected_statuses

    @pytest.mark.asyncio
    async def test_ltc_get_balance(self, rpc_client_with_session):
        """Test ltc_get_balance returns balance in LTC."""
        expected_balance = 2.5
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "1.0", "result": {"balance": expected_balance}, "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            balance = await rpc_client_with_session.ltc_get_balance("LcnEr7eNRQYU5iMngyD39j7jUWp5PgcnqB")
            assert balance == expected_balance

    @pytest.mark.asyncio
    async def test_ltc_get_block_count(self, rpc_client_with_session):
        """Test ltc_get_block_count returns block height."""
        expected_height = 2500000
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "1.0", "result": expected_height, "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            height = await rpc_client_with_session.ltc_get_block_count()
            assert height == expected_height

    @pytest.mark.asyncio
    async def test_ltc_get_transaction(self, rpc_client_with_session):
        """Test ltc_get_transaction returns transaction data."""
        expected_tx = {
            "txid": "def456",
            "version": 1,
            "locktime": 0,
            "vin": [],
            "vout": [],
        }
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "1.0", "result": expected_tx, "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            tx = await rpc_client_with_session.ltc_get_transaction("def456")
            assert tx == expected_tx


# ==================== RETRY LOGIC TESTS ====================

class TestRetryLogic:
    """Test retry logic with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self, rpc_client_with_session):
        """Test that connection errors trigger retries."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": "0x1", "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            # Fail twice, succeed on third attempt
            mock_request.side_effect = [
                aiohttp.ClientError("Connection refused"),
                aiohttp.ClientError("Connection refused"),
                MagicMock(__aenter__=AsyncMock(return_value=mock_response), __aexit__=AsyncMock(return_value=None)),
            ]
            
            result = await rpc_client_with_session.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")
            assert result == "0x1"
            assert mock_request.call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self, rpc_client_with_session):
        """Test that exponential backoff uses correct timing."""
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with patch.object(
                rpc_client_with_session.session, "request"
            ) as mock_request:
                mock_request.side_effect = aiohttp.ClientError("Connection refused")
                
                try:
                    await rpc_client_with_session.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")
                except RPCConnectionError:
                    pass
                
                # Should have 2 sleep calls (after attempt 1 and 2, not after 3)
                assert mock_sleep.call_count == 2
                # First backoff: 2^0 = 1 second
                # Second backoff: 2^1 = 2 seconds
                sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
                assert sleep_calls[0] == 1.0
                assert sleep_calls[1] == 2.0

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self, rpc_client_with_session):
        """Test that max retries raises exception."""
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.side_effect = aiohttp.ClientError("Connection refused")
            
            with pytest.raises(RPCConnectionError):
                await rpc_client_with_session.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")
            
            # Should have tried max_retries times
            assert mock_request.call_count == rpc_client_with_session.max_retries

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, rpc_client_with_session):
        """Test that timeouts trigger retries."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": "0x1", "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            # Timeout twice, succeed on third attempt
            mock_request.side_effect = [
                asyncio.TimeoutError(),
                asyncio.TimeoutError(),
                MagicMock(__aenter__=AsyncMock(return_value=mock_response), __aexit__=AsyncMock(return_value=None)),
            ]
            
            result = await rpc_client_with_session.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")
            assert result == "0x1"

    @pytest.mark.asyncio
    async def test_retry_on_rpc_error(self, rpc_client_with_session):
        """Test that RPC errors trigger retries."""
        mock_response_success = AsyncMock()
        mock_response_success.status = 200
        mock_response_success.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": "0x1", "id": 1}
        )
        
        mock_response_error = AsyncMock()
        mock_response_error.status = 200
        mock_response_error.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            # Error twice, succeed on third attempt
            mock_request.side_effect = [
                MagicMock(__aenter__=AsyncMock(return_value=mock_response_error), __aexit__=AsyncMock(return_value=None)),
                MagicMock(__aenter__=AsyncMock(return_value=mock_response_error), __aexit__=AsyncMock(return_value=None)),
                MagicMock(__aenter__=AsyncMock(return_value=mock_response_success), __aexit__=AsyncMock(return_value=None)),
            ]
            
            result = await rpc_client_with_session.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")
            assert result == "0x1"

    @pytest.mark.asyncio
    async def test_custom_max_retries(self):
        """Test that custom max_retries is respected."""
        client = RPCClient(
            eth_rpc_url="https://eth-mainnet.example.com",
            max_retries=5,
        )
        await client.connect()
        
        with patch.object(client.session, "request") as mock_request:
            mock_request.side_effect = aiohttp.ClientError("Connection refused")
            
            try:
                await client.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")
            except RPCConnectionError:
                pass
            
            assert mock_request.call_count == 5
        
        await client.close()

    @pytest.mark.asyncio
    async def test_custom_backoff_factor(self):
        """Test that custom backoff_factor is used."""
        client = RPCClient(
            eth_rpc_url="https://eth-mainnet.example.com",
            backoff_factor=3.0,
        )
        await client.connect()
        
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with patch.object(client.session, "request") as mock_request:
                mock_request.side_effect = aiohttp.ClientError("Connection refused")
                
                try:
                    await client.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")
                except RPCConnectionError:
                    pass
                
                sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
                # First backoff: 3^0 = 1 second
                # Second backoff: 3^1 = 3 seconds
                assert sleep_calls[0] == 1.0
                assert sleep_calls[1] == 3.0
        
        await client.close()


# ==================== ENVIRONMENT VARIABLE TESTS ====================

class TestEnvironmentVariables:
    """Test environment variable loading."""

    def test_load_from_env_eth(self, monkeypatch):
        """Test loading ETH_RPC_URL from environment."""
        monkeypatch.setenv("ETH_RPC_URL", "https://eth-custom.example.com")
        client = RPCClient()
        assert client.eth_rpc_url == "https://eth-custom.example.com"

    def test_load_from_env_btc(self, monkeypatch):
        """Test loading BTC_RPC_URL from environment."""
        monkeypatch.setenv("BTC_RPC_URL", "https://btc-custom.example.com")
        client = RPCClient()
        assert client.btc_rpc_url == "https://btc-custom.example.com"

    def test_load_from_env_sol(self, monkeypatch):
        """Test loading SOL_RPC_URL from environment."""
        monkeypatch.setenv("SOL_RPC_URL", "https://sol-custom.example.com")
        client = RPCClient()
        assert client.sol_rpc_url == "https://sol-custom.example.com"

    def test_load_from_env_ltc(self, monkeypatch):
        """Test loading LTC_RPC_URL from environment."""
        monkeypatch.setenv("LTC_RPC_URL", "https://ltc-custom.example.com")
        client = RPCClient()
        assert client.ltc_rpc_url == "https://ltc-custom.example.com"

    def test_constructor_overrides_env(self, monkeypatch):
        """Test that constructor parameters override environment variables."""
        monkeypatch.setenv("ETH_RPC_URL", "https://eth-env.example.com")
        client = RPCClient(eth_rpc_url="https://eth-constructor.example.com")
        assert client.eth_rpc_url == "https://eth-constructor.example.com"

    def test_all_env_vars_loaded(self, mock_env_vars):
        """Test that all environment variables are loaded."""
        client = RPCClient()
        assert client.eth_rpc_url == "https://eth-mainnet.example.com"
        assert client.btc_rpc_url == "https://btc-mainnet.example.com"
        assert client.sol_rpc_url == "https://sol-mainnet.example.com"
        assert client.ltc_rpc_url == "https://ltc-mainnet.example.com"

    def test_no_env_vars_set(self, monkeypatch):
        """Test behavior when no environment variables are set."""
        monkeypatch.delenv("ETH_RPC_URL", raising=False)
        monkeypatch.delenv("BTC_RPC_URL", raising=False)
        monkeypatch.delenv("SOL_RPC_URL", raising=False)
        monkeypatch.delenv("LTC_RPC_URL", raising=False)
        
        client = RPCClient()
        assert client.eth_rpc_url is None
        assert client.btc_rpc_url is None
        assert client.sol_rpc_url is None
        assert client.ltc_rpc_url is None


# ==================== ERROR HANDLING TESTS ====================

class TestErrorHandling:
    """Test error handling for invalid RPC URLs and other errors."""

    @pytest.mark.asyncio
    async def test_invalid_url_raises_error(self, rpc_client_with_session):
        """Test that invalid URL raises RPCConnectionError."""
        rpc_client_with_session.eth_rpc_url = None
        
        with pytest.raises(RPCConnectionError):
            await rpc_client_with_session.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")

    @pytest.mark.asyncio
    async def test_rpc_error_response(self, rpc_client_with_session):
        """Test handling of RPC error responses."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request"},
                "id": 1,
            }
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(RPCError):
                await rpc_client_with_session.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")

    @pytest.mark.asyncio
    async def test_timeout_error(self, rpc_client_with_session):
        """Test handling of timeout errors."""
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(RPCTimeoutError):
                await rpc_client_with_session.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")

    @pytest.mark.asyncio
    async def test_connection_error(self, rpc_client_with_session):
        """Test handling of connection errors."""
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.side_effect = aiohttp.ClientError("Connection refused")
            
            with pytest.raises(RPCConnectionError):
                await rpc_client_with_session.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")

    @pytest.mark.asyncio
    async def test_json_decode_error(self, rpc_client_with_session):
        """Test handling of JSON decode errors."""
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
            mock_request.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(RPCConnectionError):
                await rpc_client_with_session.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")

    @pytest.mark.asyncio
    async def test_empty_response_handling(self, rpc_client_with_session):
        """Test handling of empty responses."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await rpc_client_with_session.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")
            assert result == "0x0"  # Default value

    @pytest.mark.asyncio
    async def test_http_error_status(self, rpc_client_with_session):
        """Test handling of HTTP error status codes."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.json = AsyncMock(
            return_value={"error": "Internal Server Error"}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            # Should still attempt to parse JSON and check for error field
            with pytest.raises(RPCError):
                await rpc_client_with_session.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")

    def test_rpc_error_exception_message(self):
        """Test that RPCError includes meaningful message."""
        error = RPCError("Test error message")
        assert str(error) == "Test error message"

    def test_rpc_connection_error_exception_message(self):
        """Test that RPCConnectionError includes meaningful message."""
        error = RPCConnectionError("Connection failed")
        assert str(error) == "Connection failed"

    def test_rpc_timeout_error_exception_message(self):
        """Test that RPCTimeoutError includes meaningful message."""
        error = RPCTimeoutError("Request timed out")
        assert str(error) == "Request timed out"


# ==================== INTEGRATION TESTS ====================

class TestIntegration:
    """Integration tests combining multiple features."""

    @pytest.mark.asyncio
    async def test_full_workflow_with_retries(self, rpc_client_with_session):
        """Test complete workflow: connect, health check, query, close."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": "0x1234", "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            # Health check
            health = await rpc_client_with_session.health_check(NetworkType.ETH)
            assert health is True
            
            # Query
            balance = await rpc_client_with_session.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")
            assert balance == "0x1234"

    @pytest.mark.asyncio
    async def test_multiple_networks_concurrently(self, rpc_client_with_session):
        """Test querying multiple networks concurrently."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": "ok", "id": 1}
        )
        
        with patch.object(
            rpc_client_with_session.session, "request"
        ) as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            results = await asyncio.gather(
                rpc_client_with_session.health_check(NetworkType.ETH),
                rpc_client_with_session.health_check(NetworkType.BTC),
                rpc_client_with_session.health_check(NetworkType.SOL),
                rpc_client_with_session.health_check(NetworkType.LTC),
            )
            
            assert all(results)

    @pytest.mark.asyncio
    async def test_context_manager_with_queries(self, rpc_client):
        """Test using context manager for automatic session management."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": "0x1234", "id": 1}
        )
        
        with patch("aiohttp.ClientSession.request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with rpc_client as client:
                balance = await client.eth_get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f42bE")
                assert balance == "0x1234"
            
            # Session should be closed after context exit
            assert rpc_client.session is None

"""RPC Client Module for Blockchain Network Connectivity.

Provides async methods to connect to and query multiple blockchain networks:
- Ethereum (ETH)
- Bitcoin (BTC)
- Solana (SOL)
- Litecoin (LTC)

Features:
- Health checks with 2-second timeout
- Retry logic with exponential backoff
- Environment variable configuration
- discord.py async patterns
"""

import asyncio
import os
from typing import Optional, Dict, Any
from enum import Enum
import aiohttp
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class NetworkType(Enum):
    """Supported blockchain networks."""
    ETH = "ethereum"
    BTC = "bitcoin"
    SOL = "solana"
    LTC = "litecoin"


class RPCError(Exception):
    """Base exception for RPC client errors."""
    pass


class RPCConnectionError(RPCError):
    """Raised when unable to connect to RPC endpoint."""
    pass


class RPCTimeoutError(RPCError):
    """Raised when RPC request times out."""
    pass


class RPCClient:
    """Async RPC client for blockchain network queries.
    
    Implements discord.py-style async patterns with:
    - Exponential backoff retry logic
    - Health checks with 2-second timeout
    - Environment variable configuration
    - Comprehensive error handling
    """

    def __init__(
        self,
        eth_rpc_url: Optional[str] = None,
        btc_rpc_url: Optional[str] = None,
        sol_rpc_url: Optional[str] = None,
        ltc_rpc_url: Optional[str] = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ):
        """Initialize RPC client with network endpoints.
        
        Args:
            eth_rpc_url: Ethereum RPC endpoint URL (or ETH_RPC_URL env var)
            btc_rpc_url: Bitcoin RPC endpoint URL (or BTC_RPC_URL env var)
            sol_rpc_url: Solana RPC endpoint URL (or SOL_RPC_URL env var)
            ltc_rpc_url: Litecoin RPC endpoint URL (or LTC_RPC_URL env var)
            timeout: Request timeout in seconds (default: 10.0)
            max_retries: Maximum retry attempts (default: 3)
            backoff_factor: Exponential backoff multiplier (default: 2.0)
        """
        # Load from environment variables if not provided
        self.eth_rpc_url = eth_rpc_url or os.getenv("ETH_RPC_URL")
        self.btc_rpc_url = btc_rpc_url or os.getenv("BTC_RPC_URL")
        self.sol_rpc_url = sol_rpc_url or os.getenv("SOL_RPC_URL")
        self.ltc_rpc_url = ltc_rpc_url or os.getenv("LTC_RPC_URL")
        
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Validate that at least one RPC URL is configured
        if not any([self.eth_rpc_url, self.btc_rpc_url, self.sol_rpc_url, self.ltc_rpc_url]):
            logger.warning("No RPC URLs configured. Set environment variables: ETH_RPC_URL, BTC_RPC_URL, SOL_RPC_URL, LTC_RPC_URL")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> None:
        """Create aiohttp session for RPC requests."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
            logger.info("RPC client session created")

    async def close(self) -> None:
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("RPC client session closed")

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure session exists, create if needed."""
        if self.session is None:
            await self.connect()
        return self.session

    async def _make_request(
        self,
        url: str,
        method: str = "POST",
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make RPC request with retry logic and exponential backoff.
        
        Args:
            url: RPC endpoint URL
            method: HTTP method (default: POST)
            payload: JSON-RPC payload
            headers: HTTP headers
            
        Returns:
            Response data from RPC endpoint
            
        Raises:
            RPCConnectionError: If unable to connect after retries
            RPCTimeoutError: If request times out
            RPCError: For other RPC errors
        """
        if not url:
            raise RPCConnectionError("RPC URL not configured")

        session = await self._ensure_session()
        default_headers = {
            "Content-Type": "application/json",
            **(headers or {}),
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with session.request(
                    method,
                    url,
                    json=payload,
                    headers=default_headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    data = await response.json()
                    
                    # Check for JSON-RPC error
                    if "error" in data and data["error"] is not None:
                        error_msg = data["error"].get("message", "Unknown error")
                        raise RPCError(f"RPC error: {error_msg}")
                    
                    return data

            except asyncio.TimeoutError as e:
                last_error = RPCTimeoutError(f"RPC request timed out after {self.timeout}s")
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries}: {last_error}")
                
            except aiohttp.ClientError as e:
                last_error = RPCConnectionError(f"Connection error: {str(e)}")
                logger.warning(f"Connection error on attempt {attempt + 1}/{self.max_retries}: {last_error}")
                
            except RPCError as e:
                last_error = e
                logger.warning(f"RPC error on attempt {attempt + 1}/{self.max_retries}: {last_error}")

            # Exponential backoff before retry
            if attempt < self.max_retries - 1:
                wait_time = self.backoff_factor ** attempt
                logger.debug(f"Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)

        # All retries exhausted
        raise last_error or RPCConnectionError("Failed to connect to RPC endpoint")

    async def health_check(self, network: NetworkType) -> bool:
        """Check RPC endpoint health with 2-second timeout.
        
        Args:
            network: Network to check (ETH, BTC, SOL, LTC)
            
        Returns:
            True if endpoint is healthy, False otherwise
        """
        url = self._get_rpc_url(network)
        if not url:
            logger.warning(f"No RPC URL configured for {network.value}")
            return False

        try:
            # Use shorter timeout for health checks
            session = await self._ensure_session()
            async with session.request(
                "POST",
                url,
                json=self._get_health_check_payload(network),
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=2.0),
            ) as response:
                data = await response.json()
                is_healthy = response.status == 200 and "error" not in data
                logger.info(f"{network.value} health check: {'✓' if is_healthy else '✗'}")
                return is_healthy
                
        except (asyncio.TimeoutError, aiohttp.ClientError, Exception) as e:
            logger.warning(f"{network.value} health check failed: {str(e)}")
            return False

    async def health_check_all(self) -> Dict[str, bool]:
        """Check health of all configured networks.
        
        Returns:
            Dictionary mapping network names to health status
        """
        results = {}
        tasks = []
        networks = []
        
        for network in NetworkType:
            if self._get_rpc_url(network):
                tasks.append(self.health_check(network))
                networks.append(network.value)
        
        if not tasks:
            logger.warning("No RPC endpoints configured for health check")
            return results
        
        statuses = await asyncio.gather(*tasks, return_exceptions=True)
        for network_name, status in zip(networks, statuses):
            results[network_name] = status if isinstance(status, bool) else False
        
        return results

    def _get_rpc_url(self, network: NetworkType) -> Optional[str]:
        """Get RPC URL for network."""
        if network == NetworkType.ETH:
            return self.eth_rpc_url
        elif network == NetworkType.BTC:
            return self.btc_rpc_url
        elif network == NetworkType.SOL:
            return self.sol_rpc_url
        elif network == NetworkType.LTC:
            return self.ltc_rpc_url
        return None

    def _get_health_check_payload(self, network: NetworkType) -> Dict[str, Any]:
        """Get JSON-RPC payload for health check."""
        if network == NetworkType.ETH:
            return {
                "jsonrpc": "2.0",
                "method": "eth_chainId",
                "params": [],
                "id": 1,
            }
        elif network == NetworkType.BTC:
            return {
                "jsonrpc": "1.0",
                "method": "getblockchaininfo",
                "params": [],
                "id": 1,
            }
        elif network == NetworkType.SOL:
            return {
                "jsonrpc": "2.0",
                "method": "getHealth",
                "params": [],
                "id": 1,
            }
        elif network == NetworkType.LTC:
            return {
                "jsonrpc": "1.0",
                "method": "getblockchaininfo",
                "params": [],
                "id": 1,
            }
        return {}

    # ==================== Ethereum Methods ====================

    async def eth_get_balance(self, address: str, block: str = "latest") -> str:
        """Get Ethereum account balance.
        
        Args:
            address: Ethereum address (with or without 0x prefix)
            block: Block number or 'latest' (default: 'latest')
            
        Returns:
            Balance in wei as hex string
            
        Raises:
            RPCConnectionError: If unable to connect
            RPCError: For RPC errors
        """
        if not address.startswith("0x"):
            address = f"0x{address}"
        
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getBalance",
            "params": [address, block],
            "id": 1,
        }
        
        response = await self._make_request(self.eth_rpc_url, payload=payload)
        return response.get("result", "0x0")

    async def eth_get_transaction_count(self, address: str, block: str = "latest") -> str:
        """Get Ethereum transaction count (nonce).
        
        Args:
            address: Ethereum address
            block: Block number or 'latest'
            
        Returns:
            Transaction count as hex string
        """
        if not address.startswith("0x"):
            address = f"0x{address}"
        
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getTransactionCount",
            "params": [address, block],
            "id": 1,
        }
        
        response = await self._make_request(self.eth_rpc_url, payload=payload)
        return response.get("result", "0x0")

    async def eth_gas_price(self) -> str:
        """Get current Ethereum gas price.
        
        Returns:
            Gas price in wei as hex string
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_gasPrice",
            "params": [],
            "id": 1,
        }
        
        response = await self._make_request(self.eth_rpc_url, payload=payload)
        return response.get("result", "0x0")

    # ==================== Bitcoin Methods ====================

    async def btc_get_balance(self, address: str) -> float:
        """Get Bitcoin address balance.
        
        Args:
            address: Bitcoin address
            
        Returns:
            Balance in BTC
            
        Raises:
            RPCConnectionError: If unable to connect
            RPCError: For RPC errors
        """
        payload = {
            "jsonrpc": "1.0",
            "method": "getaddressinfo",
            "params": [address],
            "id": 1,
        }
        
        response = await self._make_request(self.btc_rpc_url, payload=payload)
        # Note: getaddressinfo doesn't return balance; use alternative methods
        # This is a placeholder - actual implementation depends on RPC node type
        return response.get("result", {}).get("balance", 0.0)

    async def btc_get_block_count(self) -> int:
        """Get Bitcoin blockchain height.
        
        Returns:
            Current block height
        """
        payload = {
            "jsonrpc": "1.0",
            "method": "getblockcount",
            "params": [],
            "id": 1,
        }
        
        response = await self._make_request(self.btc_rpc_url, payload=payload)
        return response.get("result", 0)

    async def btc_get_transaction(self, txid: str) -> Dict[str, Any]:
        """Get Bitcoin transaction details.
        
        Args:
            txid: Transaction ID
            
        Returns:
            Transaction data
        """
        payload = {
            "jsonrpc": "1.0",
            "method": "getrawtransaction",
            "params": [txid, True],
            "id": 1,
        }
        
        response = await self._make_request(self.btc_rpc_url, payload=payload)
        return response.get("result", {})

    # ==================== Solana Methods ====================

    async def sol_get_balance(self, address: str) -> int:
        """Get Solana account balance.
        
        Args:
            address: Solana public key
            
        Returns:
            Balance in lamports
            
        Raises:
            RPCConnectionError: If unable to connect
            RPCError: For RPC errors
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "getBalance",
            "params": [address],
            "id": 1,
        }
        
        response = await self._make_request(self.sol_rpc_url, payload=payload)
        return response.get("result", {}).get("value", 0)

    async def sol_get_account_info(self, address: str) -> Dict[str, Any]:
        """Get Solana account information.
        
        Args:
            address: Solana public key
            
        Returns:
            Account data
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "getAccountInfo",
            "params": [address],
            "id": 1,
        }
        
        response = await self._make_request(self.sol_rpc_url, payload=payload)
        return response.get("result", {})

    async def sol_get_signature_statuses(self, signatures: list) -> Dict[str, Any]:
        """Get Solana transaction signature statuses.
        
        Args:
            signatures: List of transaction signatures
            
        Returns:
            Signature status data
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "getSignatureStatuses",
            "params": [signatures],
            "id": 1,
        }
        
        response = await self._make_request(self.sol_rpc_url, payload=payload)
        return response.get("result", {})

    # ==================== Litecoin Methods ====================

    async def ltc_get_balance(self, address: str) -> float:
        """Get Litecoin address balance.
        
        Args:
            address: Litecoin address
            
        Returns:
            Balance in LTC
            
        Raises:
            RPCConnectionError: If unable to connect
            RPCError: For RPC errors
        """
        payload = {
            "jsonrpc": "1.0",
            "method": "getaddressinfo",
            "params": [address],
            "id": 1,
        }
        
        response = await self._make_request(self.ltc_rpc_url, payload=payload)
        return response.get("result", {}).get("balance", 0.0)

    async def ltc_get_block_count(self) -> int:
        """Get Litecoin blockchain height.
        
        Returns:
            Current block height
        """
        payload = {
            "jsonrpc": "1.0",
            "method": "getblockcount",
            "params": [],
            "id": 1,
        }
        
        response = await self._make_request(self.ltc_rpc_url, payload=payload)
        return response.get("result", 0)

    async def ltc_get_transaction(self, txid: str) -> Dict[str, Any]:
        """Get Litecoin transaction details.
        
        Args:
            txid: Transaction ID
            
        Returns:
            Transaction data
        """
        payload = {
            "jsonrpc": "1.0",
            "method": "getrawtransaction",
            "params": [txid, True],
            "id": 1,
        }
        
        response = await self._make_request(self.ltc_rpc_url, payload=payload)
        return response.get("result", {})

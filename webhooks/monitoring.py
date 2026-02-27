"""
Monitoring module for webhook metrics and health status.

Implements:
- Metrics collection for transactions, success/failure rates
- Discord embed formatting for dashboard display
- Real-time metrics updates in bot_data.json
- Webhook health status indicator
- Latest transaction tracking
- Pending confirmation monitoring
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

import discord
from discord.ext import commands

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class MetricsSnapshot:
    """Metrics snapshot data structure."""
    timestamp: str
    total_transactions: int
    successful_transactions: int
    failed_transactions: int
    pending_transactions: int
    confirmed_transactions: int
    success_rate: float
    failure_rate: float
    pending_confirmations: int
    average_confirmation_time: float
    health_status: str
    queue_size: int
    processed_count: int
    dlq_count: int
    latest_transactions: List[Dict[str, Any]]


class MetricsCollector:
    """
    Collects and manages webhook metrics.
    
    Tracks:
    - Transaction counts and statuses
    - Success/failure rates
    - Confirmation times
    - Webhook health status
    - Queue and DLQ metrics
    """

    def __init__(
        self,
        bot_data_path: str = "bot_data.json",
        dlq_path: str = "dead_letter_queue.json",
        metrics_path: str = "metrics.json",
    ):
        """
        Initialize the metrics collector.

        Args:
            bot_data_path: Path to bot_data.json file
            dlq_path: Path to dead letter queue file
            metrics_path: Path to metrics.json file
        """
        self.bot_data_path = Path(bot_data_path)
        self.dlq_path = Path(dlq_path)
        self.metrics_path = Path(metrics_path)
        
        # Initialize metrics file
        self._initialize_metrics_file()

    def _initialize_metrics_file(self) -> None:
        """Initialize metrics.json if it doesn't exist."""
        if not self.metrics_path.exists():
            initial_metrics = {
                "snapshots": [],
                "last_updated": datetime.utcnow().isoformat(),
            }
            self.metrics_path.write_text(json.dumps(initial_metrics, indent=2))
            logger.info(f"Created {self.metrics_path}")

    def _load_bot_data(self) -> Dict[str, Any]:
        """Load bot_data.json."""
        try:
            content = self.bot_data_path.read_text()
            return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading bot_data.json: {e}")
            return {"trades": {}}

    def _load_dlq(self) -> Dict[str, Any]:
        """Load dead letter queue."""
        try:
            content = self.dlq_path.read_text()
            return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading dead letter queue: {e}")
            return {"failed_events": []}

    def _load_metrics(self) -> Dict[str, Any]:
        """Load metrics.json."""
        try:
            content = self.metrics_path.read_text()
            return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading metrics.json: {e}")
            return {"snapshots": [], "last_updated": datetime.utcnow().isoformat()}

    def _save_metrics(self, data: Dict[str, Any]) -> None:
        """Save metrics.json."""
        try:
            self.metrics_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Error saving metrics.json: {e}")

    def _calculate_confirmation_time(self, trade: Dict[str, Any]) -> Optional[float]:
        """
        Calculate confirmation time for a trade in seconds.

        Args:
            trade: Trade data

        Returns:
            Confirmation time in seconds or None
        """
        try:
            created_at = datetime.fromisoformat(trade.get("created_at", ""))
            confirmed_at = trade.get("confirmed_at")
            
            if confirmed_at:
                confirmed_at = datetime.fromisoformat(confirmed_at)
                return (confirmed_at - created_at).total_seconds()
            
            return None
        except (ValueError, KeyError):
            return None

    def _determine_health_status(
        self,
        success_rate: float,
        failure_count: int,
        dlq_count: int,
    ) -> HealthStatus:
        """
        Determine webhook health status.

        Args:
            success_rate: Success rate percentage
            failure_count: Number of failed transactions
            dlq_count: Number of events in dead letter queue

        Returns:
            HealthStatus enum value
        """
        # Unhealthy: success rate < 80% or high DLQ count
        if success_rate < 80 or dlq_count > 10:
            return HealthStatus.UNHEALTHY
        
        # Degraded: success rate < 95% or moderate DLQ count
        if success_rate < 95 or dlq_count > 5:
            return HealthStatus.DEGRADED
        
        # Healthy: success rate >= 95% and low DLQ count
        return HealthStatus.HEALTHY

    def collect_metrics(self, queue_size: int = 0, processed_count: int = 0) -> MetricsSnapshot:
        """
        Collect current metrics snapshot.

        Args:
            queue_size: Current event queue size
            processed_count: Number of processed events

        Returns:
            MetricsSnapshot with current metrics
        """
        # Load data
        bot_data = self._load_bot_data()
        dlq = self._load_dlq()
        
        trades = bot_data.get("trades", {})
        failed_events = dlq.get("failed_events", [])
        
        # Calculate metrics
        total_transactions = len(trades)
        successful_transactions = sum(
            1 for trade in trades.values()
            if trade.get("status") == "completed"
        )
        failed_transactions = sum(
            1 for trade in trades.values()
            if trade.get("status") == "failed"
        )
        pending_transactions = sum(
            1 for trade in trades.values()
            if trade.get("status") in ["pending", "confirmed"]
        )
        confirmed_transactions = sum(
            1 for trade in trades.values()
            if trade.get("status") == "confirmed"
        )
        
        # Calculate rates
        success_rate = (
            (successful_transactions / total_transactions * 100)
            if total_transactions > 0
            else 0.0
        )
        failure_rate = (
            (failed_transactions / total_transactions * 100)
            if total_transactions > 0
            else 0.0
        )
        
        # Calculate pending confirmations
        pending_confirmations = sum(
            1 for trade in trades.values()
            if trade.get("status") == "pending"
        )
        
        # Calculate average confirmation time
        confirmation_times = []
        for trade in trades.values():
            conf_time = self._calculate_confirmation_time(trade)
            if conf_time is not None:
                confirmation_times.append(conf_time)
        
        average_confirmation_time = (
            sum(confirmation_times) / len(confirmation_times)
            if confirmation_times
            else 0.0
        )
        
        # Determine health status
        health_status = self._determine_health_status(
            success_rate,
            failed_transactions,
            len(failed_events),
        )
        
        # Get latest transactions
        latest_transactions = self._get_latest_transactions(trades, limit=5)
        
        # Create snapshot
        snapshot = MetricsSnapshot(
            timestamp=datetime.utcnow().isoformat(),
            total_transactions=total_transactions,
            successful_transactions=successful_transactions,
            failed_transactions=failed_transactions,
            pending_transactions=pending_transactions,
            confirmed_transactions=confirmed_transactions,
            success_rate=round(success_rate, 2),
            failure_rate=round(failure_rate, 2),
            pending_confirmations=pending_confirmations,
            average_confirmation_time=round(average_confirmation_time, 2),
            health_status=health_status.value,
            queue_size=queue_size,
            processed_count=processed_count,
            dlq_count=len(failed_events),
            latest_transactions=latest_transactions,
        )
        
        return snapshot

    def _get_latest_transactions(
        self,
        trades: Dict[str, Any],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get latest transactions sorted by creation time.

        Args:
            trades: Dictionary of trades
            limit: Maximum number of transactions to return

        Returns:
            List of latest transactions
        """
        # Sort trades by created_at timestamp
        sorted_trades = sorted(
            trades.items(),
            key=lambda x: x[1].get("created_at", ""),
            reverse=True,
        )
        
        # Extract latest transactions
        latest = []
        for trade_id, trade in sorted_trades[:limit]:
            latest.append({
                "trade_id": trade_id,
                "status": trade.get("status", "unknown"),
                "confirmations": trade.get("confirmations", 0),
                "created_at": trade.get("created_at", ""),
                "confirmed_at": trade.get("confirmed_at"),
                "completed_at": trade.get("completed_at"),
            })
        
        return latest

    def save_snapshot(self, snapshot: MetricsSnapshot) -> None:
        """
        Save metrics snapshot to metrics.json.

        Args:
            snapshot: MetricsSnapshot to save
        """
        metrics = self._load_metrics()
        snapshots = metrics.get("snapshots", [])
        
        # Add new snapshot
        snapshots.append(asdict(snapshot))
        
        # Keep only last 100 snapshots
        if len(snapshots) > 100:
            snapshots = snapshots[-100:]
        
        metrics["snapshots"] = snapshots
        metrics["last_updated"] = datetime.utcnow().isoformat()
        
        self._save_metrics(metrics)
        logger.info("Metrics snapshot saved")

    def get_latest_snapshot(self) -> Optional[MetricsSnapshot]:
        """
        Get the latest metrics snapshot.

        Returns:
            Latest MetricsSnapshot or None
        """
        metrics = self._load_metrics()
        snapshots = metrics.get("snapshots", [])
        
        if not snapshots:
            return None
        
        latest = snapshots[-1]
        return MetricsSnapshot(**latest)

    def get_metrics_history(self, hours: int = 24) -> List[MetricsSnapshot]:
        """
        Get metrics history for the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            List of MetricsSnapshot objects
        """
        metrics = self._load_metrics()
        snapshots = metrics.get("snapshots", [])
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        history = []
        for snapshot_data in snapshots:
            snapshot_time = datetime.fromisoformat(snapshot_data["timestamp"])
            if snapshot_time >= cutoff_time:
                history.append(MetricsSnapshot(**snapshot_data))
        
        return history


class MonitoringCog(commands.Cog):
    """Discord cog for monitoring commands."""

    def __init__(self, bot: commands.Bot, metrics_collector: MetricsCollector):
        """
        Initialize the monitoring cog.

        Args:
            bot: Discord bot instance
            metrics_collector: MetricsCollector instance
        """
        self.bot = bot
        self.metrics = metrics_collector

    def _create_metrics_embed(self, snapshot: MetricsSnapshot) -> discord.Embed:
        """
        Create a Discord embed for metrics dashboard.

        Args:
            snapshot: MetricsSnapshot to display

        Returns:
            discord.Embed object
        """
        # Determine color based on health status
        color_map = {
            HealthStatus.HEALTHY.value: discord.Color.green(),
            HealthStatus.DEGRADED.value: discord.Color.orange(),
            HealthStatus.UNHEALTHY.value: discord.Color.red(),
        }
        color = color_map.get(snapshot.health_status, discord.Color.blue())
        
        # Create embed
        embed = discord.Embed(
            title="📊 Webhook Monitoring Dashboard",
            description=f"Real-time metrics snapshot",
            color=color,
            timestamp=datetime.fromisoformat(snapshot.timestamp),
        )
        
        # Health Status
        health_emoji = {
            HealthStatus.HEALTHY.value: "✅",
            HealthStatus.DEGRADED.value: "⚠️",
            HealthStatus.UNHEALTHY.value: "❌",
        }
        embed.add_field(
            name="Health Status",
            value=f"{health_emoji.get(snapshot.health_status, '❓')} {snapshot.health_status.upper()}",
            inline=False,
        )
        
        # Transaction Summary
        embed.add_field(
            name="📈 Transaction Summary",
            value=(
                f"**Total**: {snapshot.total_transactions}\n"
                f"**Completed**: {snapshot.successful_transactions}\n"
                f"**Failed**: {snapshot.failed_transactions}\n"
                f"**Pending**: {snapshot.pending_transactions}\n"
                f"**Confirmed**: {snapshot.confirmed_transactions}"
            ),
            inline=True,
        )
        
        # Success/Failure Rates
        embed.add_field(
            name="📊 Success Rates",
            value=(
                f"**Success**: {snapshot.success_rate}%\n"
                f"**Failure**: {snapshot.failure_rate}%"
            ),
            inline=True,
        )
        
        # Confirmation Metrics
        embed.add_field(
            name="⏱️ Confirmation Metrics",
            value=(
                f"**Pending Confirmations**: {snapshot.pending_confirmations}\n"
                f"**Avg Confirmation Time**: {snapshot.average_confirmation_time}s"
            ),
            inline=True,
        )
        
        # Queue Status
        embed.add_field(
            name="📋 Queue Status",
            value=(
                f"**Queue Size**: {snapshot.queue_size}\n"
                f"**Processed Events**: {snapshot.processed_count}\n"
                f"**Dead Letter Queue**: {snapshot.dlq_count}"
            ),
            inline=True,
        )
        
        # Latest Transactions
        if snapshot.latest_transactions:
            latest_text = ""
            for tx in snapshot.latest_transactions:
                status_emoji = {
                    "completed": "✅",
                    "confirmed": "✔️",
                    "pending": "⏳",
                    "failed": "❌",
                }.get(tx["status"], "❓")
                
                latest_text += (
                    f"{status_emoji} **{tx['trade_id'][:8]}...** "
                    f"({tx['status']}, {tx['confirmations']} confs)\n"
                )
            
            embed.add_field(
                name="🔄 Latest Transactions",
                value=latest_text.strip(),
                inline=False,
            )
        
        # Footer
        embed.set_footer(text="Webhook Monitoring System")
        
        return embed

    @commands.command(name="metrics")
    async def metrics_command(self, ctx: commands.Context) -> None:
        """
        Display webhook monitoring dashboard.

        Usage:
            +metrics
        """
        try:
            # Collect current metrics
            snapshot = self.metrics.collect_metrics()
            
            # Save snapshot
            self.metrics.save_snapshot(snapshot)
            
            # Create and send embed
            embed = self._create_metrics_embed(snapshot)
            await ctx.send(embed=embed)
            
            logger.info(f"Metrics dashboard displayed by {ctx.author}")
            
        except Exception as e:
            logger.error(f"Error displaying metrics: {e}")
            await ctx.send(f"❌ Error displaying metrics: {str(e)}")

    @commands.command(name="health")
    async def health_command(self, ctx: commands.Context) -> None:
        """
        Display webhook health status.

        Usage:
            +health
        """
        try:
            snapshot = self.metrics.collect_metrics()
            
            # Create simple health embed
            color_map = {
                HealthStatus.HEALTHY.value: discord.Color.green(),
                HealthStatus.DEGRADED.value: discord.Color.orange(),
                HealthStatus.UNHEALTHY.value: discord.Color.red(),
            }
            color = color_map.get(snapshot.health_status, discord.Color.blue())
            
            health_emoji = {
                HealthStatus.HEALTHY.value: "✅",
                HealthStatus.DEGRADED.value: "⚠️",
                HealthStatus.UNHEALTHY.value: "❌",
            }
            
            embed = discord.Embed(
                title="🏥 Webhook Health Status",
                description=(
                    f"{health_emoji.get(snapshot.health_status, '❓')} "
                    f"**{snapshot.health_status.upper()}**"
                ),
                color=color,
            )
            
            embed.add_field(
                name="Success Rate",
                value=f"{snapshot.success_rate}%",
                inline=True,
            )
            embed.add_field(
                name="Failed Events (DLQ)",
                value=str(snapshot.dlq_count),
                inline=True,
            )
            embed.add_field(
                name="Queue Size",
                value=str(snapshot.queue_size),
                inline=True,
            )
            
            await ctx.send(embed=embed)
            logger.info(f"Health status displayed by {ctx.author}")
            
        except Exception as e:
            logger.error(f"Error displaying health status: {e}")
            await ctx.send(f"❌ Error displaying health status: {str(e)}")

    @commands.command(name="transactions")
    async def transactions_command(self, ctx: commands.Context) -> None:
        """
        Display latest transactions.

        Usage:
            +transactions
        """
        try:
            snapshot = self.metrics.collect_metrics()
            
            embed = discord.Embed(
                title="🔄 Latest Transactions",
                color=discord.Color.blue(),
            )
            
            if snapshot.latest_transactions:
                for tx in snapshot.latest_transactions:
                    status_emoji = {
                        "completed": "✅",
                        "confirmed": "✔️",
                        "pending": "⏳",
                        "failed": "❌",
                    }.get(tx["status"], "❓")
                    
                    embed.add_field(
                        name=f"{status_emoji} {tx['trade_id']}",
                        value=(
                            f"**Status**: {tx['status']}\n"
                            f"**Confirmations**: {tx['confirmations']}\n"
                            f"**Created**: {tx['created_at']}"
                        ),
                        inline=False,
                    )
            else:
                embed.description = "No transactions found"
            
            await ctx.send(embed=embed)
            logger.info(f"Transactions displayed by {ctx.author}")
            
        except Exception as e:
            logger.error(f"Error displaying transactions: {e}")
            await ctx.send(f"❌ Error displaying transactions: {str(e)}")


def setup_monitoring(bot: commands.Bot, metrics_collector: MetricsCollector) -> None:
    """
    Setup monitoring cog with the bot.

    Args:
        bot: Discord bot instance
        metrics_collector: MetricsCollector instance
    """
    cog = MonitoringCog(bot, metrics_collector)
    bot.add_cog(cog)
    logger.info("Monitoring cog loaded")


# Singleton instance
_metrics_instance: Optional[MetricsCollector] = None


def get_metrics_collector(
    bot_data_path: str = "bot_data.json",
    dlq_path: str = "dead_letter_queue.json",
    metrics_path: str = "metrics.json",
) -> MetricsCollector:
    """
    Get or create the metrics collector singleton.

    Args:
        bot_data_path: Path to bot_data.json file
        dlq_path: Path to dead letter queue file
        metrics_path: Path to metrics.json file

    Returns:
        MetricsCollector instance
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = MetricsCollector(
            bot_data_path=bot_data_path,
            dlq_path=dlq_path,
            metrics_path=metrics_path,
        )
    return _metrics_instance

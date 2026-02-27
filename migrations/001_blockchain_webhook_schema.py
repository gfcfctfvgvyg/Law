"""
Migration 001: Blockchain Webhook Schema

This migration creates the foundational schema for blockchain wallet management,
webhook event tracking, and webhook metrics monitoring. These tables support
the blockchain monitoring and webhook processing infrastructure.

Tables Created:
  - blockchain_wallets: Stores encrypted wallet addresses and keys for different networks
  - webhook_events: Tracks incoming webhook events from blockchain monitors
  - webhook_metrics: Aggregates webhook performance metrics by network

Design Rationale:
  - blockchain_wallets: Encrypted storage with network isolation for security
  - webhook_events: Event-sourced design for audit trail and replay capability
  - webhook_metrics: Denormalized metrics for fast dashboard queries
"""

from datetime import datetime
from typing import Optional, Dict, Any


class Migration:
    """
    Migration class for blockchain webhook schema.
    Implements forward and rollback operations for database schema changes.
    """

    version = "001"
    description = "Create blockchain webhook schema"

    @staticmethod
    def up(db_connection) -> None:
        """
        Apply the migration: create all required tables.
        
        Args:
            db_connection: Database connection object with execute() method
        """
        cursor = db_connection.cursor()

        try:
            # Create blockchain_wallets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blockchain_wallets (
                    id SERIAL PRIMARY KEY,
                    trade_id VARCHAR(255) NOT NULL UNIQUE,
                    network VARCHAR(50) NOT NULL,
                    address VARCHAR(255) NOT NULL,
                    encrypted_key TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT valid_network CHECK (network IN ('BTC', 'ETH', 'SOL', 'LTC')),
                    CONSTRAINT valid_address_length CHECK (LENGTH(address) > 0)
                );
            """)
            print("✓ Created blockchain_wallets table")

            # Create index on trade_id for fast lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_blockchain_wallets_trade_id
                ON blockchain_wallets(trade_id);
            """)
            print("✓ Created index on blockchain_wallets.trade_id")

            # Create index on network for filtering by blockchain
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_blockchain_wallets_network
                ON blockchain_wallets(network);
            """)
            print("✓ Created index on blockchain_wallets.network")

            # Create webhook_events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS webhook_events (
                    id SERIAL PRIMARY KEY,
                    event_id VARCHAR(255) NOT NULL UNIQUE,
                    network VARCHAR(50) NOT NULL,
                    tx_hash VARCHAR(255) NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    confirmations INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    CONSTRAINT valid_network_webhook CHECK (network IN ('BTC', 'ETH', 'SOL', 'LTC')),
                    CONSTRAINT valid_status CHECK (status IN ('pending', 'confirmed', 'failed', 'cancelled')),
                    CONSTRAINT valid_confirmations CHECK (confirmations >= 0),
                    CONSTRAINT processed_after_created CHECK (processed_at IS NULL OR processed_at >= created_at)
                );
            """)
            print("✓ Created webhook_events table")

            # Create index on event_id for deduplication
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_webhook_events_event_id
                ON webhook_events(event_id);
            """)
            print("✓ Created index on webhook_events.event_id")

            # Create index on tx_hash for transaction lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_webhook_events_tx_hash
                ON webhook_events(tx_hash);
            """)
            print("✓ Created index on webhook_events.tx_hash")

            # Create index on status for filtering unprocessed events
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_webhook_events_status
                ON webhook_events(status);
            """)
            print("✓ Created index on webhook_events.status")

            # Create index on created_at for time-range queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_webhook_events_created_at
                ON webhook_events(created_at);
            """)
            print("✓ Created index on webhook_events.created_at")

            # Create webhook_metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS webhook_metrics (
                    id SERIAL PRIMARY KEY,
                    network VARCHAR(50) NOT NULL UNIQUE,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    last_event_at TIMESTAMP,
                    CONSTRAINT valid_network_metrics CHECK (network IN ('BTC', 'ETH', 'SOL', 'LTC')),
                    CONSTRAINT valid_success_count CHECK (success_count >= 0),
                    CONSTRAINT valid_failure_count CHECK (failure_count >= 0)
                );
            """)
            print("✓ Created webhook_metrics table")

            # Create index on network for fast metric lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_webhook_metrics_network
                ON webhook_metrics(network);
            """)
            print("✓ Created index on webhook_metrics.network")

            # Initialize metrics for all supported networks
            networks = ['BTC', 'ETH', 'SOL', 'LTC']
            for network in networks:
                cursor.execute("""
                    INSERT INTO webhook_metrics (network, success_count, failure_count)
                    VALUES (%s, 0, 0)
                    ON CONFLICT (network) DO NOTHING;
                """, (network,))
            print("✓ Initialized webhook_metrics for all networks")

            db_connection.commit()
            print("\n✅ Migration 001 applied successfully")

        except Exception as e:
            db_connection.rollback()
            print(f"❌ Migration 001 failed: {str(e)}")
            raise
        finally:
            cursor.close()

    @staticmethod
    def down(db_connection) -> None:
        """
        Rollback the migration: drop all created tables.
        
        Args:
            db_connection: Database connection object with execute() method
        """
        cursor = db_connection.cursor()

        try:
            # Drop webhook_metrics table
            cursor.execute("""
                DROP TABLE IF EXISTS webhook_metrics CASCADE;
            """)
            print("✓ Dropped webhook_metrics table")

            # Drop webhook_events table
            cursor.execute("""
                DROP TABLE IF EXISTS webhook_events CASCADE;
            """)
            print("✓ Dropped webhook_events table")

            # Drop blockchain_wallets table
            cursor.execute("""
                DROP TABLE IF EXISTS blockchain_wallets CASCADE;
            """)
            print("✓ Dropped blockchain_wallets table")

            db_connection.commit()
            print("\n✅ Migration 001 rolled back successfully")

        except Exception as e:
            db_connection.rollback()
            print(f"❌ Rollback of Migration 001 failed: {str(e)}")
            raise
        finally:
            cursor.close()


class MigrationRunner:
    """
    Utility class to run migrations programmatically.
    """

    @staticmethod
    def run_migration(db_connection, direction: str = "up") -> bool:
        """
        Execute the migration in the specified direction.
        
        Args:
            db_connection: Database connection object
            direction: "up" to apply, "down" to rollback
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if direction.lower() == "up":
                Migration.up(db_connection)
                return True
            elif direction.lower() == "down":
                Migration.down(db_connection)
                return True
            else:
                print(f"❌ Invalid direction: {direction}. Use 'up' or 'down'.")
                return False
        except Exception as e:
            print(f"❌ Migration execution failed: {str(e)}")
            return False


if __name__ == "__main__":
    """
    Example usage for manual migration execution.
    
    Usage:
        python migrations/001_blockchain_webhook_schema.py
    """
    import sys
    import os

    # This would be replaced with actual database connection in production
    print("Migration 001: Blockchain Webhook Schema")
    print("="*50)
    print("\nSchema Overview:")
    print("\n1. blockchain_wallets")
    print("   - id: Primary key (auto-increment)")
    print("   - trade_id: Unique identifier for the trade")
    print("   - network: Blockchain network (BTC, ETH, SOL, LTC)")
    print("   - address: Wallet address on the network")
    print("   - encrypted_key: Encrypted private key material")
    print("   - created_at: Timestamp of wallet creation")
    print("\n2. webhook_events")
    print("   - id: Primary key (auto-increment)")
    print("   - event_id: Unique webhook event identifier")
    print("   - network: Blockchain network (BTC, ETH, SOL, LTC)")
    print("   - tx_hash: Transaction hash on the blockchain")
    print("   - status: Event status (pending, confirmed, failed, cancelled)")
    print("   - confirmations: Number of blockchain confirmations")
    print("   - created_at: Timestamp of event receipt")
    print("   - processed_at: Timestamp of event processing")
    print("\n3. webhook_metrics")
    print("   - id: Primary key (auto-increment)")
    print("   - network: Blockchain network (BTC, ETH, SOL, LTC)")
    print("   - success_count: Total successful webhook events")
    print("   - failure_count: Total failed webhook events")
    print("   - last_event_at: Timestamp of most recent event")
    print("\n" + "="*50)
    print("\nTo apply this migration, use your migration runner:")
    print("  runner.run_migration(db_connection, 'up')")
    print("\nTo rollback this migration:")
    print("  runner.run_migration(db_connection, 'down')")

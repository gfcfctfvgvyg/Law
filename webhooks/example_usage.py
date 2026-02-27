"""
Example usage of the EventProcessor for handling blockchain transaction events.

This demonstrates:
- Creating and enqueuing events
- Starting the processor
- Monitoring trade status
- Handling dead letter queue events
"""

import asyncio
from datetime import datetime
from webhooks.event_processor import Event, get_event_processor


async def example_process_transaction_events():
    """
    Example: Process blockchain transaction events with confirmation counting.
    """
    # Initialize the event processor with a 3-confirmation threshold
    processor = get_event_processor(
        bot_data_path="bot_data.json",
        confirmation_threshold=3,
        max_retries=5,
        dlq_path="dead_letter_queue.json",
    )

    # Start the processor as a background task
    processor_task = await processor.start()

    try:
        # Simulate receiving transaction events from blockchain webhook
        trade_id = "trade_12345"
        tx_hash = "0xabc123def456..."

        # Event 1: Initial transaction (1 confirmation)
        event1 = Event(
            event_id="evt_001",
            trade_id=trade_id,
            tx_hash=tx_hash,
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={"block_number": 18000000, "gas_used": 21000},
        )
        await processor.enqueue_event(event1)

        # Wait a bit for processing
        await asyncio.sleep(0.5)

        # Check trade status
        trade = processor.get_trade_status(trade_id)
        print(f"Trade after 1st event: {trade}")
        # Output: status='pending', confirmations=1

        # Event 2: Second confirmation
        event2 = Event(
            event_id="evt_002",
            trade_id=trade_id,
            tx_hash=tx_hash,
            confirmation_count=2,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={"block_number": 18000001},
        )
        await processor.enqueue_event(event2)
        await asyncio.sleep(0.5)

        trade = processor.get_trade_status(trade_id)
        print(f"Trade after 2nd event: {trade}")
        # Output: status='pending', confirmations=2

        # Event 3: Third confirmation (threshold reached)
        event3 = Event(
            event_id="evt_003",
            trade_id=trade_id,
            tx_hash=tx_hash,
            confirmation_count=3,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={"block_number": 18000002},
        )
        await processor.enqueue_event(event3)
        await asyncio.sleep(0.5)

        trade = processor.get_trade_status(trade_id)
        print(f"Trade after 3rd event (confirmed): {trade}")
        # Output: status='confirmed', confirmations=3, confirmed_at=<timestamp>

        # Event 4: Final confirmation event
        event4 = Event(
            event_id="evt_004",
            trade_id=trade_id,
            tx_hash=tx_hash,
            confirmation_count=4,
            timestamp=datetime.utcnow().isoformat(),
            event_type="final_confirmation",
            data={"block_number": 18000003},
        )
        await processor.enqueue_event(event4)
        await asyncio.sleep(0.5)

        trade = processor.get_trade_status(trade_id)
        print(f"Trade after final event (completed): {trade}")
        # Output: status='completed', confirmations=4, completed_at=<timestamp>

        # Print queue stats
        print(f"\nQueue size: {processor.get_queue_size()}")
        print(f"Processed events: {processor.get_processed_count()}")

    finally:
        # Stop the processor
        processor.stop()
        await processor_task


async def example_handle_failed_events():
    """
    Example: Handle failed events and retry from dead letter queue.
    """
    processor = get_event_processor()
    processor_task = await processor.start()

    try:
        # Create an event that will fail (simulated by invalid data)
        event = Event(
            event_id="evt_fail_001",
            trade_id="trade_fail_001",
            tx_hash="0xfail...",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={"error": "simulated failure"},
        )

        await processor.enqueue_event(event)
        await asyncio.sleep(1.0)

        # Check dead letter queue
        dlq_events = processor.get_dlq_events()
        print(f"Dead letter queue events: {len(dlq_events)}")

        if dlq_events:
            # Retry the first failed event
            first_event = dlq_events[0]
            print(f"Retrying event: {first_event['event_id']}")
            processor.retry_dlq_event(first_event["event_id"])

            await asyncio.sleep(0.5)

            # Check if it was processed
            trade = processor.get_trade_status(first_event["trade_id"])
            print(f"Trade status after retry: {trade}")

    finally:
        processor.stop()
        await processor_task


async def example_multiple_trades():
    """
    Example: Process events for multiple trades concurrently.
    """
    processor = get_event_processor()
    processor_task = await processor.start()

    try:
        # Create events for 3 different trades
        trades = ["trade_A", "trade_B", "trade_C"]

        for trade_id in trades:
            for i in range(1, 4):
                event = Event(
                    event_id=f"{trade_id}_evt_{i}",
                    trade_id=trade_id,
                    tx_hash=f"0x{trade_id}_{i}",
                    confirmation_count=i,
                    timestamp=datetime.utcnow().isoformat(),
                    event_type="confirmation",
                    data={"sequence": i},
                )
                await processor.enqueue_event(event)

        # Wait for all events to process
        await asyncio.sleep(1.0)

        # Check all trades
        for trade_id in trades:
            trade = processor.get_trade_status(trade_id)
            print(f"{trade_id}: status={trade['status']}, confirmations={trade['confirmations']}")

    finally:
        processor.stop()
        await processor_task


if __name__ == "__main__":
    print("=== Example 1: Process Transaction Events ===")
    asyncio.run(example_process_transaction_events())

    print("\n=== Example 2: Handle Failed Events ===")
    asyncio.run(example_handle_failed_events())

    print("\n=== Example 3: Multiple Trades ===")
    asyncio.run(example_multiple_trades())

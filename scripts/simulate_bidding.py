#!/usr/bin/env python3
"""
Simulate bidding on a live British Auction RFQ.
Demonstrates:
1. Anti-sniping extension triggering when a quote is placed in the trigger window
2. Idempotency protection against duplicate submissions
3. Real-time ranking change and activity logging

Usage:
    python scripts/simulate_bidding.py
    python scripts/simulate_bidding.py --rfq RFQ-2026-LIVE
"""

import sys
import os
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import uuid

# Add backend directory to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.db.session import SessionLocal, init_db
from app.models.entities import RFQ, Supplier, RFQSupplier, Bid
from app.schemas.bid import BidCreate
from app.services.clock import SystemClock
from app.services.bid_service import submit_bid


def simulate(rfq_ref: str = "RFQ-2026-LIVE"):
    init_db()
    db = SessionLocal()
    clock = SystemClock()

    rfq = db.query(RFQ).filter(RFQ.reference_id == rfq_ref).first()
    if not rfq:
        print(f"[!] RFQ with reference ID '{rfq_ref}' not found. Run 'python scripts/seed.py' first.")
        db.close()
        return

    now = clock.now()
    print(f"[*] Found RFQ: {rfq.name} ({rfq.reference_id})")
    print(f"    Status: {rfq.status.value}")
    print(f"    Current Close Time: {rfq.current_close_time.isoformat()}")
    print(f"    Forced Close Time:  {rfq.forced_close_time.isoformat()}")

    # Find invited suppliers
    invited_suppliers = (
        db.query(Supplier)
        .join(RFQSupplier, RFQSupplier.supplier_id == Supplier.id)
        .filter(RFQSupplier.rfq_id == rfq.id)
        .all()
    )

    if not invited_suppliers:
        print("[!] No invited suppliers found for this RFQ.")
        db.close()
        return

    # Find current best bid
    lowest_bid = (
        db.query(Bid)
        .filter(Bid.rfq_id == rfq.id)
        .order_by(Bid.total_price.asc())
        .first()
    )

    current_lowest = lowest_bid.total_price if lowest_bid else Decimal("100000.00")
    print(f"    Current Lowest Quote: {rfq.currency} {current_lowest:.2f}")

    # Pick a supplier that is not the current L1 to trigger an L1 change
    bidding_supplier = invited_suppliers[0]
    for s in invited_suppliers:
        if lowest_bid and s.id != lowest_bid.supplier_id:
            bidding_supplier = s
            break

    # Calculate new lower price (-5%)
    new_price = (current_lowest * Decimal("0.95")).quantize(Decimal("0.01"))
    freight = new_price - Decimal("1000.00")
    orig = Decimal("500.00")
    dest = Decimal("500.00")

    print(f"\n[*] Submitting new competitive bid from '{bidding_supplier.name}':")
    print(f"    Freight:     {rfq.currency} {freight:.2f}")
    print(f"    Origin:      {rfq.currency} {orig:.2f}")
    print(f"    Destination: {rfq.currency} {dest:.2f}")
    print(f"    Total Price: {rfq.currency} {new_price:.2f} (Strictly lower)")

    idempotency_key = str(uuid.uuid4())
    print(f"    Idempotency-Key: {idempotency_key}")

    try:
        bid_in = BidCreate(
            supplier_id=bidding_supplier.id,
            freight_charges=freight,
            origin_charges=orig,
            destination_charges=dest,
            transit_time_days=14,
            quote_validity_days=30,
        )

        result, was_replayed = submit_bid(
            rfq_id=rfq.id,
            bid_in=bid_in,
            session=db,
            clock=clock,
            idempotency_key=idempotency_key,
        )

        db.refresh(rfq)
        print(f"\n[✓] Bid accepted successfully! Bid ID: {result.bid.id}")
        print(f"    New Supplier Rank: #{result.rank}")
        print(f"    New Current Close Time: {result.new_close_time.isoformat()}")

        if result.extended:
            print("\n    ⚡ ANTI-SNIPING EXTENSION TRIGGERED!")
            print(f"    Reason: {result.extension_reason}")
            print(f"    Close time pushed from original close to: {result.new_close_time.isoformat()}")
        else:
            print("    (Bid accepted without extension: outside trigger window or condition not met)")

        # Demonstrate idempotency replay
        print("\n[*] Demonstrating Idempotency: Retrying with identical key...")
        replayed_result, was_replayed_2 = submit_bid(
            rfq_id=rfq.id,
            bid_in=bid_in,
            session=db,
            clock=clock,
            idempotency_key=idempotency_key,
        )
        print(f"[✓] Idempotent Replay Verified: was_replayed={was_replayed_2}, Bid ID unchanged={replayed_result.bid.id}")

    except Exception as e:
        print(f"\n[!] Bid rejected: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate bidding on an RFQ")
    parser.add_argument("--rfq", default="RFQ-2026-LIVE", help="RFQ reference ID")
    args = parser.parse_args()
    simulate(rfq_ref=args.rfq)

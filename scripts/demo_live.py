#!/usr/bin/env python3
"""
Live demonstration script for NeoBidding — Enterprise Reverse Auction Platform.
Validates live integration with Neon PostgreSQL and Upstash Redis.
"""

import sys
import os
from pathlib import Path
from decimal import Decimal

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.models.entities import RFQ, Supplier, BritishAuctionConfig, Bid, AuctionEvent
from app.models.enums import AuctionStatus
from app.core.celery_app import celery_app
from app.schemas.bid import BidCreate
from app.services.bid_service import submit_bid
from app.services.clock import SystemClock


def run_demo():
    print("\n" + "=" * 70)
    print(" LIVE DEMONSTRATION: NEOBIDDING ENTERPRISE REVERSE AUCTION")
    print(" Cloud Infrastructure: Neon PostgreSQL + Upstash Redis (Celery)")
    print("=" * 70)

    db = SessionLocal()
    clock = SystemClock()
    now = clock.now()

    try:
        # 1. Query Suppliers in Neon PostgreSQL
        suppliers = db.query(Supplier).all()
        print(f"\n[1] SUPPLIERS IN NEON POSTGRESQL ({len(suppliers)} carriers registered):")
        for s in suppliers:
            print(f"    - ID: {s.id} | Carrier: {s.name}")

        # 2. Query RFQs in Neon PostgreSQL
        rfqs = db.query(RFQ).all()
        print(f"\n[2] AUCTIONS IN NEON POSTGRESQL ({len(rfqs)} auctions seeded):")
        live_auction = None
        for rfq in rfqs:
            cfg = db.query(BritishAuctionConfig).filter_by(rfq_id=rfq.id).first()
            cfg_str = f"Trigger Window: {cfg.trigger_window_minutes}m, Ext: +{cfg.extension_minutes}m, Trigger: {cfg.extension_trigger.value}" if cfg else "Standard"
            print(f"    - [{rfq.status.value:^12}] Ref: {rfq.reference_id:<18} | Name: {rfq.name:<28} | Config: {cfg_str}")
            if rfq.reference_id == "RFQ-2026-ACTIVE":
                live_auction = rfq

        # 3. Test Celery & Upstash Broker
        print(f"\n[3] CELERY WORKER & UPSTASH BROKER READINESS:")
        print(f"    - Broker Endpoint : {celery_app.conf.broker_url.split('@')[-1]}")
        print(f"    - SSL / TLS       : broker_use_ssl={celery_app.conf.broker_use_ssl}")
        print(f"    - Celery Beat     : finalize_due_auctions scheduled every {celery_app.conf.beat_schedule['finalize_due_auctions_every_5s']['schedule']}s")
        with celery_app.connection_for_read() as conn:
            conn.ensure_connection(max_retries=2)
            print(f"    - Broker Link     : Active & Verified connected to Upstash!")

        # 4. Live Bidding Demonstration
        if live_auction and suppliers:
            print(f"\n[4] LIVE BIDDING EXECUTION ON '{live_auction.reference_id}':")
            carrier = suppliers[0]

            # Check existing lowest bid
            existing_bids = db.query(Bid).filter_by(rfq_id=live_auction.id).order_by(Bid.total_price.asc()).all()
            current_lowest = existing_bids[0].total_price if existing_bids else Decimal("3000.00")
            new_freight = current_lowest - Decimal("200.00")
            new_origin = Decimal("50.00")
            new_dest = Decimal("50.00")

            total_new = new_freight + new_origin + new_dest

            print(f"    - Current lowest bid: {current_lowest} {live_auction.currency}")
            print(f"    - Submitting competitive quote: Total {total_new} {live_auction.currency} from '{carrier.name}'...")

            bid_in = BidCreate(
                supplier_id=carrier.id,
                freight_charges=new_freight,
                origin_charges=new_origin,
                destination_charges=new_dest,
                transit_time_days=14,
                quote_validity_days=30,
            )
            submission_result, is_replay = submit_bid(
                rfq_id=live_auction.id,
                bid_in=bid_in,
                session=db,
                clock=clock,
                idempotency_key=f"demo_bid_{int(now.timestamp())}",
            )
            db.commit()

            print(f"    [+] BID ACCEPTED AND PERSISTED TO NEON POSTGRESQL!")
            print(f"        - Bid ID          : {submission_result.bid.id}")
            print(f"        - Total Price     : {submission_result.bid.total_price} {live_auction.currency}")
            print(f"        - Supplier Rank   : #{submission_result.rank} ({'Leading / L1' if submission_result.rank == 1 else 'Competitive'})")
            print(f"        - Extended?       : {submission_result.extended} (Reason: {submission_result.extension_reason or 'None (outside trigger window)'})")
            print(f"        - Current Close   : {submission_result.new_close_time.isoformat()}")

            # 5. Audit Events
            events = db.query(AuctionEvent).filter_by(rfq_id=live_auction.id).order_by(AuctionEvent.occurred_at.desc()).limit(3).all()
            print(f"\n[5] IMMUTABLE AUDIT TRAIL RECORDED IN NEON:")
            for ev in events:
                print(f"    - [{ev.occurred_at.strftime('%H:%M:%S')}] Event: {ev.event_type.value:<20} | Reason: {ev.reason or 'N/A'}")

        print("\n" + "=" * 70)
        print(" DEMONSTRATION COMPLETE: SYSTEM IS FULLY OPERATIONAL")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    run_demo()

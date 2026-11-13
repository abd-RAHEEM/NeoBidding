#!/usr/bin/env python3
"""
Seed script for British Auction RFQ System.
Populates suppliers and realistic sample auctions across all lifecycle states:
1. SCHEDULED
2. ACTIVE (regular bidding, outside trigger window)
3. TRIGGER_WINDOW (inside last X minutes, ready for anti-sniping extension test)
4. CLOSED (concluded normally with L1 winner)
5. FORCE_CLOSED (hit the hard forced close cap)

Usage:
    python scripts/seed.py
    python scripts/seed.py --live   # creates an interactive auction closing in 4m
"""

import sys
import argparse
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import uuid
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.db.session import SessionLocal, init_db
from app.models.entities import Supplier, RFQ, RFQSupplier, BritishAuctionConfig, Bid, AuctionEvent
from app.models.enums import AuctionType, ExtensionTrigger, AuctionStatus, AuctionEventType
from app.services.clock import SystemClock


def ensure_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def seed_data(live_demo: bool = False):
    init_db()
    db = SessionLocal()
    clock = SystemClock()

    now = clock.now()
    print(f"[*] Seeding data relative to current server time: {now.isoformat()}")

    # 1. Seed Realistic Freight Carriers
    carriers_data = [
        "Maersk Line Logistics",
        "DHL Global Forwarding",
        "Blue Dart Express",
        "DB Schenker India",
        "FedEx Freight Logistics",
    ]

    suppliers = []
    for name in carriers_data:
        supplier = db.query(Supplier).filter(Supplier.name == name).first()
        if not supplier:
            supplier = Supplier(
                id=uuid.uuid4(),
                name=name,
                created_at=now,
            )
            db.add(supplier)
            db.flush()
        suppliers.append(supplier)

    db.commit()
    print(f"[+] Seeded {len(suppliers)} carriers.")

    # 2. RFQ 1: SCHEDULED (Opens in 30 minutes)
    rfq_sched = db.query(RFQ).filter(RFQ.reference_id == "RFQ-2026-SCHED").first()
    if not rfq_sched:
        rfq_sched = RFQ(
            id=uuid.uuid4(),
            reference_id="RFQ-2026-SCHED",
            name="Nhava Sheva to Frankfurt Air Freight",
            currency="EUR",
            pickup_date=now.date() + timedelta(days=7),
            bid_start_time=now + timedelta(minutes=30),
            original_close_time=now + timedelta(minutes=90),
            current_close_time=now + timedelta(minutes=90),
            forced_close_time=now + timedelta(minutes=150),
            auction_type=AuctionType.BRITISH,
            status=AuctionStatus.SCHEDULED,
            created_at=now - timedelta(hours=2),
        )
        db.add(rfq_sched)
        db.flush()

        db.add(BritishAuctionConfig(
            rfq_id=rfq_sched.id,
            trigger_window_minutes=10,
            extension_minutes=10,
            extension_trigger=ExtensionTrigger.L1_CHANGE_IN_LAST_X,
        ))

        for s in suppliers[:4]:
            db.add(RFQSupplier(rfq_id=rfq_sched.id, supplier_id=s.id))

        db.add(AuctionEvent(
            id=uuid.uuid4(),
            rfq_id=rfq_sched.id,
            event_type=AuctionEventType.AUCTION_CREATED,
            occurred_at=now - timedelta(hours=2),
            created_at=now - timedelta(hours=2),
            payload={"auction_type": "BRITISH", "reference_id": "RFQ-2026-SCHED"},
        ))
        db.commit()
        print(f"[+] Created SCHEDULED auction: {rfq_sched.reference_id}")

    # 3. RFQ 2: ACTIVE (Regular bidding, 45 minutes remaining)
    rfq_active = db.query(RFQ).filter(RFQ.reference_id == "RFQ-2026-ACTIVE").first()
    if not rfq_active:
        rfq_active = RFQ(
            id=uuid.uuid4(),
            reference_id="RFQ-2026-ACTIVE",
            name="Delhi to Singapore FCL Sea Freight",
            currency="USD",
            pickup_date=now.date() + timedelta(days=5),
            bid_start_time=now - timedelta(minutes=30),
            original_close_time=now + timedelta(minutes=45),
            current_close_time=now + timedelta(minutes=45),
            forced_close_time=now + timedelta(minutes=105),
            auction_type=AuctionType.BRITISH,
            status=AuctionStatus.ACTIVE,
            created_at=now - timedelta(hours=1),
        )
        db.add(rfq_active)
        db.flush()

        db.add(BritishAuctionConfig(
            rfq_id=rfq_active.id,
            trigger_window_minutes=5,
            extension_minutes=5,
            extension_trigger=ExtensionTrigger.L1_CHANGE_IN_LAST_X,
        ))

        for s in suppliers:
            db.add(RFQSupplier(rfq_id=rfq_active.id, supplier_id=s.id))

        db.add(AuctionEvent(
            id=uuid.uuid4(),
            rfq_id=rfq_active.id,
            event_type=AuctionEventType.AUCTION_CREATED,
            occurred_at=now - timedelta(hours=1),
            created_at=now - timedelta(hours=1),
            payload={"auction_type": "BRITISH"},
        ))
        db.add(AuctionEvent(
            id=uuid.uuid4(),
            rfq_id=rfq_active.id,
            event_type=AuctionEventType.AUCTION_STARTED,
            occurred_at=now - timedelta(minutes=30),
            created_at=now - timedelta(minutes=30),
            payload={},
        ))
        db.commit()

        # Place initial bids
        bids_to_place = [
            (suppliers[0], Decimal("2800.00"), Decimal("200.00"), Decimal("200.00"), 12, 14, now - timedelta(minutes=25)),
            (suppliers[1], Decimal("2700.00"), Decimal("150.00"), Decimal("150.00"), 10, 14, now - timedelta(minutes=18)),
            (suppliers[2], Decimal("2500.00"), Decimal("200.00"), Decimal("150.00"), 11, 21, now - timedelta(minutes=10)),
        ]
        for sup, freight, orig, dest, transit, val, sub_time in bids_to_place:
            tot = freight + orig + dest
            bid = Bid(
                id=uuid.uuid4(),
                rfq_id=rfq_active.id,
                supplier_id=sup.id,
                carrier_name=sup.name,
                freight_charges=freight,
                origin_charges=orig,
                destination_charges=dest,
                total_price=tot,
                transit_time_days=transit,
                quote_validity_days=val,
                submitted_at=sub_time,
            )
            db.add(bid)
            db.add(AuctionEvent(
                id=uuid.uuid4(),
                rfq_id=rfq_active.id,
                event_type=AuctionEventType.BID_PLACED,
                occurred_at=sub_time,
                created_at=sub_time,
                payload={
                    "supplier_id": str(sup.id),
                    "carrier_name": sup.name,
                    "total_price": str(tot),
                    "currency": "USD",
                },
            ))
        db.commit()
        print(f"[+] Created ACTIVE auction: {rfq_active.reference_id}")

    # 4. RFQ 3: TRIGGER_WINDOW / LIVE DEMO
    rfq_window = db.query(RFQ).filter(RFQ.reference_id == "RFQ-2026-LIVE").first()
    if not rfq_window:
        close_delta = timedelta(minutes=4 if live_demo else 3)
        rfq_window = RFQ(
            id=uuid.uuid4(),
            reference_id="RFQ-2026-LIVE",
            name="★ LIVE DEMO: Chennai to Rotterdam Express",
            currency="INR",
            pickup_date=now.date() + timedelta(days=3),
            bid_start_time=now - timedelta(minutes=15),
            original_close_time=now + close_delta,
            current_close_time=now + close_delta,
            forced_close_time=now + timedelta(minutes=25),
            auction_type=AuctionType.BRITISH,
            status=AuctionStatus.ACTIVE,
            created_at=now - timedelta(minutes=20),
        )
        db.add(rfq_window)
        db.flush()

        db.add(BritishAuctionConfig(
            rfq_id=rfq_window.id,
            trigger_window_minutes=5,
            extension_minutes=5,
            extension_trigger=ExtensionTrigger.L1_CHANGE_IN_LAST_X,
        ))

        for s in suppliers:
            db.add(RFQSupplier(rfq_id=rfq_window.id, supplier_id=s.id))

        db.add(AuctionEvent(
            id=uuid.uuid4(),
            rfq_id=rfq_window.id,
            event_type=AuctionEventType.AUCTION_CREATED,
            occurred_at=now - timedelta(minutes=20),
            created_at=now - timedelta(minutes=20),
            payload={"auction_type": "BRITISH", "reference_id": "RFQ-2026-LIVE"},
        ))
        db.add(AuctionEvent(
            id=uuid.uuid4(),
            rfq_id=rfq_window.id,
            event_type=AuctionEventType.AUCTION_STARTED,
            occurred_at=now - timedelta(minutes=15),
            created_at=now - timedelta(minutes=15),
            payload={},
        ))
        db.commit()

        # Two initial bids
        bids_live = [
            (suppliers[0], Decimal("85000.00"), Decimal("5000.00"), Decimal("5000.00"), 18, 30, now - timedelta(minutes=12)),
            (suppliers[1], Decimal("80000.00"), Decimal("4000.00"), Decimal("4000.00"), 16, 30, now - timedelta(minutes=7)),
        ]
        for sup, freight, orig, dest, transit, val, sub_time in bids_live:
            tot = freight + orig + dest
            bid = Bid(
                id=uuid.uuid4(),
                rfq_id=rfq_window.id,
                supplier_id=sup.id,
                carrier_name=sup.name,
                freight_charges=freight,
                origin_charges=orig,
                destination_charges=dest,
                total_price=tot,
                transit_time_days=transit,
                quote_validity_days=val,
                submitted_at=sub_time,
            )
            db.add(bid)
            db.add(AuctionEvent(
                id=uuid.uuid4(),
                rfq_id=rfq_window.id,
                event_type=AuctionEventType.BID_PLACED,
                occurred_at=sub_time,
                created_at=sub_time,
                payload={
                    "supplier_id": str(sup.id),
                    "carrier_name": sup.name,
                    "total_price": str(tot),
                    "currency": "INR",
                },
            ))
        db.commit()
        print(f"[+] Created LIVE TRIGGER-WINDOW auction: {rfq_window.reference_id}")
        print(f"    --> Bidding closes in {(ensure_utc(rfq_window.current_close_time) - now).total_seconds() / 60:.1f} mins!")
        print(f"    --> Submitting a bid with total < 88,000 INR will extend close time by 5 minutes!")

    # 5. RFQ 4: CLOSED (Normal closure, 2 hours ago)
    rfq_closed = db.query(RFQ).filter(RFQ.reference_id == "RFQ-2026-CLOSED").first()
    if not rfq_closed:
        rfq_closed = RFQ(
            id=uuid.uuid4(),
            reference_id="RFQ-2026-CLOSED",
            name="Bengaluru to Dubai Jebel Ali Ocean Freight",
            currency="AED",
            pickup_date=now.date() + timedelta(days=2),
            bid_start_time=now - timedelta(hours=5),
            original_close_time=now - timedelta(hours=2),
            current_close_time=now - timedelta(hours=2),
            forced_close_time=now - timedelta(hours=1),
            auction_type=AuctionType.BRITISH,
            status=AuctionStatus.CLOSED,
            created_at=now - timedelta(hours=6),
        )
        db.add(rfq_closed)
        db.flush()

        db.add(BritishAuctionConfig(
            rfq_id=rfq_closed.id,
            trigger_window_minutes=5,
            extension_minutes=5,
            extension_trigger=ExtensionTrigger.L1_CHANGE_IN_LAST_X,
        ))

        for s in suppliers[:3]:
            db.add(RFQSupplier(rfq_id=rfq_closed.id, supplier_id=s.id))

        db.add(AuctionEvent(
            id=uuid.uuid4(),
            rfq_id=rfq_closed.id,
            event_type=AuctionEventType.AUCTION_CREATED,
            occurred_at=now - timedelta(hours=6),
            created_at=now - timedelta(hours=6),
            payload={"auction_type": "BRITISH"},
        ))
        db.add(AuctionEvent(
            id=uuid.uuid4(),
            rfq_id=rfq_closed.id,
            event_type=AuctionEventType.AUCTION_STARTED,
            occurred_at=now - timedelta(hours=5),
            created_at=now - timedelta(hours=5),
            payload={},
        ))
        db.add(AuctionEvent(
            id=uuid.uuid4(),
            rfq_id=rfq_closed.id,
            event_type=AuctionEventType.AUCTION_CLOSED,
            occurred_at=now - timedelta(hours=2),
            created_at=now - timedelta(hours=2),
            payload={"reason": "SCHEDULED_TIME_ELAPSED"},
        ))

        bids_closed = [
            (suppliers[0], Decimal("14000.00"), Decimal("1000.00"), Decimal("1000.00"), 8, 14, now - timedelta(hours=4)),
            (suppliers[1], Decimal("12500.00"), Decimal("800.00"), Decimal("700.00"), 7, 14, now - timedelta(hours=3)),
            (suppliers[2], Decimal("11000.00"), Decimal("600.00"), Decimal("500.00"), 6, 14, now - timedelta(hours=2, minutes=30)),
        ]
        for sup, freight, orig, dest, transit, val, sub_time in bids_closed:
            tot = freight + orig + dest
            bid = Bid(
                id=uuid.uuid4(),
                rfq_id=rfq_closed.id,
                supplier_id=sup.id,
                carrier_name=sup.name,
                freight_charges=freight,
                origin_charges=orig,
                destination_charges=dest,
                total_price=tot,
                transit_time_days=transit,
                quote_validity_days=val,
                submitted_at=sub_time,
            )
            db.add(bid)
            db.add(AuctionEvent(
                id=uuid.uuid4(),
                rfq_id=rfq_closed.id,
                event_type=AuctionEventType.BID_PLACED,
                occurred_at=sub_time,
                created_at=sub_time,
                payload={
                    "supplier_id": str(sup.id),
                    "carrier_name": sup.name,
                    "total_price": str(tot),
                    "currency": "AED",
                },
            ))
        db.commit()
        print(f"[+] Created CLOSED auction: {rfq_closed.reference_id}")

    # 6. RFQ 5: FORCE_CLOSED (Extended to cap, ended at forced close time)
    rfq_forced = db.query(RFQ).filter(RFQ.reference_id == "RFQ-2026-FORCE-CLOSED").first()
    if not rfq_forced:
        cap_time = now - timedelta(minutes=45)
        rfq_forced = RFQ(
            id=uuid.uuid4(),
            reference_id="RFQ-2026-FORCE-CLOSED",
            name="Hyderabad to London Heathrow Cold-Chain Pharma",
            currency="GBP",
            pickup_date=now.date() + timedelta(days=1),
            bid_start_time=now - timedelta(hours=3),
            original_close_time=now - timedelta(hours=2),
            current_close_time=cap_time,
            forced_close_time=cap_time,
            auction_type=AuctionType.BRITISH,
            status=AuctionStatus.FORCE_CLOSED,
            created_at=now - timedelta(hours=4),
        )
        db.add(rfq_forced)
        db.flush()

        db.add(BritishAuctionConfig(
            rfq_id=rfq_forced.id,
            trigger_window_minutes=5,
            extension_minutes=5,
            extension_trigger=ExtensionTrigger.L1_CHANGE_IN_LAST_X,
        ))

        for s in suppliers[:3]:
            db.add(RFQSupplier(rfq_id=rfq_forced.id, supplier_id=s.id))

        db.add(AuctionEvent(
            id=uuid.uuid4(),
            rfq_id=rfq_forced.id,
            event_type=AuctionEventType.AUCTION_CREATED,
            occurred_at=now - timedelta(hours=4),
            created_at=now - timedelta(hours=4),
            payload={"auction_type": "BRITISH"},
        ))
        db.add(AuctionEvent(
            id=uuid.uuid4(),
            rfq_id=rfq_forced.id,
            event_type=AuctionEventType.AUCTION_STARTED,
            occurred_at=now - timedelta(hours=3),
            created_at=now - timedelta(hours=3),
            payload={},
        ))
        db.add(AuctionEvent(
            id=uuid.uuid4(),
            rfq_id=rfq_forced.id,
            event_type=AuctionEventType.TIME_EXTENDED,
            occurred_at=now - timedelta(hours=2, minutes=2),
            created_at=now - timedelta(hours=2, minutes=2),
            payload={
                "trigger_type": "L1_CHANGE_IN_LAST_X",
                "new_close_time": (now - timedelta(hours=1, minutes=55)).isoformat(),
                "reason": "L1 changed inside trigger window",
            },
        ))
        db.add(AuctionEvent(
            id=uuid.uuid4(),
            rfq_id=rfq_forced.id,
            event_type=AuctionEventType.AUCTION_FORCE_CLOSED,
            occurred_at=cap_time,
            created_at=cap_time,
            payload={"reason": "FORCED_BID_CLOSE_TIME_REACHED"},
        ))
        db.commit()
        print(f"[+] Created FORCE_CLOSED auction: {rfq_forced.reference_id}")

    db.close()
    print("\n[✓] Seed complete! All auction lifecycle states are represented.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed British Auction RFQ Demo Data")
    parser.add_argument("--live", action="store_true", help="Ensure an auction is closing in ~4m for live anti-sniping demo")
    args = parser.parse_args()
    seed_data(live_demo=args.live)

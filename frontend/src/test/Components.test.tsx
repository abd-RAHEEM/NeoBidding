import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Countdown } from '../components/common/Countdown';
import { Badge } from '../components/common/Badge';
import { SupplierRankingTab } from '../components/rfq/SupplierRankingTab';
import { BidForm } from '../components/rfq/BidForm';
import type { SupplierRanking } from '../api/types';

describe('Frontend Component Tests', () => {
  describe('Countdown Component', () => {
    it('displays auction closed status when closed', () => {
      render(
        <Countdown
          targetTime={new Date().toISOString()}
          status="CLOSED"
        />
      );
      expect(screen.getByText('Auction Concluded')).toBeInTheDocument();
    });

    it('displays forced closed status when force closed', () => {
      render(
        <Countdown
          targetTime={new Date().toISOString()}
          status="FORCE_CLOSED"
        />
      );
      expect(screen.getByText('Forced Closed')).toBeInTheDocument();
    });

    it('displays trigger window indicator when inside trigger window', () => {
      const futureTime = new Date(Date.now() + 120 * 1000).toISOString();
      render(
        <Countdown
          targetTime={futureTime}
          status="ACTIVE"
          isInTriggerWindow={true}
        />
      );
      expect(screen.getByText('Trigger Window')).toBeInTheDocument();
    });
  });

  describe('Badge Component', () => {
    it('renders Active badge with pulsating dot', () => {
      render(<Badge status="ACTIVE" />);
      expect(screen.getByText('Active')).toBeInTheDocument();
    });

    it('renders L1 LEADER badge', () => {
      render(<Badge variant="l1" />);
      expect(screen.getByText('L1 LEADER')).toBeInTheDocument();
    });

    it('renders British mode badge', () => {
      render(<Badge mode="BRITISH" />);
      expect(screen.getByText('British')).toBeInTheDocument();
    });
  });

  describe('SupplierRankingTab Component', () => {
    const mockRankings: SupplierRanking[] = [
      {
        rank: 1,
        is_l1: true,
        supplier_id: 's1',
        supplier_name: 'Fast Logistics Ltd',
        supplier_code: 'FAST-01',
        has_bid: true,
        best_bid: {
          id: 'b1',
          total_price: '9500.00',
          freight_charges: '8000.00',
          origin_charges: '800.00',
          destination_charges: '700.00',
          transit_time_days: 3,
          quote_validity_days: 14,
          submitted_at: '2026-11-14T01:00:00Z',
        },
      },
      {
        rank: 2,
        is_l1: false,
        supplier_id: 's2',
        supplier_name: 'Global Cargo Express',
        supplier_code: 'GCX-02',
        has_bid: false,
        best_bid: null,
      },
    ];

    it('renders L1 supplier with rank, total price, and badges', () => {
      render(<SupplierRankingTab rankings={mockRankings} currency="INR" />);
      expect(screen.getByText('Fast Logistics Ltd')).toBeInTheDocument();
      expect(screen.getByText('L1 LEADER')).toBeInTheDocument();
      expect(screen.getByText('9,500.00')).toBeInTheDocument();
    });

    it('renders non-bidding supplier with muted "No bid submitted yet" row', () => {
      render(<SupplierRankingTab rankings={mockRankings} currency="INR" />);
      expect(screen.getByText('Global Cargo Express')).toBeInTheDocument();
      expect(screen.getByText(/No bid submitted yet/i)).toBeInTheDocument();
    });
  });

  describe('BidForm Component', () => {
    const mockSuppliers = [
      { id: 's1', name: 'Carrier Alpha', code: 'ALP-01' },
    ];
    const mockRankings: SupplierRanking[] = [
      {
        rank: 1,
        is_l1: true,
        supplier_id: 's1',
        supplier_name: 'Carrier Alpha',
        supplier_code: 'ALP-01',
        has_bid: true,
        best_bid: {
          id: 'b1',
          total_price: '10000.00',
          freight_charges: '10000.00',
          origin_charges: '0.00',
          destination_charges: '0.00',
          transit_time_days: 2,
          quote_validity_days: 7,
          submitted_at: '2026-11-14T01:00:00Z',
        },
      },
    ];

    it('warns when total price is not lower than carrier current best quote', () => {
      render(
        <BidForm
          rfqId="rfq-1"
          currency="INR"
          status="ACTIVE"
          invitedSuppliers={mockSuppliers}
          supplierRankings={mockRankings}
          onBidSubmitted={vi.fn()}
        />
      );

      // Carrier Alpha best is 10000.00
      expect(screen.getByText('Carrier Current Best:')).toBeInTheDocument();
      expect(screen.getByText('10,000.00')).toBeInTheDocument();

      // Enter freight charges 12000 (higher than 10000)
      const freightInput = screen.getByPlaceholderText('e.g. 5000');
      fireEvent.change(freightInput, { target: { value: '12000' } });

      // Should display warning that it must beat 10000
      expect(screen.getByText(/Must beat INR 10000.00/i)).toBeInTheDocument();

      // Submit button should be disabled
      const submitBtn = screen.getByRole('button', { name: /Submit Binding Quote/i });
      expect(submitBtn).toBeDisabled();
    });

    it('enables submission when total quote is lower than current best', () => {
      render(
        <BidForm
          rfqId="rfq-1"
          currency="INR"
          status="ACTIVE"
          invitedSuppliers={mockSuppliers}
          supplierRankings={mockRankings}
          onBidSubmitted={vi.fn()}
        />
      );

      const freightInput = screen.getByPlaceholderText('e.g. 5000');
      fireEvent.change(freightInput, { target: { value: '9500' } });

      // Should show valid lower quote
      expect(screen.getByText(/✓ Valid lower quote/i)).toBeInTheDocument();

      const submitBtn = screen.getByRole('button', { name: /Submit Binding Quote/i });
      expect(submitBtn).not.toBeDisabled();
    });
  });
});

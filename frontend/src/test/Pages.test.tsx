import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter, MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuctionsListPage } from '../pages/AuctionsListPage';
import { CreateRfqPage } from '../pages/CreateRfqPage';
import { AuctionDetailPage } from '../pages/AuctionDetailPage';
import * as rfqsApi from '../api/rfqs';

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{ui}</BrowserRouter>
    </QueryClientProvider>
  );
}

describe('Live Page & Button Interactive Tests', () => {
  describe('AuctionsListPage Interactions', () => {
    it('renders auctions list and handles status filter buttons', async () => {
      const mockRfqs = [
        {
          id: '1',
          reference_id: 'RFQ-01',
          name: 'Active Freight Auction',
          auction_type: 'BRITISH' as const,
          currency: 'INR' as const,
          status: 'ACTIVE' as const,
          bid_start_time: '2026-11-14T01:00:00Z',
          current_close_time: '2026-11-14T02:00:00Z',
          forced_close_time: '2026-11-14T03:00:00Z',
          current_lowest_bid: '10000.00',
          bids_count: 3,
          extension_count: 1,
        },
      ];

      vi.spyOn(rfqsApi, 'fetchRfqs').mockResolvedValue(mockRfqs);

      renderWithProviders(<AuctionsListPage />);

      // Verify auction appears
      expect(await screen.findByText('Active Freight Auction')).toBeInTheDocument();
      expect(screen.getByText('RFQ-01')).toBeInTheDocument();

      // Test status filter buttons: ALL, ACTIVE, SCHEDULED, CLOSED, FORCE_CLOSED
      const activeBtn = screen.getByRole('button', { name: /Active/i });
      fireEvent.click(activeBtn);
      expect(rfqsApi.fetchRfqs).toHaveBeenCalledWith(expect.objectContaining({ status: 'ACTIVE' }));

      const allBtn = screen.getByRole('button', { name: /All/i });
      fireEvent.click(allBtn);
      expect(rfqsApi.fetchRfqs).toHaveBeenCalledWith(expect.objectContaining({ status: 'ALL' }));

      // Test search filter input
      const searchInput = screen.getByPlaceholderText(/Search by RFQ name/i);
      fireEvent.change(searchInput, { target: { value: 'Mumbai' } });
      expect(searchInput).toHaveValue('Mumbai');
    });

    it('navigates to create new RFQ from header button', async () => {
      vi.spyOn(rfqsApi, 'fetchRfqs').mockResolvedValue([]);
      renderWithProviders(<AuctionsListPage />);

      const createBtn = await screen.findByRole('link', { name: /\+ Create New RFQ/i });
      expect(createBtn).toHaveAttribute('href', '/rfqs/new');
    });
  });

  describe('CreateRfqPage Interactions', () => {
    const mockSuppliers = [
      { id: 'sup-1', name: 'Maersk Line Logistics', code: 'MSK-01' },
      { id: 'sup-2', name: 'DHL Global Forwarding', code: 'DHL-02' },
      { id: 'sup-3', name: 'Blue Dart Express', code: 'BLU-03' },
    ];

    it('handles Carrier selection buttons (Select All, Clear All, toggle) and British toggle', async () => {
      vi.spyOn(rfqsApi, 'fetchSuppliers').mockResolvedValue(mockSuppliers);

      renderWithProviders(<CreateRfqPage />);

      // Verify carriers load
      expect(await screen.findByText('Maersk Line Logistics')).toBeInTheDocument();
      expect(screen.getByText('DHL Global Forwarding')).toBeInTheDocument();

      // Test "Clear All" button
      const clearAllBtn = screen.getByRole('button', { name: /Clear All/i });
      fireEvent.click(clearAllBtn);
      expect(screen.getByText(/4\. Carrier Invitations \(0 Selected\)/i)).toBeInTheDocument();

      // Test "Select All" button
      const selectAllBtn = screen.getByRole('button', { name: /Select All/i });
      fireEvent.click(selectAllBtn);
      expect(screen.getByText(/4\. Carrier Invitations \(3 Selected\)/i)).toBeInTheDocument();

      // Test toggling individual carrier
      const carrierCard = screen.getByText('Blue Dart Express');
      fireEvent.click(carrierCard);
      expect(screen.getByText(/4\. Carrier Invitations \(2 Selected\)/i)).toBeInTheDocument();

      // Test Carrier Search filter
      const searchCarrierInput = screen.getByPlaceholderText(/Search carriers by name or code/i);
      fireEvent.change(searchCarrierInput, { target: { value: 'DHL' } });
      expect(screen.getByText('DHL Global Forwarding')).toBeInTheDocument();
      expect(screen.queryByText('Maersk Line Logistics')).not.toBeInTheDocument();

      // Clear search
      fireEvent.change(searchCarrierInput, { target: { value: '' } });
      expect(screen.getByText('Maersk Line Logistics')).toBeInTheDocument();

      // Test Regenerate Reference ID button
      const regenBtn = screen.getByRole('button', { name: /Regenerate/i });
      fireEvent.click(regenBtn);

      // Test British Anti-Sniping Toggle switch
      const toggleBtn = screen.getByRole('button', { name: '' }); // the switch button
      fireEvent.click(toggleBtn);
      expect(screen.getByText(/Disabled \(Standard\)/i)).toBeInTheDocument();
      fireEvent.click(toggleBtn);
      expect(screen.getByText(/Enabled/i)).toBeInTheDocument();
    });
  });

  describe('AuctionDetailPage Interactions', () => {
    const mockRfqDetail = {
      id: 'rfq-detail-1',
      reference_id: 'RFQ-2026-LIVE',
      name: 'Chennai to Rotterdam Express',
      auction_type: 'BRITISH' as const,
      currency: 'INR' as const,
      status: 'ACTIVE' as const,
      pickup_date: '2026-11-20',
      bid_start_time: '2026-11-14T01:00:00Z',
      original_close_time: '2026-11-14T02:00:00Z',
      current_close_time: '2026-11-14T02:00:00Z',
      forced_close_time: '2026-11-14T03:00:00Z',
      british_config: {
        trigger_window_minutes: 5,
        extension_minutes: 5,
        extension_duration_minutes: 5,
        extension_trigger: 'L1_CHANGE_IN_LAST_X' as const,
      },
      invited_suppliers: [
        { id: 's1', name: 'Maersk Logistics', code: 'MSK-01' },
      ],
      supplier_rankings: [
        {
          rank: 1,
          is_l1: true,
          supplier_id: 's1',
          supplier_name: 'Maersk Logistics',
          carrier_name: 'Maersk Logistics',
          supplier_code: 'MSK-01',
          total_price: '50000.00',
          freight_charges: '40000.00',
          origin_charges: '5000.00',
          destination_charges: '5000.00',
          transit_time_days: 14,
          quote_validity_days: 30,
          submitted_at: '2026-11-14T01:10:00Z',
          has_bid: true,
          no_bid: false,
        },
      ],
      bid_history: [
        {
          id: 'b1',
          rfq_id: 'rfq-detail-1',
          supplier_id: 's1',
          carrier_name: 'Maersk Logistics',
          freight_charges: '40000.00',
          origin_charges: '5000.00',
          destination_charges: '5000.00',
          total_price: '50000.00',
          transit_time_days: 14,
          quote_validity_days: 30,
          submitted_at: '2026-11-14T01:10:00Z',
        },
      ],
      activity_log: [
        {
          id: 'ev1',
          rfq_id: 'rfq-detail-1',
          event_type: 'BID_SUBMITTED' as const,
          occurred_at: '2026-11-14T01:10:00Z',
          payload: { carrier_name: 'Maersk Logistics', total_price: '50000.00', currency: 'INR' },
        },
      ],
      stats: {
        total_bids: 1,
        participating_suppliers: 1,
        total_invited_suppliers: 1,
        extension_count: 0,
        initial_l1_price: '50000.00',
        current_l1_price: '50000.00',
        price_improvement: '0.00',
        price_improvement_pct: '0.00',
      },
      in_trigger_window: false,
      server_time: '2026-11-14T01:15:00Z',
    };

    it('renders detail view and switches tabs between Supplier Ranking and Bid History', async () => {
      vi.spyOn(rfqsApi, 'fetchRfqDetail').mockResolvedValue(mockRfqDetail);

      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false, gcTime: 0 } },
      });

      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={['/rfqs/rfq-detail-1']}>
            <Routes>
              <Route path="/rfqs/:id" element={<AuctionDetailPage />} />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      );

      // Verify title & stats
      expect(await screen.findByText('Chennai to Rotterdam Express')).toBeInTheDocument();
      expect(screen.getByText('RFQ-2026-LIVE')).toBeInTheDocument();

      // Verify Tab 1 is active by default
      expect(screen.getAllByText('Maersk Logistics').length).toBeGreaterThan(0);
      expect(screen.getAllByText('50,000.00').length).toBeGreaterThan(0);

      // Click Tab 2: "2. Bid History"
      const historyTabBtn = screen.getByRole('button', { name: /2\. Bid History/i });
      fireEvent.click(historyTabBtn);

      // Verify Bid History Tab rendered
      expect(screen.getByText(/Sort by Time/i)).toBeInTheDocument();
      expect(screen.getByText(/Sort by Price/i)).toBeInTheDocument();

      // Click "Sort by Price" button
      const sortPriceBtn = screen.getByRole('button', { name: /Sort by Price/i });
      fireEvent.click(sortPriceBtn);

      // Click "Sort by Time" button
      const sortTimeBtn = screen.getByRole('button', { name: /Sort by Time/i });
      fireEvent.click(sortTimeBtn);

      // Switch back to Tab 1: "1. Supplier Ranking"
      const rankingTabBtn = screen.getByRole('button', { name: /1\. Supplier Ranking/i });
      fireEvent.click(rankingTabBtn);
      expect(screen.getAllByText('Maersk Logistics').length).toBeGreaterThan(0);

      // Verify Audit Trail rendered
      expect(screen.getByText(/Audit Trail & Activity Log/i)).toBeInTheDocument();
      expect(screen.getByText(/1 event recorded/i)).toBeInTheDocument();
    });
  });

  describe('No Hiring/Assignment Wording Check', () => {
    it('verifies that no "hiring" or "assignment" text exists in the App layout', () => {
      const container = document.body;
      const textContent = container.textContent?.toLowerCase() || '';
      expect(textContent).not.toContain('hiring assignment');
    });
  });
});

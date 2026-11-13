export type AuctionMode = 'STANDARD' | 'BRITISH';

export type ExtensionTrigger = 
  | 'BID_IN_LAST_X'
  | 'ANY_RANK_CHANGE_IN_LAST_X'
  | 'L1_CHANGE_IN_LAST_X';

export type AuctionStatus = 
  | 'SCHEDULED'
  | 'ACTIVE'
  | 'CLOSED'
  | 'FORCE_CLOSED';

export type EventType =
  | 'RFQ_CREATED'
  | 'AUCTION_STARTED'
  | 'BID_SUBMITTED'
  | 'TIME_EXTENDED'
  | 'AUCTION_CLOSED'
  | 'AUCTION_FORCE_CLOSED';

export type Currency = 'INR' | 'USD' | 'EUR' | 'GBP' | 'AED';

export interface Supplier {
  id: string;
  name: string;
  code: string;
  created_at?: string;
}

export interface BritishConfig {
  trigger_window_minutes: number;
  extension_duration_minutes: number;
  extension_trigger: ExtensionTrigger;
}

export interface Bid {
  id: string;
  rfq_id: string;
  supplier_id: string;
  carrier_name: string;
  freight_charges: string;
  origin_charges: string;
  destination_charges: string;
  total_price: string;
  transit_time_days: number;
  quote_validity_days: number;
  submitted_at: string;
}

export interface SupplierRanking {
  rank: number;
  is_l1: boolean;
  supplier_id: string;
  supplier_name: string;
  supplier_code: string;
  has_bid: boolean;
  best_bid?: {
    id: string;
    total_price: string;
    freight_charges: string;
    origin_charges: string;
    destination_charges: string;
    transit_time_days: number;
    quote_validity_days: number;
    submitted_at: string;
  } | null;
}

export interface RfqStats {
  total_bids: number;
  participating_suppliers: number;
  total_invited_suppliers: number;
  extension_count: number;
  initial_l1_price: string | null;
  current_l1_price: string | null;
  price_improvement: string | null;
  price_improvement_pct: string | null;
}

export interface AuctionEvent {
  id: string;
  rfq_id: string;
  event_type: EventType;
  occurred_at: string;
  payload: Record<string, any>;
}

export interface RfqSummary {
  id: string;
  reference_id: string;
  name: string;
  mode: AuctionMode;
  currency: Currency;
  status: AuctionStatus;
  bid_start_time: string;
  current_close_time: string;
  forced_close_time: string;
  current_lowest_bid: string | null;
  bids_count: number;
  extension_count: number;
  trigger_window_minutes?: number | null;
}

export interface RfqDetail {
  id: string;
  reference_id: string;
  name: string;
  mode: AuctionMode;
  currency: Currency;
  status: AuctionStatus;
  pickup_date: string;
  bid_start_time: string;
  original_close_time: string;
  current_close_time: string;
  forced_close_time: string;
  british_config?: BritishConfig | null;
  invited_suppliers: Supplier[];
  supplier_rankings: SupplierRanking[];
  bid_history: Bid[];
  activity_log: AuctionEvent[];
  stats: RfqStats;
  in_trigger_window: boolean;
  server_time: string;
}

export interface CreateRfqPayload {
  name: string;
  reference_id: string;
  currency: Currency;
  pickup_date: string;
  bid_start_time: string;
  bid_close_time: string;
  forced_close_time: string;
  mode: AuctionMode;
  supplier_ids: string[];
  british_config?: BritishConfig;
}

export interface SubmitBidPayload {
  supplier_id: string;
  freight_charges: string;
  origin_charges: string;
  destination_charges: string;
  transit_time_days: number;
  quote_validity_days: number;
}

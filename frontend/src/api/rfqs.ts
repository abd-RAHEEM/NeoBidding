import { apiRequest } from './client';
import type { 
  Supplier, 
  RfqSummary, 
  RfqDetail, 
  CreateRfqPayload, 
  SubmitBidPayload, 
  Bid 
} from './types';

export async function fetchSuppliers(): Promise<Supplier[]> {
  const data = await apiRequest<any>('/suppliers');
  if (Array.isArray(data)) {
    return data;
  }
  if (data && Array.isArray(data.items)) {
    return data.items;
  }
  return [];
}

export async function fetchRfqs(filters?: { status?: string; search?: string }): Promise<RfqSummary[]> {
  const params = new URLSearchParams();
  if (filters?.status && filters.status !== 'ALL') {
    params.set('status', filters.status);
  }
  if (filters?.search && filters.search.trim()) {
    // Send 'q' which matches backend query parameter
    params.set('q', filters.search.trim());
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  const data = await apiRequest<any>(`/rfqs${query}`);
  if (Array.isArray(data)) {
    return data;
  }
  if (data && Array.isArray(data.items)) {
    return data.items;
  }
  return [];
}

export async function fetchRfqDetail(rfqId: string): Promise<RfqDetail> {
  const data = await apiRequest<any>(`/rfqs/${rfqId}`);
  if (data) {
    data.supplier_rankings = Array.isArray(data.supplier_rankings)
      ? data.supplier_rankings
      : Array.isArray(data.ranking)
      ? data.ranking
      : [];
    data.bid_history = Array.isArray(data.bid_history) ? data.bid_history : [];
    data.activity_log = Array.isArray(data.activity_log) ? data.activity_log : [];
    data.invited_suppliers = Array.isArray(data.invited_suppliers) ? data.invited_suppliers : [];
    data.in_trigger_window = Boolean(data.in_trigger_window);
  }
  return data as RfqDetail;
}

export async function createRfq(payload: CreateRfqPayload): Promise<RfqDetail> {
  return apiRequest<RfqDetail>('/rfqs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function submitBid(
  rfqId: string, 
  payload: SubmitBidPayload, 
  idempotencyKey: string
): Promise<Bid> {
  return apiRequest<Bid>(`/rfqs/${rfqId}/bids`, {
    method: 'POST',
    headers: {
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify(payload),
  });
}


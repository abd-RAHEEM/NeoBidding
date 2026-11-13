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
  return apiRequest<Supplier[]>('/suppliers');
}

export async function fetchRfqs(filters?: { status?: string; search?: string }): Promise<RfqSummary[]> {
  const params = new URLSearchParams();
  if (filters?.status && filters.status !== 'ALL') {
    params.set('status', filters.status);
  }
  if (filters?.search && filters.search.trim()) {
    params.set('search', filters.search.trim());
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  return apiRequest<RfqSummary[]>(`/rfqs${query}`);
}

export async function fetchRfqDetail(rfqId: string): Promise<RfqDetail> {
  return apiRequest<RfqDetail>(`/rfqs/${rfqId}`);
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

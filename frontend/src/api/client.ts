let serverClockOffsetMs = 0;

export function updateServerTimeOffset(serverTimeIso: string): void {
  try {
    const serverMs = new Date(serverTimeIso).getTime();
    if (!isNaN(serverMs)) {
      serverClockOffsetMs = serverMs - Date.now();
    }
  } catch {
    // Ignore invalid timestamps
  }
}

export function getServerNow(): Date {
  return new Date(Date.now() + serverClockOffsetMs);
}

export class ApiError extends Error {
  errorCode: string;
  statusCode: number;
  details?: any;

  constructor(message: string, errorCode: string = 'UNKNOWN_ERROR', statusCode: number = 500, details?: any) {
    super(message);
    this.name = 'ApiError';
    this.errorCode = errorCode;
    this.statusCode = statusCode;
    this.details = details;
  }
}

const BASE_URL = '/api/v1';

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  const contentType = response.headers.get('content-type');
  const isJson = contentType && contentType.includes('application/json');
  const data = isJson ? await response.json() : await response.text();

  if (isJson && data && typeof data === 'object' && 'server_time' in data) {
    updateServerTimeOffset(data.server_time);
  }

  if (!response.ok) {
    const errCode = (isJson && data?.error_code) || `HTTP_${response.status}`;
    const errMsg = (isJson && data?.message) || response.statusText || 'Request failed';
    throw new ApiError(errMsg, errCode, response.status, isJson ? data?.details : undefined);
  }

  return data as T;
}

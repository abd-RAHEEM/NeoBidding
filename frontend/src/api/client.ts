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

// Resolve API Base URL from Vite environment variables (VITE_API_BASE_URL)
// Defaults to '/api/v1' so local development continues using the Vite proxy
function resolveApiBaseUrl(): string {
  const envUrl = (import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/+$/, '');
  if (!envUrl) {
    return '/api/v1';
  }
  // Ensure /api/v1 prefix is appended if user provides host only (e.g. https://xyz.onrender.com)
  if (!envUrl.endsWith('/api/v1')) {
    return `${envUrl}/api/v1`;
  }
  return envUrl;
}

const BASE_URL = resolveApiBaseUrl();

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = `${BASE_URL}${cleanEndpoint}`;
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


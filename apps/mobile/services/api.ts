import { getIdToken } from "@/services/firebase";
import { trackApiError } from "@/services/telemetry";
import { VerifyResponse } from "@hausly/types";

const BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const API_PREFIX = "/api/v1";

interface ApiError {
  detail: string;
  code?: string;
}

class ApiClientError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
  }
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  const token = await getIdToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const authHeaders = await getAuthHeaders();
  const url = `${BASE_URL}${API_PREFIX}${path}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    let errorBody: ApiError = { detail: "Unknown error" };
    try {
      errorBody = await response.json();
    } catch {
      // Response body isn't JSON
    }
    trackApiError(
      options.method ?? "GET",
      path,
      response.status,
      errorBody.detail,
    );
    throw new ApiClientError(
      errorBody.detail,
      response.status,
      errorBody.code
    );
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

export const api = {
  get<T>(path: string): Promise<T> {
    return request<T>(path, { method: "GET" });
  },

  post<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  },

  put<T>(path: string, body: unknown): Promise<T> {
    return request<T>(path, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  },

  patch<T>(path: string, body: unknown): Promise<T> {
    return request<T>(path, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  delete<T>(path: string): Promise<T> {
    return request<T>(path, { method: "DELETE" });
  },
};

// --- Auth ---

export { VerifyResponse };

export function verifyToken(): Promise<VerifyResponse> {
  return api.post<VerifyResponse>("/auth/verify");
}

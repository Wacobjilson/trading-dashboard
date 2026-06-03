import type { AuthResponse, Quote, User } from "./types";

// API_BASE is empty by default → requests go to the same origin (e.g. behind an
// ingress that routes /api to the backend). For local docker-compose, the
// frontend and backend are on different ports, so NEXT_PUBLIC_API_BASE_URL is set.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

const TOKEN_KEY = "quanta_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.error) msg = body.error;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  register: (email: string, password: string, displayName: string) =>
    request<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, displayName }),
    }),

  login: (email: string, password: string) =>
    request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<User>("/me"),

  quotes: (symbols?: string[]) => {
    const q = symbols?.length ? `?symbols=${symbols.join(",")}` : "";
    return request<{ quotes: Quote[] }>(`/quotes${q}`);
  },
};

export { API_BASE };

"use client";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type ApiRequestOptions = RequestInit & {
  token?: string | null;
};

export async function apiFetch<T>(
  path: string,
  { token, headers, ...init }: ApiRequestOptions = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/api${path}`, {
    ...init,
    headers: {
      ...(headers ?? {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    if (text) {
      try {
        const parsed = JSON.parse(text) as { detail?: string };
        throw new Error(parsed.detail || text);
      } catch {
        throw new Error(text);
      }
    }
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export type AuthSession = {
  accessToken: string;
  refreshToken: string;
};

export function readSession(): AuthSession | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem("attendance-session");
  return raw ? (JSON.parse(raw) as AuthSession) : null;
}

export function writeSession(session: AuthSession) {
  window.localStorage.setItem("attendance-session", JSON.stringify(session));
}

export function clearSession() {
  window.localStorage.removeItem("attendance-session");
}

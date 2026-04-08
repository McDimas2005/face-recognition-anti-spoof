"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { apiFetch, writeSession } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("ChangeMe123!");
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const session = await apiFetch<{ access_token: string; refresh_token: string }>("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      writeSession({
        accessToken: session.access_token,
        refreshToken: session.refresh_token,
      });
      router.push("/");
    } catch {
      setError("Login failed. Check your credentials.");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="glass-card w-full max-w-xl p-8">
        <p className="pill">Face Attendance</p>
        <h1 className="mt-6 text-5xl font-semibold tracking-tight">Launch-ready V1</h1>
        <p className="mt-4 text-sm text-ink/70">
          Admin login for enrollment, attendance, review, and audit workflows.
        </p>
        <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
          <input className="field" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email" />
          <input
            className="field"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            placeholder="Password"
          />
          {error ? <p className="text-sm text-warning">{error}</p> : null}
          <button className="btn-primary w-full" type="submit">
            Sign In
          </button>
        </form>
      </div>
    </main>
  );
}


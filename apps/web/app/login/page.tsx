"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { apiFetch, writeSession } from "@/lib/api";

const demoAccounts = [
  {
    role: "Super Admin",
    description: "Full settings, users, thresholds, audit, and system administration.",
    email: "demo.superadmin@example.com",
    password: "DemoSuperadmin123!",
  },
  {
    role: "Admin",
    description: "Manage people, enrollments, sessions, and attendance operations.",
    email: "demo.admin@example.com",
    password: "DemoAdmin123!",
  },
  {
    role: "Reviewer",
    description: "Review unknown, ambiguous, spoof-rejected, and manual follow-up cases.",
    email: "demo.reviewer@example.com",
    password: "DemoReviewer123!",
  },
  {
    role: "Viewer",
    description: "Read-only access for dashboards, logs, and attendance visibility.",
    email: "demo.viewer@example.com",
    password: "DemoViewer123!",
  },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  function useDemoAccount(account: (typeof demoAccounts)[number]) {
    setEmail(account.email);
    setPassword(account.password);
    setError("");
  }

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
      <div className="grid w-full max-w-6xl gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <section className="glass-card p-8">
          <p className="pill">Face Attendance</p>
          <h1 className="mt-6 text-4xl font-semibold tracking-tight sm:text-5xl">Portfolio demo login</h1>
          <p className="mt-4 text-sm text-ink/70">
            Use one of the public demo accounts to explore enrollment, attendance, review, audit, and admin workflows.
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
          <p className="mt-5 text-xs leading-5 text-ink/55">
            Demo accounts are public. Do not upload sensitive biometric data.
          </p>
        </section>

        <section className="glass-card p-8">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="pill">Demo accounts</p>
              <h2 className="mt-4 text-2xl font-semibold">Choose a role to try</h2>
            </div>
          </div>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {demoAccounts.map((account) => (
              <article key={account.email} className="rounded-2xl border border-ink/10 bg-white p-4 shadow-card">
                <h3 className="text-lg font-semibold">{account.role}</h3>
                <p className="mt-2 min-h-12 text-sm leading-5 text-ink/65">{account.description}</p>
                <dl className="mt-4 space-y-2 text-sm">
                  <div>
                    <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink/45">Email</dt>
                    <dd className="mt-1 break-all font-medium">{account.email}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink/45">Password</dt>
                    <dd className="mt-1 break-all font-medium">{account.password}</dd>
                  </div>
                </dl>
                <button className="btn-secondary mt-5 w-full" type="button" onClick={() => useDemoAccount(account)}>
                  Use this account
                </button>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

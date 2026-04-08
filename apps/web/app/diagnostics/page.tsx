"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { API_BASE_URL } from "@/lib/api";

export default function DiagnosticsPage() {
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/health/live`)
      .then((response) => response.json())
      .then(() => setStatus("healthy"))
      .catch(() => setStatus("unreachable"));
  }, []);

  return (
    <AppShell title="Diagnostics">
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">API reachability</p>
          <p className="mt-4 text-3xl font-semibold">{status}</p>
        </div>
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Risk framing</p>
          <p className="mt-4 text-sm text-ink/70">
            Anti-spoofing and passive liveness are risk-reduction controls. They are not guarantees against printed-photo,
            replay-screen, or sophisticated presentation attacks.
          </p>
        </div>
      </div>
    </AppShell>
  );
}


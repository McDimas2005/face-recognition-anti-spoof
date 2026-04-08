"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch, readSession } from "@/lib/api";

type ReviewCase = {
  id: string;
  reason: string;
  status: string;
  proposed_person_id?: string | null;
  resolution_notes?: string | null;
};

export default function ReviewPage() {
  const [cases, setCases] = useState<ReviewCase[]>([]);

  useEffect(() => {
    const session = readSession();
    if (!session) return;
    apiFetch<ReviewCase[]>("/review-cases", { token: session.accessToken }).then(setCases);
  }, []);

  return (
    <AppShell title="Review Queue">
      <div className="glass-card p-6">
        <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Unknown and risky attempts</p>
        <div className="mt-4 space-y-3">
          {cases.map((item) => (
            <div key={item.id} className="rounded-2xl bg-sand p-4">
              <p className="font-semibold">{item.reason}</p>
              <p className="text-sm text-ink/60">{item.status}</p>
              <p className="text-sm text-ink/60">{item.proposed_person_id || "No proposed identity"}</p>
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  );
}


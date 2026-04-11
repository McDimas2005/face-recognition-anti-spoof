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
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadCases() {
    const session = readSession();
    if (!session) return;
    const response = await apiFetch<ReviewCase[]>("/review-cases", { token: session.accessToken });
    setCases(response);
  }

  useEffect(() => {
    void loadCases();
  }, []);

  async function clearQueue() {
    const session = readSession();
    if (!session || !window.confirm("Clear the entire review queue?")) return;
    try {
      await apiFetch("/review-cases", { token: session.accessToken, method: "DELETE" });
      setMessage("Review queue cleared.");
      setError(null);
      await loadCases();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to clear review queue");
    }
  }

  async function deleteCase(reviewId: string) {
    const session = readSession();
    if (!session || !window.confirm("Delete this review case?")) return;
    try {
      await apiFetch(`/review-cases/${reviewId}`, { token: session.accessToken, method: "DELETE" });
      setMessage("Review case deleted.");
      setError(null);
      await loadCases();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to delete review case");
    }
  }

  return (
    <AppShell title="Review Queue">
      <div className="glass-card p-6">
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Unknown and risky attempts</p>
          <button className="btn-secondary" onClick={() => void clearQueue()}>
            Clear queue
          </button>
        </div>
        {message ? <p className="mt-4 text-sm text-emerald-700">{message}</p> : null}
        {error ? <p className="mt-4 text-sm text-warning">{error}</p> : null}
        <div className="mt-4 space-y-3">
          {cases.map((item) => (
            <div key={item.id} className="rounded-2xl bg-sand p-4">
              <p className="font-semibold">{item.reason}</p>
              <p className="text-sm text-ink/60">{item.status}</p>
              <p className="text-sm text-ink/60">{item.proposed_person_id || "No proposed identity"}</p>
              <p className="text-sm text-ink/55">{item.resolution_notes || "No notes"}</p>
              <button className="btn-secondary mt-4" onClick={() => void deleteCase(item.id)}>
                Delete
              </button>
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  );
}

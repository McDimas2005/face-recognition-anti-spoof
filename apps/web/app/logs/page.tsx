"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch, readSession } from "@/lib/api";

type Attempt = { id: string; outcome: string; top_person_id?: string | null; created_at: string };
type Event = { id: string; person_id: string; source: string; status: string; recognized_at: string };

export default function LogsPage() {
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [events, setEvents] = useState<Event[]>([]);

  useEffect(() => {
    const session = readSession();
    if (!session) return;
    Promise.all([
      apiFetch<Attempt[]>("/recognition-attempts", { token: session.accessToken }),
      apiFetch<Event[]>("/attendance-events", { token: session.accessToken }),
    ]).then(([attemptsResponse, eventsResponse]) => {
      setAttempts(attemptsResponse);
      setEvents(eventsResponse);
    });
  }, []);

  return (
    <AppShell title="Logs">
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Recognition attempts</p>
          <div className="mt-4 space-y-3">
            {attempts.map((attempt) => (
              <div key={attempt.id} className="rounded-2xl bg-sand p-4 text-sm">
                <p className="font-semibold">{attempt.outcome}</p>
                <p className="text-ink/60">{attempt.top_person_id || "No person selected"}</p>
                <p className="text-xs text-ink/45">{new Date(attempt.created_at).toLocaleString()}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Attendance events</p>
          <div className="mt-4 space-y-3">
            {events.map((event) => (
              <div key={event.id} className="rounded-2xl bg-sand p-4 text-sm">
                <p className="font-semibold">{event.person_id}</p>
                <p className="text-ink/60">{event.source} / {event.status}</p>
                <p className="text-xs text-ink/45">{new Date(event.recognized_at).toLocaleString()}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}


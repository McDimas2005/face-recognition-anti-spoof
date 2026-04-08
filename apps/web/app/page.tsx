"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { StatCard } from "@/components/stat-card";
import { apiFetch, readSession } from "@/lib/api";

type DashboardStats = {
  people: number;
  sessions: number;
  attendanceEvents: number;
  reviewCases: number;
};

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>({
    people: 0,
    sessions: 0,
    attendanceEvents: 0,
    reviewCases: 0,
  });

  useEffect(() => {
    const session = readSession();
    if (!session) {
      return;
    }
    Promise.all([
      apiFetch<Array<unknown>>("/persons", { token: session.accessToken }),
      apiFetch<Array<unknown>>("/sessions", { token: session.accessToken }),
      apiFetch<Array<unknown>>("/attendance-events", { token: session.accessToken }),
      apiFetch<Array<unknown>>("/review-cases", { token: session.accessToken }),
    ]).then(([people, sessions, attendanceEvents, reviewCases]) =>
      setStats({
        people: people.length,
        sessions: sessions.length,
        attendanceEvents: attendanceEvents.length,
        reviewCases: reviewCases.length,
      }),
    );
  }, []);

  return (
    <AppShell title="Dashboard">
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="People" value={stats.people} description="Managed identities in the enrollment store." />
        <StatCard label="Sessions" value={stats.sessions} description="Attendance windows created by admins." />
        <StatCard label="Attendance" value={stats.attendanceEvents} description="Committed attendance events." />
        <StatCard label="Review Queue" value={stats.reviewCases} description="Unknown, ambiguous, or risky attempts." />
      </div>
      <div className="glass-card mt-6 p-8">
        <p className="pill">Operational rules</p>
        <ul className="mt-5 space-y-3 text-sm text-ink/70">
          <li>Attendance is rejected when multiple faces appear in the frame.</li>
          <li>Manual overrides remain auditable and separate from AI-confirmed attendance.</li>
          <li>Enrollment batches stay incomplete until diversity requirements are met.</li>
          <li>Liveness reduces spoofing risk but does not guarantee spoof prevention.</li>
        </ul>
      </div>
    </AppShell>
  );
}


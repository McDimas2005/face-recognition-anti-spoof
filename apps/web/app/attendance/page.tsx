"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { AttendanceCamera } from "@/components/attendance-camera";
import { apiFetch, readSession } from "@/lib/api";

type SessionItem = { id: string; name: string };

export default function AttendancePage() {
  const [sessions, setSessions] = useState<SessionItem[]>([]);

  useEffect(() => {
    const session = readSession();
    if (!session) return;
    apiFetch<SessionItem[]>("/sessions", { token: session.accessToken }).then(setSessions);
  }, []);

  return (
    <AppShell title="Live Attendance">
      <AttendanceCamera sessions={sessions} />
    </AppShell>
  );
}


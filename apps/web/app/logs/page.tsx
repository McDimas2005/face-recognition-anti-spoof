"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch, readSession } from "@/lib/api";

type Attempt = {
  id: string;
  outcome: string;
  face_count: number;
  quality_passed: boolean;
  top_person_id?: string | null;
  top_person_name?: string | null;
  top_score?: number | null;
  second_score?: number | null;
  liveness_score?: number | null;
  breakdown: Record<string, unknown>;
  created_at: string;
};

type Event = {
  id: string;
  person_id: string;
  person_name?: string | null;
  source: string;
  status: string;
  recognized_at: string;
  manual_reason?: string | null;
};

function readObject(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function formatPercent(value: unknown, scale = 100): string {
  return typeof value === "number" ? `${(value * scale).toFixed(2)}%` : "n/a";
}

function formatNumber(value: unknown, digits = 4): string {
  return typeof value === "number" ? value.toFixed(digits) : "n/a";
}

function formatLabel(value: string): string {
  return value.replaceAll("_", " ");
}

export default function LogsPage() {
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadLogs() {
    const session = readSession();
    if (!session) return;
    const [attemptsResponse, eventsResponse] = await Promise.all([
      apiFetch<Attempt[]>("/recognition-attempts", { token: session.accessToken }),
      apiFetch<Event[]>("/attendance-events", { token: session.accessToken }),
    ]);
    setAttempts(attemptsResponse);
    setEvents(eventsResponse);
  }

  useEffect(() => {
    void loadLogs();
  }, []);

  async function clearAttempts() {
    const session = readSession();
    if (!session || !window.confirm("Clear all recognition attempts? Related review cases will also be removed.")) return;
    try {
      await apiFetch("/recognition-attempts", { token: session.accessToken, method: "DELETE" });
      setMessage("Recognition attempts cleared.");
      setError(null);
      await loadLogs();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to clear recognition attempts");
    }
  }

  async function deleteAttempt(attemptId: string) {
    const session = readSession();
    if (!session || !window.confirm("Delete this recognition attempt?")) return;
    try {
      await apiFetch(`/recognition-attempts/${attemptId}`, { token: session.accessToken, method: "DELETE" });
      setMessage("Recognition attempt deleted.");
      setError(null);
      await loadLogs();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to delete recognition attempt");
    }
  }

  async function clearEvents() {
    const session = readSession();
    if (!session || !window.confirm("Clear all attendance events?")) return;
    try {
      await apiFetch("/attendance-events", { token: session.accessToken, method: "DELETE" });
      setMessage("Attendance events cleared.");
      setError(null);
      await loadLogs();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to clear attendance events");
    }
  }

  async function deleteEvent(eventId: string) {
    const session = readSession();
    if (!session || !window.confirm("Delete this attendance event?")) return;
    try {
      await apiFetch(`/attendance-events/${eventId}`, { token: session.accessToken, method: "DELETE" });
      setMessage("Attendance event deleted.");
      setError(null);
      await loadLogs();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to delete attendance event");
    }
  }

  return (
    <AppShell title="Logs">
      <div className="space-y-4">
        {message ? <p className="text-sm text-emerald-700">{message}</p> : null}
        {error ? <p className="text-sm text-warning">{error}</p> : null}
      </div>
      <div className="mt-4 grid gap-6 lg:grid-cols-2">
        <div className="glass-card p-6">
          <div className="flex items-center justify-between gap-4">
            <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Recognition attempts</p>
            <button className="btn-secondary" onClick={() => void clearAttempts()}>
              Clear attempts
            </button>
          </div>
          <div className="mt-4 space-y-3">
            {attempts.map((attempt) => {
              const breakdown = readObject(attempt.breakdown) ?? {};
              const recognitionThresholds = readObject(breakdown.recognition_thresholds);
              const qualityThresholds = readObject(breakdown.quality_thresholds);

              return (
                <div key={attempt.id} className="rounded-2xl bg-sand p-4 text-sm">
                  <p className="font-semibold capitalize">{formatLabel(attempt.outcome)}</p>
                  <p className="mt-1 text-ink/70">
                    {attempt.top_person_name ?? attempt.top_person_id ?? "No person selected"}
                  </p>
                  {attempt.top_person_name && attempt.top_person_id ? (
                    <p className="text-xs text-ink/45">{attempt.top_person_id}</p>
                  ) : null}
                  <p className="mt-2 text-xs text-ink/45">{new Date(attempt.created_at).toLocaleString()}</p>

                  <div className="mt-4 grid gap-2 text-xs text-ink/75 sm:grid-cols-2">
                    <p>Faces detected: {attempt.face_count}</p>
                    <p>Quality passed: {attempt.quality_passed ? "yes" : "no"}</p>
                    <p>Top score: {formatNumber(attempt.top_score)}</p>
                    <p>Second score: {formatNumber(attempt.second_score)}</p>
                    <p>Liveness score: {formatNumber(attempt.liveness_score)}</p>
                    <p>Match percent: {formatPercent(breakdown.match_percent, 1)}</p>
                    <p>Margin: {formatNumber(breakdown.margin_raw ?? breakdown.margin)}</p>
                    <p>Model: {typeof breakdown.top_model_name === "string" ? breakdown.top_model_name : "n/a"}</p>
                  </div>

                  {recognitionThresholds ? (
                    <div className="mt-4 rounded-2xl bg-white/70 p-3 text-xs text-ink/75">
                      <p className="font-semibold text-ink">Recognition thresholds</p>
                      <div className="mt-2 grid gap-2 sm:grid-cols-2">
                        <p>Similarity: {formatNumber(recognitionThresholds.similarity_threshold)}</p>
                        <p>Commit: {formatNumber(recognitionThresholds.commit_threshold)}</p>
                        <p>Ambiguity margin: {formatNumber(recognitionThresholds.ambiguity_margin)}</p>
                        <p>Liveness: {formatNumber(recognitionThresholds.liveness_threshold)}</p>
                        <p>Consensus frames: {formatNumber(recognitionThresholds.consensus_frames, 0)}</p>
                        <p>Consensus window: {formatNumber(recognitionThresholds.consensus_window_seconds, 0)}s</p>
                      </div>
                    </div>
                  ) : null}

                  {qualityThresholds ? (
                    <div className="mt-3 rounded-2xl bg-white/70 p-3 text-xs text-ink/75">
                      <p className="font-semibold text-ink">Quality thresholds</p>
                      <div className="mt-2 grid gap-2 sm:grid-cols-2">
                        <p>Min face size: {formatNumber(qualityThresholds.min_face_size, 0)}</p>
                        <p>Min brightness: {formatNumber(qualityThresholds.min_brightness)}</p>
                        <p>Max brightness: {formatNumber(qualityThresholds.max_brightness)}</p>
                        <p>Min blur score: {formatNumber(qualityThresholds.min_blur_score)}</p>
                        <p>Max yaw score: {formatNumber(qualityThresholds.max_yaw_score)}</p>
                        <p>Max occlusion: {formatNumber(qualityThresholds.max_occlusion_score)}</p>
                      </div>
                    </div>
                  ) : null}

                  <details className="mt-4">
                    <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.14em] text-ink/55">
                      Detailed breakdown
                    </summary>
                    <pre className="mt-3 overflow-auto rounded-2xl bg-ink p-4 text-xs text-sand">
                      {JSON.stringify(attempt.breakdown, null, 2)}
                    </pre>
                  </details>

                  <button className="btn-secondary mt-4" onClick={() => void deleteAttempt(attempt.id)}>
                    Delete
                  </button>
                </div>
              );
            })}
          </div>
        </div>
        <div className="glass-card p-6">
          <div className="flex items-center justify-between gap-4">
            <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Attendance events</p>
            <button className="btn-secondary" onClick={() => void clearEvents()}>
              Clear events
            </button>
          </div>
          <div className="mt-4 space-y-3">
            {events.map((event) => (
              <div key={event.id} className="rounded-2xl bg-sand p-4 text-sm">
                <p className="font-semibold">{event.person_name ?? event.person_id}</p>
                {event.person_name ? <p className="text-xs text-ink/45">{event.person_id}</p> : null}
                <p className="mt-1 text-ink/60">
                  {formatLabel(event.source)} / {formatLabel(event.status)}
                </p>
                {event.manual_reason ? <p className="mt-2 text-xs text-ink/60">Reason: {event.manual_reason}</p> : null}
                <p className="mt-2 text-xs text-ink/45">{new Date(event.recognized_at).toLocaleString()}</p>
                <button className="btn-secondary mt-4" onClick={() => void deleteEvent(event.id)}>
                  Delete
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

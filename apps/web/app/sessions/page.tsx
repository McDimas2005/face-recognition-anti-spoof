"use client";

import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch, readSession } from "@/lib/api";

type Person = { id: string; full_name: string };
type SessionItem = {
  id: string;
  name: string;
  description?: string | null;
  starts_at: string;
  ends_at: string;
  allowed_person_ids: string[];
};

const defaultForm = {
  id: "",
  name: "",
  description: "",
  startsAt: "",
  endsAt: "",
  selectedPeople: [] as string[],
};

function toIsoStringFromLocalInput(value: string) {
  if (!value) return "";
  return new Date(value).toISOString();
}

function toLocalInputValue(value: string) {
  const date = new Date(value);
  const offsetDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return offsetDate.toISOString().slice(0, 16);
}

export default function SessionsPage() {
  const [people, setPeople] = useState<Person[]>([]);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [form, setForm] = useState(defaultForm);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const editing = Boolean(form.id);

  async function loadData() {
    const session = readSession();
    if (!session) return;
    const [peopleResponse, sessionsResponse] = await Promise.all([
      apiFetch<Person[]>("/persons", { token: session.accessToken }),
      apiFetch<SessionItem[]>("/sessions", { token: session.accessToken }),
    ]);
    setPeople(peopleResponse);
    setSessions(sessionsResponse);
  }

  useEffect(() => {
    void loadData();
  }, []);

  function resetForm() {
    setForm(defaultForm);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const session = readSession();
    if (!session) return;
    setError(null);
    setMessage(null);
    const payload = {
      name: form.name,
      description: form.description || null,
      starts_at: toIsoStringFromLocalInput(form.startsAt),
      ends_at: toIsoStringFromLocalInput(form.endsAt),
      allowed_person_ids: form.selectedPeople,
    };
    try {
      if (editing) {
        await apiFetch(`/sessions/${form.id}`, {
          token: session.accessToken,
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        setMessage("Session updated.");
      } else {
        await apiFetch("/sessions", {
          token: session.accessToken,
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        setMessage("Session created.");
      }
      resetForm();
      await loadData();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to save session");
    }
  }

  async function deleteSession(sessionId: string) {
    const session = readSession();
    if (!session || !window.confirm("Delete this session and its related attendance/review data?")) return;
    setError(null);
    setMessage(null);
    try {
      await apiFetch(`/sessions/${sessionId}`, {
        token: session.accessToken,
        method: "DELETE",
      });
      if (form.id === sessionId) resetForm();
      setMessage("Session deleted.");
      await loadData();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to delete session");
    }
  }

  return (
    <AppShell title="Sessions">
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <form className="glass-card p-6" onSubmit={handleSubmit}>
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">{editing ? "Edit session" : "Create session"}</p>
          <div className="mt-4 space-y-4">
            <input
              className="field"
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="Class or event name"
            />
            <textarea
              className="field min-h-24"
              value={form.description}
              onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
              placeholder="Description"
            />
            <input
              className="field"
              type="datetime-local"
              value={form.startsAt}
              onChange={(event) => setForm((current) => ({ ...current, startsAt: event.target.value }))}
            />
            <input
              className="field"
              type="datetime-local"
              value={form.endsAt}
              onChange={(event) => setForm((current) => ({ ...current, endsAt: event.target.value }))}
            />
            <p className="text-xs text-ink/55">
              Session times are entered in your browser's local timezone and stored with timezone information.
            </p>
            <div className="rounded-2xl border border-ink/10 bg-white p-4">
              <p className="text-sm font-semibold">Allowlist</p>
              <div className="mt-3 grid gap-2">
                {people.map((person) => (
                  <label key={person.id} className="flex items-center gap-3 text-sm">
                    <input
                      type="checkbox"
                      checked={form.selectedPeople.includes(person.id)}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          selectedPeople: event.target.checked
                            ? [...current.selectedPeople, person.id]
                            : current.selectedPeople.filter((item) => item !== person.id),
                        }))
                      }
                    />
                    {person.full_name}
                  </label>
                ))}
              </div>
            </div>
            {message ? <p className="text-sm text-emerald-700">{message}</p> : null}
            {error ? <p className="text-sm text-warning">{error}</p> : null}
            <div className="flex gap-3">
              <button className="btn-primary flex-1">{editing ? "Save changes" : "Save session"}</button>
              {editing ? (
                <button type="button" className="btn-secondary flex-1" onClick={resetForm}>
                  Cancel
                </button>
              ) : null}
            </div>
          </div>
        </form>
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Session list</p>
          <div className="mt-4 space-y-3">
            {sessions.map((item) => (
              <div key={item.id} className="rounded-2xl bg-sand p-4">
                <p className="font-semibold">{item.name}</p>
                <p className="text-sm text-ink/60">
                  {new Date(item.starts_at).toLocaleString()} to {new Date(item.ends_at).toLocaleString()}
                </p>
                <p className="text-sm text-ink/55">{item.description || "No description"}</p>
                <p className="mt-2 text-xs uppercase tracking-[0.18em] text-ink/50">
                  {item.allowed_person_ids.length} allowed people
                </p>
                <div className="mt-4 flex gap-3">
                  <button
                    className="btn-secondary"
                    onClick={() =>
                      setForm({
                        id: item.id,
                        name: item.name,
                        description: item.description ?? "",
                        startsAt: toLocalInputValue(item.starts_at),
                        endsAt: toLocalInputValue(item.ends_at),
                        selectedPeople: item.allowed_person_ids,
                      })
                    }
                  >
                    Edit
                  </button>
                  <button className="btn-secondary" onClick={() => void deleteSession(item.id)}>
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

"use client";

import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch, readSession } from "@/lib/api";

type Person = { id: string; full_name: string };
type SessionItem = { id: string; name: string; starts_at: string; ends_at: string; allowed_person_ids: string[] };

export default function SessionsPage() {
  const [people, setPeople] = useState<Person[]>([]);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [name, setName] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [selectedPeople, setSelectedPeople] = useState<string[]>([]);

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
    loadData();
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const session = readSession();
    if (!session) return;
    await apiFetch("/sessions", {
      token: session.accessToken,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        starts_at: startsAt,
        ends_at: endsAt,
        allowed_person_ids: selectedPeople,
      }),
    });
    setName("");
    loadData();
  }

  return (
    <AppShell title="Sessions">
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <form className="glass-card p-6" onSubmit={handleSubmit}>
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Create session</p>
          <div className="mt-4 space-y-4">
            <input className="field" value={name} onChange={(event) => setName(event.target.value)} placeholder="Class or event name" />
            <input className="field" type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} />
            <input className="field" type="datetime-local" value={endsAt} onChange={(event) => setEndsAt(event.target.value)} />
            <div className="rounded-2xl border border-ink/10 bg-white p-4">
              <p className="text-sm font-semibold">Allowlist</p>
              <div className="mt-3 grid gap-2">
                {people.map((person) => (
                  <label key={person.id} className="flex items-center gap-3 text-sm">
                    <input
                      type="checkbox"
                      checked={selectedPeople.includes(person.id)}
                      onChange={(event) =>
                        setSelectedPeople((current) =>
                          event.target.checked ? [...current, person.id] : current.filter((item) => item !== person.id),
                        )
                      }
                    />
                    {person.full_name}
                  </label>
                ))}
              </div>
            </div>
            <button className="btn-primary w-full">Save session</button>
          </div>
        </form>
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Session list</p>
          <div className="mt-4 space-y-3">
            {sessions.map((item) => (
              <div key={item.id} className="rounded-2xl bg-sand p-4">
                <p className="font-semibold">{item.name}</p>
                <p className="text-sm text-ink/60">{new Date(item.starts_at).toLocaleString()} to {new Date(item.ends_at).toLocaleString()}</p>
                <p className="mt-2 text-xs uppercase tracking-[0.18em] text-ink/50">
                  {item.allowed_person_ids.length} allowed people
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}


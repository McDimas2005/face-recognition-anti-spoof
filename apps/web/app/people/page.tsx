"use client";

import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch, readSession } from "@/lib/api";

type Person = {
  id: string;
  full_name: string;
  external_id?: string | null;
  notes?: string | null;
};

export default function PeoplePage() {
  const [people, setPeople] = useState<Person[]>([]);
  const [name, setName] = useState("");
  const [externalId, setExternalId] = useState("");

  async function loadPeople() {
    const session = readSession();
    if (!session) return;
    const data = await apiFetch<Person[]>("/persons", { token: session.accessToken });
    setPeople(data);
  }

  useEffect(() => {
    loadPeople();
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const session = readSession();
    if (!session) return;
    await apiFetch("/persons", {
      token: session.accessToken,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_name: name, external_id: externalId || null }),
    });
    setName("");
    setExternalId("");
    loadPeople();
  }

  return (
    <AppShell title="People">
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <form className="glass-card p-6" onSubmit={handleSubmit}>
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Create person</p>
          <div className="mt-4 space-y-4">
            <input className="field" placeholder="Full name" value={name} onChange={(event) => setName(event.target.value)} />
            <input className="field" placeholder="External ID" value={externalId} onChange={(event) => setExternalId(event.target.value)} />
            <button className="btn-primary w-full">Save person</button>
          </div>
        </form>
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Roster</p>
          <div className="mt-4 space-y-3">
            {people.map((person) => (
              <div key={person.id} className="rounded-2xl bg-sand p-4">
                <p className="font-semibold">{person.full_name}</p>
                <p className="text-sm text-ink/60">{person.external_id || "No external ID"}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}


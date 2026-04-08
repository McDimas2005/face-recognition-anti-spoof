"use client";

import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch, readSession } from "@/lib/api";

type Person = { id: string; full_name: string };
type Batch = { id: string; person_id: string; status: string; diversity_status: Record<string, boolean>; quality_summary: Record<string, unknown> };

const diversityTags = [
  "frontal_neutral",
  "left_yaw",
  "right_yaw",
  "expression",
  "lighting",
];

export default function EnrollmentsPage() {
  const [people, setPeople] = useState<Person[]>([]);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [personId, setPersonId] = useState("");
  const [tag, setTag] = useState(diversityTags[0]);
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => {
    const session = readSession();
    if (!session) return;
    apiFetch<Person[]>("/persons", { token: session.accessToken }).then((response) => {
      setPeople(response);
      setPersonId(response[0]?.id ?? "");
    });
  }, []);

  async function createBatch() {
    const session = readSession();
    if (!session || !personId) return;
    const response = await apiFetch<Batch>("/enrollments/batches", {
      token: session.accessToken,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ person_id: personId }),
    });
    setBatch(response);
  }

  async function uploadSample(event: FormEvent) {
    event.preventDefault();
    if (!batch || !file) return;
    const session = readSession();
    if (!session) return;
    const formData = new FormData();
    formData.append("diversity_tag", tag);
    formData.append("image", file);
    await apiFetch(`/enrollments/batches/${batch.id}/samples`, {
      token: session.accessToken,
      method: "POST",
      body: formData,
    });
    const refreshed = await apiFetch<Batch>(`/enrollments/batches/${batch.id}`, { token: session.accessToken });
    setBatch(refreshed);
    setFile(null);
  }

  return (
    <AppShell title="Enrollments">
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-6">
          <div className="glass-card p-6">
            <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Batch setup</p>
            <div className="mt-4 space-y-4">
              <select className="field" value={personId} onChange={(event) => setPersonId(event.target.value)}>
                {people.map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.full_name}
                  </option>
                ))}
              </select>
              <button className="btn-primary w-full" onClick={createBatch}>
                Create enrollment batch
              </button>
            </div>
          </div>
          <form className="glass-card p-6" onSubmit={uploadSample}>
            <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Upload sample</p>
            <div className="mt-4 space-y-4">
              <select className="field" value={tag} onChange={(event) => setTag(event.target.value)}>
                {diversityTags.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
              <input className="field" type="file" accept="image/*" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
              <button className="btn-primary w-full" disabled={!batch || !file}>
                Submit sample
              </button>
            </div>
          </form>
        </div>
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Batch status</p>
          {batch ? (
            <div className="mt-4 space-y-4">
              <p className="text-2xl font-semibold capitalize">{batch.status}</p>
              <pre className="overflow-auto rounded-2xl bg-ink p-4 text-xs text-sand">
                {JSON.stringify(batch.diversity_status, null, 2)}
              </pre>
              <pre className="overflow-auto rounded-2xl bg-ink p-4 text-xs text-sand">
                {JSON.stringify(batch.quality_summary, null, 2)}
              </pre>
            </div>
          ) : (
            <p className="mt-4 text-sm text-ink/60">Create a batch before uploading samples.</p>
          )}
        </div>
      </div>
    </AppShell>
  );
}


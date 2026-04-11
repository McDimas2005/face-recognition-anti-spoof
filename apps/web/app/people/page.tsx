"use client";

import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch, readSession } from "@/lib/api";

type Person = {
  id: string;
  full_name: string;
  external_id?: string | null;
  notes?: string | null;
  is_active?: boolean;
  owner_user_id?: string | null;
};

const defaultForm = {
  id: "",
  full_name: "",
  external_id: "",
  notes: "",
  is_active: true,
};

export default function PeoplePage() {
  const [people, setPeople] = useState<Person[]>([]);
  const [form, setForm] = useState(defaultForm);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const editing = Boolean(form.id);

  async function loadPeople() {
    const session = readSession();
    if (!session) return;
    const data = await apiFetch<Person[]>("/persons", { token: session.accessToken });
    setPeople(data);
  }

  useEffect(() => {
    void loadPeople();
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
    try {
      if (editing) {
        await apiFetch(`/persons/${form.id}`, {
          token: session.accessToken,
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            full_name: form.full_name,
            external_id: form.external_id || null,
            notes: form.notes || null,
            is_active: form.is_active,
          }),
        });
        setMessage("Person updated.");
      } else {
        await apiFetch("/persons", {
          token: session.accessToken,
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            full_name: form.full_name,
            external_id: form.external_id || null,
            notes: form.notes || null,
          }),
        });
        setMessage("Person created.");
      }
      resetForm();
      await loadPeople();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to save person");
    }
  }

  async function deletePerson(personId: string) {
    const session = readSession();
    if (!session || !window.confirm("Delete this person and their related enrollment/session links?")) return;
    setError(null);
    setMessage(null);
    try {
      await apiFetch(`/persons/${personId}`, {
        token: session.accessToken,
        method: "DELETE",
      });
      if (form.id === personId) resetForm();
      setMessage("Person deleted.");
      await loadPeople();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to delete person");
    }
  }

  return (
    <AppShell title="People">
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <form className="glass-card p-6" onSubmit={handleSubmit}>
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">{editing ? "Edit person" : "Create person"}</p>
          <div className="mt-4 space-y-4">
            <input
              className="field"
              placeholder="Full name"
              value={form.full_name}
              onChange={(event) => setForm((current) => ({ ...current, full_name: event.target.value }))}
            />
            <input
              className="field"
              placeholder="External ID"
              value={form.external_id}
              onChange={(event) => setForm((current) => ({ ...current, external_id: event.target.value }))}
            />
            <textarea
              className="field min-h-28"
              placeholder="Notes"
              value={form.notes}
              onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
            />
            {editing ? (
              <label className="flex items-center gap-3 text-sm text-ink/75">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))}
                />
                Active person
              </label>
            ) : null}
            {message ? <p className="text-sm text-emerald-700">{message}</p> : null}
            {error ? <p className="text-sm text-warning">{error}</p> : null}
            <div className="flex gap-3">
              <button className="btn-primary flex-1">{editing ? "Save changes" : "Save person"}</button>
              {editing ? (
                <button type="button" className="btn-secondary flex-1" onClick={resetForm}>
                  Cancel
                </button>
              ) : null}
            </div>
          </div>
        </form>
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Roster</p>
          <div className="mt-4 space-y-3">
            {people.map((person) => (
              <div key={person.id} className="rounded-2xl bg-sand p-4">
                <p className="font-semibold">{person.full_name}</p>
                <p className="text-sm text-ink/60">{person.external_id || "No external ID"}</p>
                <p className="text-sm text-ink/55">{person.notes || "No notes"}</p>
                <p className="mt-2 text-xs uppercase tracking-[0.18em] text-ink/45">
                  {(person.is_active ?? true) ? "active" : "inactive"} {person.owner_user_id ? "/ owned self-enrollment identity" : ""}
                </p>
                <div className="mt-4 flex gap-3">
                  <button
                    className="btn-secondary"
                    onClick={() =>
                      setForm({
                        id: person.id,
                        full_name: person.full_name,
                        external_id: person.external_id ?? "",
                        notes: person.notes ?? "",
                        is_active: person.is_active ?? true,
                      })
                    }
                  >
                    Edit
                  </button>
                  <button className="btn-secondary" onClick={() => void deletePerson(person.id)}>
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

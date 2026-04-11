"use client";

import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch, readSession } from "@/lib/api";

type UserItem = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
};

const defaultForm = {
  id: "",
  email: "",
  full_name: "",
  password: "",
  role: "reviewer",
  is_active: true,
};

export default function UsersPage() {
  const [users, setUsers] = useState<UserItem[]>([]);
  const [form, setForm] = useState(defaultForm);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const editing = Boolean(form.id);

  async function loadUsers() {
    const session = readSession();
    if (!session) return;
    const response = await apiFetch<UserItem[]>("/users", { token: session.accessToken });
    setUsers(response);
  }

  useEffect(() => {
    void loadUsers();
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
        await apiFetch(`/users/${form.id}`, {
          token: session.accessToken,
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: form.email,
            full_name: form.full_name,
            password: form.password || undefined,
            role: form.role,
            is_active: form.is_active,
          }),
        });
        setMessage("User updated.");
      } else {
        await apiFetch("/users", {
          token: session.accessToken,
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: form.email,
            full_name: form.full_name,
            password: form.password,
            role: form.role,
          }),
        });
        setMessage("User created.");
      }
      resetForm();
      await loadUsers();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to save user");
    }
  }

  async function deleteUser(userId: string) {
    const session = readSession();
    if (!session || !window.confirm("Delete this user?")) return;
    setError(null);
    setMessage(null);
    try {
      await apiFetch(`/users/${userId}`, {
        token: session.accessToken,
        method: "DELETE",
      });
      if (form.id === userId) resetForm();
      setMessage("User deleted.");
      await loadUsers();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to delete user");
    }
  }

  return (
    <AppShell title="Users">
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <form className="glass-card p-6" onSubmit={handleSubmit}>
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">{editing ? "Edit user" : "Create user"}</p>
          <div className="mt-4 space-y-4">
            <input
              className="field"
              value={form.full_name}
              onChange={(event) => setForm((current) => ({ ...current, full_name: event.target.value }))}
              placeholder="Full name"
            />
            <input
              className="field"
              value={form.email}
              onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
              placeholder="Email"
            />
            <input
              className="field"
              type="password"
              value={form.password}
              onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
              placeholder={editing ? "New password (optional)" : "Password"}
            />
            <select className="field" value={form.role} onChange={(event) => setForm((current) => ({ ...current, role: event.target.value }))}>
              <option value="superadmin">superadmin</option>
              <option value="admin">admin</option>
              <option value="reviewer">reviewer</option>
              <option value="viewer">viewer</option>
            </select>
            {editing ? (
              <label className="flex items-center gap-3 text-sm text-ink/75">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))}
                />
                Active user
              </label>
            ) : null}
            {message ? <p className="text-sm text-emerald-700">{message}</p> : null}
            {error ? <p className="text-sm text-warning">{error}</p> : null}
            <div className="flex gap-3">
              <button className="btn-primary flex-1">{editing ? "Save changes" : "Create user"}</button>
              {editing ? (
                <button type="button" className="btn-secondary flex-1" onClick={resetForm}>
                  Cancel
                </button>
              ) : null}
            </div>
          </div>
        </form>
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">User directory</p>
          <div className="mt-4 space-y-3">
            {users.map((user) => (
              <div key={user.id} className="rounded-2xl bg-sand p-4">
                <p className="font-semibold">{user.full_name}</p>
                <p className="text-sm text-ink/60">{user.email}</p>
                <p className="text-xs uppercase tracking-[0.18em] text-ink/45">
                  {user.role} / {user.is_active ? "active" : "inactive"}
                </p>
                <div className="mt-4 flex gap-3">
                  <button
                    className="btn-secondary"
                    onClick={() =>
                      setForm({
                        id: user.id,
                        email: user.email,
                        full_name: user.full_name,
                        password: "",
                        role: user.role,
                        is_active: user.is_active,
                      })
                    }
                  >
                    Edit
                  </button>
                  <button className="btn-secondary" onClick={() => void deleteUser(user.id)}>
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

"use client";

import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch, readSession } from "@/lib/api";

type UserItem = {
  id: string;
  email: string;
  full_name: string;
  role: string;
};

export default function UsersPage() {
  const [users, setUsers] = useState<UserItem[]>([]);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("reviewer");

  async function loadUsers() {
    const session = readSession();
    if (!session) return;
    const response = await apiFetch<UserItem[]>("/users", { token: session.accessToken });
    setUsers(response);
  }

  useEffect(() => {
    loadUsers();
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const session = readSession();
    if (!session) return;
    await apiFetch("/users", {
      token: session.accessToken,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, full_name: fullName, password, role }),
    });
    setEmail("");
    setFullName("");
    setPassword("");
    setRole("reviewer");
    loadUsers();
  }

  return (
    <AppShell title="Users">
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <form className="glass-card p-6" onSubmit={handleSubmit}>
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Create user</p>
          <div className="mt-4 space-y-4">
            <input className="field" value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Full name" />
            <input className="field" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email" />
            <input className="field" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password" />
            <select className="field" value={role} onChange={(event) => setRole(event.target.value)}>
              <option value="admin">admin</option>
              <option value="reviewer">reviewer</option>
              <option value="viewer">viewer</option>
            </select>
            <button className="btn-primary w-full">Create user</button>
          </div>
        </form>
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">User directory</p>
          <div className="mt-4 space-y-3">
            {users.map((user) => (
              <div key={user.id} className="rounded-2xl bg-sand p-4">
                <p className="font-semibold">{user.full_name}</p>
                <p className="text-sm text-ink/60">{user.email}</p>
                <p className="text-xs uppercase tracking-[0.18em] text-ink/45">{user.role}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}


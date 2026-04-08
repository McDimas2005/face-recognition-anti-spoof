"use client";

import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch, readSession } from "@/lib/api";

type SettingsPayload = {
  recognition_policy: Record<string, unknown>;
  retention_policy: Record<string, unknown>;
};

export default function SettingsPage() {
  const [payload, setPayload] = useState<SettingsPayload>({
    recognition_policy: {},
    retention_policy: {},
  });
  const [recognitionText, setRecognitionText] = useState("{}");
  const [retentionText, setRetentionText] = useState("{}");

  useEffect(() => {
    const session = readSession();
    if (!session) return;
    apiFetch<SettingsPayload>("/settings", { token: session.accessToken }).then((response) => {
      setPayload(response);
      setRecognitionText(JSON.stringify(response.recognition_policy, null, 2));
      setRetentionText(JSON.stringify(response.retention_policy, null, 2));
    });
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const session = readSession();
    if (!session) return;
    const parsed = {
      recognition_policy: JSON.parse(recognitionText || "{}"),
      retention_policy: JSON.parse(retentionText || "{}"),
    };
    setPayload(parsed);
    await apiFetch("/settings", {
      token: session.accessToken,
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parsed),
    });
  }

  return (
    <AppShell title="Settings">
      <form className="grid gap-6 lg:grid-cols-2" onSubmit={handleSubmit}>
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Recognition policy</p>
          <textarea
            className="field mt-4 min-h-80 font-mono text-sm"
            value={recognitionText}
            onChange={(event) => setRecognitionText(event.target.value)}
          />
        </div>
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Retention policy</p>
          <textarea
            className="field mt-4 min-h-80 font-mono text-sm"
            value={retentionText}
            onChange={(event) => setRetentionText(event.target.value)}
          />
        </div>
        <button className="btn-primary lg:col-span-2">Save settings</button>
      </form>
    </AppShell>
  );
}

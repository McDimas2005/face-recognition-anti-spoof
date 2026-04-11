"use client";

import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch, readSession } from "@/lib/api";

type RecognitionPolicy = {
  similarity_threshold: number;
  commit_threshold: number;
  ambiguity_margin: number;
  liveness_threshold: number;
  consensus_frames: number;
  consensus_window_seconds: number;
};

type QualityPolicy = {
  min_face_size: number;
  min_brightness: number;
  max_brightness: number;
  blur_threshold: number;
  max_yaw_score: number;
  max_occlusion_score: number;
};

type RetentionPolicy = {
  retain_enrollment_images: boolean;
  retain_review_images: boolean;
  privacy_notice: string;
};

type SettingsPayload = {
  recognition_policy: RecognitionPolicy;
  quality_policy: QualityPolicy;
  retention_policy: RetentionPolicy;
  can_edit_settings: boolean;
  can_edit_all: boolean;
};

export default function SettingsPage() {
  const [payload, setPayload] = useState<SettingsPayload | null>(null);
  const [recognitionText, setRecognitionText] = useState("{}");
  const [qualityText, setQualityText] = useState("{}");
  const [retentionText, setRetentionText] = useState("{}");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const session = readSession();
    if (!session) return;
    apiFetch<SettingsPayload>("/settings", { token: session.accessToken }).then((response) => {
      setPayload(response);
      setRecognitionText(JSON.stringify(response.recognition_policy, null, 2));
      setQualityText(JSON.stringify(response.quality_policy, null, 2));
      setRetentionText(JSON.stringify(response.retention_policy, null, 2));
    });
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const session = readSession();
    if (!session || !payload?.can_edit_settings) return;
    setError(null);
    setStatus(null);
    try {
      const parsed = {
        recognition_policy: JSON.parse(recognitionText || "{}"),
        retention_policy: JSON.parse(retentionText || "{}"),
        ...(payload.can_edit_all ? { quality_policy: JSON.parse(qualityText || "{}") } : {}),
      };
      const response = await apiFetch<SettingsPayload>("/settings", {
        token: session.accessToken,
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed),
      });
      setPayload(response);
      setRecognitionText(JSON.stringify(response.recognition_policy, null, 2));
      setQualityText(JSON.stringify(response.quality_policy, null, 2));
      setRetentionText(JSON.stringify(response.retention_policy, null, 2));
      setStatus("Settings saved.");
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "Failed to save settings");
    }
  }

  const canEditSettings = payload?.can_edit_settings ?? false;
  const canEditAll = payload?.can_edit_all ?? false;

  return (
    <AppShell title="Settings">
      <form className="grid gap-6 xl:grid-cols-3" onSubmit={handleSubmit}>
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Recognition policy</p>
          <textarea
            className="field mt-4 min-h-80 font-mono text-sm"
            value={recognitionText}
            onChange={(event) => setRecognitionText(event.target.value)}
            disabled={!canEditSettings}
          />
        </div>
        <div className="glass-card p-6">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Quality policy</p>
            {!canEditAll ? <span className="pill">Super Admin</span> : null}
          </div>
          <textarea
            className="field mt-4 min-h-80 font-mono text-sm"
            value={qualityText}
            onChange={(event) => setQualityText(event.target.value)}
            disabled={!canEditAll}
          />
          <p className="mt-3 text-sm text-ink/55">
            Face-size, brightness, blur, yaw, and occlusion thresholds are only editable by Super Admin.
          </p>
        </div>
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Retention policy</p>
          <textarea
            className="field mt-4 min-h-80 font-mono text-sm"
            value={retentionText}
            onChange={(event) => setRetentionText(event.target.value)}
            disabled={!canEditSettings}
          />
        </div>
        <div className="xl:col-span-3">
          {error ? <p className="mb-3 text-sm text-rose-700">{error}</p> : null}
          {status ? <p className="mb-3 text-sm text-emerald-700">{status}</p> : null}
          {!canEditSettings ? (
            <p className="mb-3 text-sm text-ink/60">This account can view settings but cannot update them.</p>
          ) : null}
          <button className="btn-primary" disabled={!canEditSettings}>
            Save settings
          </button>
        </div>
      </form>
    </AppShell>
  );
}

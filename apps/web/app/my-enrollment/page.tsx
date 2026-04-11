"use client";

import { useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch, readSession } from "@/lib/api";

type BatchSummary = {
  id: string;
  person_id: string;
  status: string;
  is_active: boolean;
  is_self_enrollment: boolean;
  bypass_quality_validation: boolean;
  target_sample_count: number;
  replacement_for_batch_id?: string | null;
  diversity_status: Record<string, boolean>;
  quality_summary: Record<string, unknown>;
  accepted_sample_count: number;
  total_sample_count: number;
  remaining_sample_count: number;
  last_sample_id?: string | null;
  created_at: string;
  finalized_at?: string | null;
};

type StatusResponse = {
  person: {
    id: string;
    full_name: string;
    owner_user_id?: string | null;
  };
  active_batch: BatchSummary | null;
  draft_batch: BatchSummary | null;
  quality_bypass_allowed: boolean;
  target_sample_count: number;
};

type FrameResponse = {
  batch: BatchSummary;
  sample: {
    id: string;
    quality_score?: number;
    rejection_reason?: string | null;
    metadata_json: Record<string, unknown>;
  };
  accepted: boolean;
  message: string;
};

type FaceBox = {
  x: number;
  y: number;
  width: number;
  height: number;
  image_width: number;
  image_height: number;
  confidence?: number;
};

const AUTO_CAPTURE_INTERVAL_MS = 1400;
const CAPTURE_STAGES = [
  "Keep your face centered and look straight into the camera.",
  "Turn slightly to your left while keeping your face visible.",
  "Turn slightly to your right while keeping your face visible.",
  "Vary your expression while staying in frame.",
  "Keep your face visible and vary your lighting or distance a little.",
];

function formatDate(value?: string | null) {
  if (!value) return "Not available";
  return new Date(value).toLocaleString();
}

function stageInstruction(batch: BatchSummary | null, targetSampleCount: number) {
  const accepted = batch?.accepted_sample_count ?? 0;
  const bucketSize = Math.max(1, Math.floor(targetSampleCount / CAPTURE_STAGES.length));
  const index = Math.min(Math.floor(accepted / bucketSize), CAPTURE_STAGES.length - 1);
  return CAPTURE_STAGES[index];
}

function readFaceBox(metadata: Record<string, unknown>): FaceBox | null {
  const box = metadata.face_box;
  if (!box || typeof box !== "object") return null;
  const candidate = box as Partial<FaceBox>;
  if (
    typeof candidate.x !== "number" ||
    typeof candidate.y !== "number" ||
    typeof candidate.width !== "number" ||
    typeof candidate.height !== "number" ||
    typeof candidate.image_width !== "number" ||
    typeof candidate.image_height !== "number"
  ) {
    return null;
  }
  return candidate as FaceBox;
}

export default function MyEnrollmentPage() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [batch, setBatch] = useState<BatchSummary | null>(null);
  const [bypassQuality, setBypassQuality] = useState(false);
  const [captureState, setCaptureState] = useState<"idle" | "running" | "paused">("idle");
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [faceBox, setFaceBox] = useState<FaceBox | null>(null);
  const [lastQualityPercent, setLastQualityPercent] = useState<number | null>(null);
  const [lastDetectorPercent, setLastDetectorPercent] = useState<number | null>(null);
  const [confirmStartOpen, setConfirmStartOpen] = useState(false);
  const [confirmReplaceOpen, setConfirmReplaceOpen] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<number | null>(null);
  const captureInFlightRef = useRef(false);

  async function loadStatus() {
    const session = readSession();
    if (!session) return;
    const response = await apiFetch<StatusResponse>("/me/enrollment/live", {
      token: session.accessToken,
    });
    setStatus(response);
    setBatch(response.draft_batch);
    setBypassQuality(response.draft_batch?.bypass_quality_validation ?? false);
  }

  async function ensureCamera() {
    if (streamRef.current) return;
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    streamRef.current = stream;
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
    }
  }

  function stopLoop() {
    if (intervalRef.current) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }

  function stopCamera() {
    stopLoop();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  async function captureFrame() {
    if (!batch || captureInFlightRef.current || submitting) return;
    if (!videoRef.current || !canvasRef.current) return;
    if (batch.accepted_sample_count >= batch.target_sample_count) {
      setCaptureState("paused");
      stopLoop();
      return;
    }

    captureInFlightRef.current = true;
    try {
      const session = readSession();
      if (!session) return;

      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (
        video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA ||
        video.videoWidth <= 0 ||
        video.videoHeight <= 0
      ) {
        return;
      }

      const width = video.videoWidth;
      const height = video.videoHeight;
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Canvas context is not available");

      context.drawImage(video, 0, 0, width, height);
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
      if (!blob) throw new Error("Unable to capture frame");

      const formData = new FormData();
      formData.append("batch_id", batch.id);
      formData.append("image", blob, `enrollment-${Date.now()}.jpg`);

      const response = await apiFetch<FrameResponse>("/me/enrollment/live/frame", {
        token: session.accessToken,
        method: "POST",
        body: formData,
      });
      setBatch(response.batch);
      setFaceBox(readFaceBox(response.sample.metadata_json));
      setLastQualityPercent(
        typeof response.sample.metadata_json.quality_score === "number"
          ? Math.round(Number(response.sample.metadata_json.quality_score) * 100)
          : null,
      );
      setLastDetectorPercent(
        typeof response.sample.metadata_json.detector_confidence === "number"
          ? Math.round(Number(response.sample.metadata_json.detector_confidence) * 100)
          : null,
      );
      setMessage(
        response.accepted
          ? `Accepted ${response.batch.accepted_sample_count}/${response.batch.target_sample_count}`
          : `Rejected: ${response.sample.rejection_reason ?? response.message}`,
      );
      setError(null);

      if (response.batch.accepted_sample_count >= response.batch.target_sample_count) {
        setCaptureState("paused");
        stopLoop();
      }
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to capture frame");
      setFaceBox(null);
      setLastQualityPercent(null);
      setLastDetectorPercent(null);
      setCaptureState("paused");
      stopLoop();
    } finally {
      captureInFlightRef.current = false;
    }
  }

  async function startNewBatch() {
    setSubmitting(true);
    setError(null);
    try {
      const session = readSession();
      if (!session) return;
      const response = await apiFetch<{ batch: BatchSummary }>("/me/enrollment/live/start", {
        token: session.accessToken,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bypass_quality_validation: bypassQuality }),
      });
      setBatch(response.batch);
      setMessage("Self-enrollment batch started. Capture 100 accepted frames before replacement.");
      setConfirmStartOpen(false);
      await ensureCamera();
      setCaptureState("running");
      await loadStatus();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to start self-enrollment");
    } finally {
      setSubmitting(false);
    }
  }

  async function finalizeBatch() {
    if (!batch) return;
    setSubmitting(true);
    setError(null);
    try {
      const session = readSession();
      if (!session) return;
      const response = await apiFetch<{ batch: BatchSummary; active_sample_count: number }>("/me/enrollment/live/finalize", {
        token: session.accessToken,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ batch_id: batch.id, confirm_replace: true }),
      });
      setMessage(`Enrollment replaced successfully with ${response.active_sample_count} active photos.`);
      setConfirmReplaceOpen(false);
      setCaptureState("paused");
      stopLoop();
      await loadStatus();
      setBatch(response.batch);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to finalize self-enrollment");
    } finally {
      setSubmitting(false);
    }
  }

  async function retakeLastFrame() {
    if (!batch?.last_sample_id) return;
    setSubmitting(true);
    setError(null);
    try {
      const session = readSession();
      if (!session) return;
      const response = await apiFetch<{ batch: BatchSummary }>("/me/enrollment/live/samples/" + batch.last_sample_id, {
        token: session.accessToken,
        method: "DELETE",
      });
      setBatch(response.batch);
      setFaceBox(null);
      setLastQualityPercent(null);
      setLastDetectorPercent(null);
      setMessage("Last captured frame removed. Capture again when ready.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to retake last frame");
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    loadStatus()
      .catch((caughtError) => setError(caughtError instanceof Error ? caughtError.message : "Failed to load status"))
      .finally(() => setLoading(false));
    return () => stopCamera();
  }, []);

  useEffect(() => {
    if (captureState !== "running" || !batch) {
      stopLoop();
      return;
    }
    if (intervalRef.current) return;
    intervalRef.current = window.setInterval(() => {
      void captureFrame();
    }, AUTO_CAPTURE_INTERVAL_MS);
    return () => stopLoop();
  }, [batch, captureState, submitting]);

  const activeBatch = status?.active_batch ?? null;
  const targetSampleCount = status?.target_sample_count ?? 100;
  const progress = batch ? Math.min(100, (batch.accepted_sample_count / batch.target_sample_count) * 100) : 0;
  const experimentalMode = batch?.bypass_quality_validation ?? bypassQuality;
  const isDraftBatch = !!batch && batch.status === "incomplete";
  const canFinalize = !!batch && batch.status === "ready" && !batch.is_active;

  return (
    <AppShell title="My Enrollment">
      <canvas ref={canvasRef} className="hidden" />
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-6">
          <div className="glass-card overflow-hidden">
            <div className="border-b border-ink/10 px-6 py-5">
              <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Live capture</p>
              <h3 className="mt-2 text-2xl font-semibold tracking-tight">
                {status?.person.full_name ?? "Preparing self-enrollment"}
              </h3>
              <p className="mt-2 text-sm text-ink/65">
                Capture a fresh set of {targetSampleCount} live webcam photos. The new set replaces your current active enrollment only after final confirmation.
              </p>
            </div>
            <div className="p-6">
              <div className="relative overflow-hidden rounded-[28px] bg-ink">
                <video ref={videoRef} playsInline muted className="aspect-video w-full object-contain" />
                {faceBox ? (
                  <div
                    className="pointer-events-none absolute border-4 border-emerald-400 shadow-[0_0_0_9999px_rgba(0,0,0,0.08)]"
                    style={{
                      left: `${(faceBox.x / faceBox.image_width) * 100}%`,
                      top: `${(faceBox.y / faceBox.image_height) * 100}%`,
                      width: `${(faceBox.width / faceBox.image_width) * 100}%`,
                      height: `${(faceBox.height / faceBox.image_height) * 100}%`,
                    }}
                  >
                    <div className="absolute -top-10 left-0 rounded-xl bg-emerald-500 px-3 py-2 text-xs font-semibold text-white">
                      Face {lastQualityPercent ?? lastDetectorPercent ?? 0}%
                    </div>
                  </div>
                ) : null}
                <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-ink/85 to-transparent px-5 py-4 text-sm text-white">
                  <span>{batch ? stageInstruction(batch, targetSampleCount) : "Start a new batch to enable live capture."}</span>
                  <span>{captureState === "running" ? "Capturing" : captureState === "paused" ? "Paused" : "Idle"}</span>
                </div>
              </div>

              {experimentalMode ? (
                <div className="mt-4 rounded-3xl border border-amber-400/40 bg-amber-50 px-4 py-4 text-sm text-amber-900">
                  Experimental mode is enabled. Low-quality single-face enrollment frames may be accepted, which can reduce recognition reliability.
                </div>
              ) : null}

              {message ? <div className="mt-4 rounded-3xl bg-sand px-4 py-4 text-sm text-ink/80">{message}</div> : null}
              {error ? <div className="mt-4 rounded-3xl border border-red-300 bg-red-50 px-4 py-4 text-sm text-red-700">{error}</div> : null}

              <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                <button
                  className="btn-primary"
                  disabled={submitting}
                  onClick={() => setConfirmStartOpen(true)}
                >
                  {batch ? "Start new batch" : "Start capture"}
                </button>
                <button
                  className="btn-secondary"
                  disabled={!isDraftBatch || submitting || captureState === "running"}
                  onClick={async () => {
                    try {
                      await ensureCamera();
                      setCaptureState("running");
                    } catch (caughtError) {
                      setError(caughtError instanceof Error ? caughtError.message : "Camera access failed");
                    }
                  }}
                >
                  Resume
                </button>
                <button
                  className="btn-secondary"
                  disabled={!isDraftBatch || captureState !== "running"}
                  onClick={() => {
                    setCaptureState("paused");
                    stopLoop();
                  }}
                >
                  Pause
                </button>
                <button className="btn-secondary" disabled={!isDraftBatch || submitting} onClick={() => void captureFrame()}>
                  Capture now
                </button>
                <button className="btn-secondary" disabled={!isDraftBatch || !batch?.last_sample_id || submitting} onClick={() => void retakeLastFrame()}>
                  Retake last
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="glass-card p-6">
            <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Replacement rules</p>
            <div className="mt-4 space-y-3 text-sm text-ink/75">
              <p>Only your owned identity can be enrolled from this page.</p>
              <p>Recognition keeps using your current active enrollment until you finalize the new batch.</p>
              <p>The active enrollment set is capped at 100 photos after replacement.</p>
            </div>
          </div>

          <div className="glass-card p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Progress</p>
                <h3 className="mt-2 text-3xl font-semibold tracking-tight">{batch?.accepted_sample_count ?? 0}/{targetSampleCount}</h3>
              </div>
              <div className="text-right text-sm text-ink/60">
                <p>Remaining</p>
                <p className="mt-1 text-xl font-semibold text-ink">{batch?.remaining_sample_count ?? targetSampleCount}</p>
              </div>
            </div>
            <div className="mt-5 h-4 rounded-full bg-sand">
              <div className="h-full rounded-full bg-ink transition-all" style={{ width: `${progress}%` }} />
            </div>
            <div className="mt-5 space-y-3 text-sm text-ink/70">
              <p>Current instruction: {stageInstruction(batch, targetSampleCount)}</p>
              <p>Accepted frames: {batch?.accepted_sample_count ?? 0}</p>
              <p>Total attempts: {batch?.total_sample_count ?? 0}</p>
              <p>Last face quality: {lastQualityPercent !== null ? `${lastQualityPercent}%` : "n/a"}</p>
              <p>Last detector confidence: {lastDetectorPercent !== null ? `${lastDetectorPercent}%` : "n/a"}</p>
            </div>
          </div>

          <div className="glass-card p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Quality validation</p>
                <h3 className="mt-2 text-xl font-semibold tracking-tight">Bypass quality validation</h3>
                <p className="mt-2 text-sm text-ink/60">
                  Single-face frames with weak quality can be accepted in experimental mode. No-face and multi-face captures are still rejected.
                </p>
              </div>
              <label className="inline-flex cursor-pointer items-center gap-3">
                <span className="text-sm text-ink/70">Experimental</span>
                <input
                  type="checkbox"
                  className="h-5 w-5 accent-ink"
                  disabled={!!batch || !status?.quality_bypass_allowed}
                  checked={bypassQuality}
                  onChange={(event) => setBypassQuality(event.target.checked)}
                />
              </label>
            </div>
            {!status?.quality_bypass_allowed ? (
              <p className="mt-4 rounded-2xl bg-sand px-4 py-3 text-sm text-ink/70">
                Quality bypass is limited to non-production environments or admin users.
              </p>
            ) : null}
          </div>

          <div className="glass-card p-6">
            <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Current active enrollment</p>
            {activeBatch ? (
              <div className="mt-4 space-y-3 text-sm text-ink/75">
                <p>Last finalized: {formatDate(activeBatch.finalized_at ?? activeBatch.created_at)}</p>
                <p>Active photos: {activeBatch.accepted_sample_count}</p>
                <p>Mode: {activeBatch.bypass_quality_validation ? "Experimental quality bypass" : "Standard quality validation"}</p>
              </div>
            ) : (
              <p className="mt-4 text-sm text-ink/60">No active enrollment exists yet for this user.</p>
            )}
            <button
              className="btn-primary mt-6 w-full"
              disabled={!canFinalize || submitting}
              onClick={() => setConfirmReplaceOpen(true)}
            >
              Replace my current enrollment
            </button>
          </div>
        </div>
      </div>

      {confirmStartOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/45 px-6">
          <div className="glass-card w-full max-w-xl p-6">
            <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Start replacement batch</p>
            <h3 className="mt-3 text-2xl font-semibold tracking-tight">Create a new self-enrollment batch?</h3>
            <div className="mt-4 space-y-3 text-sm text-ink/70">
              <p>Your current active enrollment stays in use until the new batch reaches 100 accepted photos and you finalize replacement.</p>
              <p>Starting a new batch archives any unfinished self-enrollment draft for your user.</p>
            </div>
            <div className="mt-6 flex gap-3">
              <button className="btn-primary flex-1" disabled={submitting} onClick={() => void startNewBatch()}>
                Confirm start
              </button>
              <button className="btn-secondary flex-1" disabled={submitting} onClick={() => setConfirmStartOpen(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {confirmReplaceOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/45 px-6">
          <div className="glass-card w-full max-w-xl p-6">
            <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Finalize replacement</p>
            <h3 className="mt-3 text-2xl font-semibold tracking-tight">Replace your active enrollment now?</h3>
            <div className="mt-4 space-y-3 text-sm text-ink/70">
              <p>This activates the newly captured batch and deactivates your previous active enrollment photos for recognition.</p>
              <p>Only the new 100-photo set remains active after the swap.</p>
            </div>
            <div className="mt-6 flex gap-3">
              <button className="btn-primary flex-1" disabled={submitting} onClick={() => void finalizeBatch()}>
                Confirm replace
              </button>
              <button className="btn-secondary flex-1" disabled={submitting} onClick={() => setConfirmReplaceOpen(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {loading ? <div className="glass-card mt-6 p-6 text-sm text-ink/60">Loading enrollment state...</div> : null}
    </AppShell>
  );
}

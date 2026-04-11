"use client";

import { useEffect, useRef, useState } from "react";

import { apiFetch, readSession } from "@/lib/api";

type SessionOption = {
  id: string;
  name: string;
};

type RecognitionResult = {
  state: string;
  top_person_id?: string | null;
  top_person_name?: string | null;
  top_score?: number | null;
  breakdown: Record<string, unknown>;
  attendance_event_id?: string | null;
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

function readFaceBox(breakdown: Record<string, unknown>): FaceBox | null {
  const box = breakdown.face_box;
  if (!box || typeof box !== "object") {
    return null;
  }
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

export function AttendanceCamera({ sessions }: { sessions: SessionOption[] }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [selectedSession, setSelectedSession] = useState(sessions[0]?.id ?? "");
  const [status, setStatus] = useState<string>("idle");
  const [result, setResult] = useState<RecognitionResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [faceBox, setFaceBox] = useState<FaceBox | null>(null);

  useEffect(() => {
    if (!selectedSession && sessions[0]?.id) {
      setSelectedSession(sessions[0].id);
    }
  }, [selectedSession, sessions]);

  useEffect(() => {
    let stream: MediaStream | null = null;
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "user" }, audio: false })
      .then((mediaStream) => {
        stream = mediaStream;
        if (videoRef.current) {
          videoRef.current.srcObject = mediaStream;
        }
      })
      .catch(() => setStatus("camera_error"));

    return () => {
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  useEffect(() => {
    if (!running || !selectedSession) {
      return;
    }

    const interval = window.setInterval(async () => {
      const session = readSession();
      if (!session || !videoRef.current || !canvasRef.current) {
        return;
      }

      const video = videoRef.current;
      const canvas = canvasRef.current;
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      const context = canvas.getContext("2d");
      if (!context) {
        return;
      }

      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise<Blob | null>((resolve) =>
        canvas.toBlob(resolve, "image/jpeg", 0.85),
      );
      if (!blob) {
        return;
      }

      setStatus("processing");
      const formData = new FormData();
      formData.append("session_id", selectedSession);
      formData.append("client_key", "browser-webcam");
      formData.append("frame", blob, "frame.jpg");

      try {
        const response = await apiFetch<RecognitionResult>("/recognition/evaluate", {
          token: session.accessToken,
          method: "POST",
          body: formData,
        });
        setStatus(response.state);
        setResult(response);
        setFaceBox(readFaceBox(response.breakdown));
        setError(null);
      } catch (caughtError) {
        setStatus("request_error");
        setFaceBox(null);
        setError(caughtError instanceof Error ? caughtError.message : "Recognition request failed");
      }
    }, 1500);

    return () => window.clearInterval(interval);
  }, [running, selectedSession]);

  const qualityPercent = typeof result?.breakdown?.quality_score === "number" ? Math.round(Number(result.breakdown.quality_score) * 100) : null;
  const matchPercent = typeof result?.breakdown?.match_percent === "number" ? Math.round(Number(result.breakdown.match_percent)) : null;
  const detectorPercent =
    typeof result?.breakdown?.detector_confidence === "number" ? Math.round(Number(result.breakdown.detector_confidence) * 100) : null;
  const recognizedName =
    result?.top_person_name ?? (typeof result?.breakdown?.top_person_name === "string" ? result.breakdown.top_person_name : null);
  const overlayLabel = recognizedName ? `${recognizedName} ${matchPercent ?? qualityPercent ?? detectorPercent ?? 0}%` : `Face ${matchPercent ?? qualityPercent ?? detectorPercent ?? 0}%`;

  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      <div className="glass-card overflow-hidden p-4">
        <div className="mb-4 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Live camera</p>
            <p className="text-sm text-ink/65">
              Attendance only commits after consistent multi-frame agreement.
            </p>
          </div>
          <div className="flex gap-3">
            <select
              value={selectedSession}
              onChange={(event) => setSelectedSession(event.target.value)}
              className="field min-w-52"
            >
              {sessions.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            <button className="btn-primary" onClick={() => setRunning((value) => !value)}>
              {running ? "Stop" : "Start"}
            </button>
          </div>
        </div>
        <div className="relative">
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className="aspect-video w-full rounded-3xl bg-ink object-contain"
          />
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
                {overlayLabel}
              </div>
            </div>
          ) : null}
        </div>
        <canvas ref={canvasRef} className="hidden" />
      </div>
      <div className="space-y-6">
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Recognition state</p>
          <p className="mt-4 text-3xl font-semibold capitalize">{status.replaceAll("_", " ")}</p>
          {recognizedName ? <p className="mt-3 text-lg font-medium text-ink">Recognized user: {recognizedName}</p> : null}
          <p className="mt-3 text-sm text-ink/65">
            States: detecting, spoof check, matched, unknown, duplicate, success, error.
          </p>
          {error ? <p className="mt-3 text-sm text-warning">{error}</p> : null}
          <div className="mt-4 space-y-2 text-sm text-ink/70">
            <p>Detector confidence: {detectorPercent !== null ? `${detectorPercent}%` : "n/a"}</p>
            <p>Face quality: {qualityPercent !== null ? `${qualityPercent}%` : "n/a"}</p>
            <p>Match score: {matchPercent !== null ? `${matchPercent}%` : "n/a"}</p>
          </div>
        </div>
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Decision breakdown</p>
          <pre className="mt-4 overflow-auto rounded-2xl bg-ink p-4 text-xs text-sand">
            {JSON.stringify(result?.breakdown ?? { note: "No result yet" }, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}

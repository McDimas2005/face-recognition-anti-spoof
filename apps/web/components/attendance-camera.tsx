"use client";

import { useEffect, useRef, useState } from "react";

import { apiFetch, readSession } from "@/lib/api";

type SessionOption = {
  id: string;
  name: string;
};

type RecognitionResult = {
  state: string;
  breakdown: Record<string, unknown>;
  attendance_event_id?: string | null;
};

export function AttendanceCamera({ sessions }: { sessions: SessionOption[] }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [selectedSession, setSelectedSession] = useState(sessions[0]?.id ?? "");
  const [status, setStatus] = useState<string>("idle");
  const [result, setResult] = useState<RecognitionResult | null>(null);
  const [running, setRunning] = useState(false);

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
      } catch {
        setStatus("request_error");
      }
    }, 1500);

    return () => window.clearInterval(interval);
  }, [running, selectedSession]);

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
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className="aspect-video w-full rounded-3xl bg-ink object-cover"
        />
        <canvas ref={canvasRef} className="hidden" />
      </div>
      <div className="space-y-6">
        <div className="glass-card p-6">
          <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Recognition state</p>
          <p className="mt-4 text-3xl font-semibold capitalize">{status.replaceAll("_", " ")}</p>
          <p className="mt-3 text-sm text-ink/65">
            States: detecting, spoof check, matched, unknown, duplicate, success, error.
          </p>
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

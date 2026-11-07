"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";

import { ACCEPT, cleanLines, readDocument, type ReadResponse } from "@/lib/scan";

type Phase =
  | { name: "pick" }
  | { name: "camera" }
  | { name: "reading"; label: string }
  | { name: "review"; result: ReadResponse; source: string }
  | { name: "error"; message: string };

function CameraIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden className={className}>
      <path
        d="M3 6.5A1.5 1.5 0 0 1 4.5 5h2l1.2-1.6A1 1 0 0 1 8.5 3h3a1 1 0 0 1 .8.4L13.5 5h2A1.5 1.5 0 0 1 17 6.5v8a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 3 14.5v-8Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <circle cx="10" cy="10.5" r="3" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

const ENGINE_LABEL: Record<string, string> = {
  "apple-vision": "read on this Mac with Apple's text recognizer",
  "pdf-text": "taken from the PDF's text",
  "pdf-text+apple-vision": "taken from the PDF (scanned pages read with Apple's text recognizer)",
  textutil: "taken from the document",
  text: "taken from the text file",
};

export interface ScanApply {
  lines: string[];
  asAnswer: boolean;
}

/**
 * "Scan work": photograph handwriting or pick a photo, PDF or document, check what was read,
 * then drop it into the step editor. Nothing is checked until the student presses Check.
 */
export function ScanDialog({
  problemKind,
  hasAnswer,
  onApply,
}: {
  problemKind: string;
  hasAnswer: boolean;
  onApply: (apply: ScanApply) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const photoInput = useRef<HTMLInputElement>(null);
  const textArea = useRef<HTMLTextAreaElement>(null);
  const ids = useId();
  const [phase, setPhase] = useState<Phase>({ name: "pick" });
  const [text, setText] = useState("");
  const [dragging, setDragging] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);

  const stopCamera = useCallback(() => {
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
  }, []);

  useEffect(() => stopCamera, [stopCamera]);

  useEffect(() => {
    if (phase.name === "review") textArea.current?.focus();
  }, [phase.name]);

  // Attach the live stream after React has rendered the preview (not before: there'd be no
  // <video> yet, and the preview would stay blank).
  useEffect(() => {
    const v = video.current;
    if (phase.name !== "camera" || !v || !stream.current) return;
    v.srcObject = stream.current;
    void v.play().catch(() => undefined);
  }, [phase.name]);

  function open() {
    setPhase({ name: "pick" });
    setText("");
    dialog.current?.showModal();
  }

  function close() {
    stopCamera();
    dialog.current?.close();
  }

  async function read(file: Blob, label: string) {
    stopCamera();
    setPhase({ name: "reading", label });
    try {
      const result = await readDocument(file, label);
      const lines = cleanLines(
        result.lines.map((l) => l.text),
        problemKind,
      );
      setText(lines.join("\n"));
      setPhase({ name: "review", result, source: label });
    } catch (error) {
      setPhase({
        name: "error",
        message: error instanceof Error ? error.message : "ProofLab couldn't read that file.",
      });
    }
  }

  async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      photoInput.current?.click(); // phones: the file picker opens the camera instead
      return;
    }
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      });
      setCameraReady(false);
      setPhase({ name: "camera" }); // the effect below attaches the stream once <video> exists
    } catch {
      setPhase({
        name: "error",
        message:
          "ProofLab couldn't use the camera. Allow camera access in your browser, or take the photo with your phone and choose it as a file.",
      });
    }
  }

  function capture() {
    const v = video.current;
    if (!v || !v.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    canvas.getContext("2d")?.drawImage(v, 0, 0);
    canvas.toBlob((blob) => blob && void read(blob, "camera photo"), "image/jpeg", 0.92);
  }

  function onFiles(files: FileList | null) {
    const file = files?.[0];
    if (file) void read(file, file.name);
  }

  function apply(asAnswer: boolean) {
    const lines = text
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    if (lines.length === 0) return;
    onApply({ lines, asAnswer });
    close();
  }

  const lineCount = text.split("\n").filter((l) => l.trim()).length;

  return (
    <>
      <button
        type="button"
        onClick={open}
        className="flex min-h-11 items-center gap-1.5 rounded-md border border-line px-3 py-1.5 text-muted transition hover:border-accent hover:text-accent"
      >
        <CameraIcon className="h-4 w-4" />
        Scan work
      </button>

      <dialog
        ref={dialog}
        aria-labelledby={`${ids}-title`}
        onClose={stopCamera}
        onClick={(e) => {
          if (e.target === e.currentTarget) close();
        }}
        onPaste={(e) => {
          const file = [...e.clipboardData.files].find((f) => f.type.startsWith("image/"));
          if (file && phase.name === "pick") {
            e.preventDefault();
            void read(file, "pasted image");
          }
        }}
        className="mx-auto mt-[8vh] w-[calc(100%-2rem)] max-w-xl rounded-xl border border-line bg-surface p-0 text-ink shadow-xl backdrop:bg-black/40"
      >
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <h2 id={`${ids}-title`} className="text-lg">
            Scan your work
          </h2>
          <button
            type="button"
            onClick={close}
            aria-label="Close"
            className="flex h-11 w-11 items-center justify-center rounded-md text-xl text-muted hover:text-ink"
          >
            ×
          </button>
        </div>

        <div className="space-y-4 p-4" aria-live="polite">
          {phase.name === "pick" && (
            <>
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  onFiles(e.dataTransfer.files);
                }}
                className={`space-y-3 rounded-lg border border-dashed p-5 text-center ${
                  dragging ? "border-accent bg-accent-soft" : "border-line"
                }`}
              >
                <div className="flex flex-wrap justify-center gap-2">
                  <button
                    type="button"
                    onClick={startCamera}
                    className="flex h-11 items-center gap-2 rounded-lg bg-accent px-4 text-sm font-semibold text-accent-ink transition hover:opacity-90"
                  >
                    <CameraIcon className="h-4 w-4" />
                    Take a photo
                  </button>
                  <button
                    type="button"
                    onClick={() => fileInput.current?.click()}
                    className="flex h-11 items-center rounded-lg border border-line px-4 text-sm font-medium hover:border-accent"
                  >
                    Choose a file
                  </button>
                </div>
                <p className="text-sm text-muted">
                  Or drop a file here, or paste a screenshot. Photos of handwriting, PDFs, Word
                  documents and text files all work.
                </p>
              </div>
              <p className="text-xs text-muted">
                Reading happens on the computer running ProofLab; nothing is sent anywhere else. You
                check the text before anything is graded.
              </p>
            </>
          )}

          {phase.name === "camera" && (
            <div className="space-y-3">
              <video
                ref={video}
                playsInline
                muted
                onLoadedData={() => setCameraReady(true)}
                className="aspect-video w-full rounded-lg bg-black object-contain"
              />
              <p className="text-sm text-muted">
                Fill the frame with your work, in good light, and hold still.
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={capture}
                  disabled={!cameraReady}
                  className="h-11 rounded-lg bg-accent px-5 text-sm font-semibold text-accent-ink transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {cameraReady ? "Capture" : "Starting the camera…"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    stopCamera();
                    setPhase({ name: "pick" });
                  }}
                  className="h-11 rounded-lg border border-line px-4 text-sm hover:border-accent"
                >
                  Back
                </button>
              </div>
            </div>
          )}

          {phase.name === "reading" && (
            <p className="py-6 text-center text-sm text-muted">Reading {phase.label}…</p>
          )}

          {phase.name === "error" && (
            <div className="space-y-3">
              <p className="rounded-lg border border-bad/40 bg-bad-soft px-4 py-3 text-sm text-bad">
                {phase.message}
              </p>
              <button
                type="button"
                onClick={() => setPhase({ name: "pick" })}
                className="h-11 rounded-lg border border-line px-4 text-sm hover:border-accent"
              >
                Try again
              </button>
            </div>
          )}

          {phase.name === "review" && (
            <div className="space-y-3">
              <label htmlFor={`${ids}-text`} className="block text-sm font-medium">
                Check what ProofLab read
              </label>
              <textarea
                ref={textArea}
                id={`${ids}-text`}
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={Math.min(12, Math.max(4, lineCount + 1))}
                spellCheck={false}
                aria-describedby={`${ids}-help`}
                className="w-full rounded-lg border border-line bg-bg px-3 py-2 font-mono text-[15px] leading-relaxed outline-none focus:border-accent focus:ring-2 focus:ring-accent"
              />
              <p id={`${ids}-help`} className="text-xs text-muted">
                {lineCount === 0
                  ? "No text was found. Try a sharper photo with more light, or type your work."
                  : `${lineCount} ${lineCount === 1 ? "line" : "lines"}, ${
                      ENGINE_LABEL[phase.result.engine] ?? "read"
                    }${phase.result.pages > 1 ? ` from ${phase.result.pages} pages` : ""}. Each line becomes one step. Handwriting is easy to misread: watch k and K, 2 and z, and missing ^ or brackets.`}
              </p>
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => apply(false)}
                  disabled={lineCount === 0}
                  className="h-11 rounded-lg bg-accent px-4 text-sm font-semibold text-accent-ink transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Add as steps
                </button>
                {hasAnswer && (
                  <button
                    type="button"
                    onClick={() => apply(true)}
                    disabled={lineCount === 0}
                    className="h-11 rounded-lg border border-line px-4 text-sm font-medium hover:border-accent disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Use last line as the answer
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setPhase({ name: "pick" })}
                  className="h-11 px-2 text-sm text-muted hover:text-ink"
                >
                  Scan something else
                </button>
              </div>
            </div>
          )}
        </div>

        <input
          ref={fileInput}
          type="file"
          accept={ACCEPT}
          className="sr-only"
          tabIndex={-1}
          aria-hidden
          onChange={(e) => {
            onFiles(e.target.files);
            e.target.value = "";
          }}
        />
        <input
          ref={photoInput}
          type="file"
          accept="image/*"
          capture="environment"
          className="sr-only"
          tabIndex={-1}
          aria-hidden
          onChange={(e) => {
            onFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </dialog>
    </>
  );
}

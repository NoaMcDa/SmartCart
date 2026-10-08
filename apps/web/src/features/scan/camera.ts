/**
 * Camera access for the scanner: getUserMedia with the rear camera, and a mapping from the
 * browser's errors to what the screen tells the user. Nothing is recorded or uploaded; the stream
 * only feeds the detector and is stopped as soon as a code is read or the screen closes.
 */
import type { ScanMessageKey } from "@/i18n/messages/scan";

export type CameraFailure = "denied" | "no-camera" | "busy" | "unsupported";

export type CameraResult = { ok: true; stream: MediaStream } | { ok: false; reason: CameraFailure };

export function cameraSupported(): boolean {
  return (
    typeof navigator !== "undefined" &&
    Boolean(navigator.mediaDevices) &&
    typeof navigator.mediaDevices.getUserMedia === "function"
  );
}

export function classifyCameraError(err: unknown): CameraFailure {
  const name =
    typeof err === "object" && err !== null && "name" in err ? String((err as Error).name) : "";
  if (name === "NotAllowedError" || name === "SecurityError" || name === "PermissionDeniedError") {
    return "denied";
  }
  if (
    name === "NotFoundError" ||
    name === "OverconstrainedError" ||
    name === "DevicesNotFoundError"
  ) {
    return "no-camera";
  }
  if (name === "NotReadableError" || name === "AbortError" || name === "TrackStartError") {
    return "busy";
  }
  return "unsupported";
}

export async function requestCamera(): Promise<CameraResult> {
  if (!cameraSupported()) return { ok: false, reason: "unsupported" };
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { facingMode: { ideal: "environment" } },
    });
    return { ok: true, stream };
  } catch (err) {
    return { ok: false, reason: classifyCameraError(err) };
  }
}

export function stopStream(stream: MediaStream | null | undefined): void {
  stream?.getTracks().forEach((t) => t.stop());
}

/** Message key (`scanMessages`) per camera failure; the screen translates it. */
export const CAMERA_MESSAGES = {
  denied: "camDenied",
  "no-camera": "camNone",
  busy: "camBusy",
  unsupported: "camUnsupported",
} as const satisfies Record<CameraFailure, ScanMessageKey>;

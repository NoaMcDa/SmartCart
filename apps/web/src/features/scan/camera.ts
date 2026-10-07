/**
 * Camera access for the scanner: getUserMedia with the rear camera, and a mapping from the
 * browser's errors to what the screen tells the user. Nothing is recorded or uploaded; the stream
 * only feeds the detector and is stopped as soon as a code is read or the screen closes.
 */

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

export const CAMERA_MESSAGES: Record<CameraFailure, string> = {
  denied:
    "הגישה למצלמה נחסמה. אפשר לאשר אותה בהגדרות הדפדפן ולנסות שוב, או להקליד את הברקוד ידנית.",
  "no-camera": "לא נמצאה מצלמה במכשיר הזה. אפשר להקליד את הברקוד ידנית.",
  busy: "המצלמה תפוסה על ידי אפליקציה אחרת. סגרי אותה ונסי שוב, או הקלידי את הברקוד ידנית.",
  unsupported: "הדפדפן הזה לא מאפשר לפתוח מצלמה. אפשר להקליד את הברקוד ידנית.",
};

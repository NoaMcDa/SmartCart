"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useId, useRef, useState, type FormEvent } from "react";
import { lookupBarcode, type BarcodeLookupResponse } from "@/api/client";
import { Button, Card, Skeleton } from "@/components/ui";
import { IconBarcode, IconClose, IconInfo } from "@/components/ui/icons";
import { reportScanCompleted, reportScanStarted } from "@/features/consent/betaEvents";
import type { ScanEngine, ScanOutcome } from "@/features/consent/betaEvents";
import { ReportGapButton } from "@/features/feedback";
import controls from "@/features/profile/controls/controls.module.css";
import { useShopper } from "@/state/shopper";
import { BARCODE_ERRORS, checkBarcode } from "./barcode";
import { CAMERA_MESSAGES, requestCamera, stopStream, type CameraFailure } from "./camera";
import { startDetector, type ScanSession } from "./detector";
import { ResultCard } from "./ResultCard";
import { recordScan } from "./scanLog";
import { useScanStores } from "./stores";
import styles from "./Scan.module.css";

type Phase =
  | { kind: "idle" }
  | { kind: "starting" }
  | { kind: "scanning" }
  | { kind: "camera-error"; reason: CameraFailure }
  | { kind: "loading"; code: string }
  | { kind: "result"; result: BarcodeLookupResponse }
  | { kind: "lookup-error"; code: string };

/** What the shopper saw: a product with no price anywhere is "no_price", never "found". */
export function outcomeOf(result: BarcodeLookupResponse): ScanOutcome {
  if (!result.found) return "not_found";
  const priced = result.here || result.cheapest_nearby || result.cheaper_substitute;
  return priced ? "found" : "no_price";
}

/**
 * Barcode scanning (issue #39). Camera behind an explicit "turn on" (the permission is asked only
 * after the explanation), native BarcodeDetector or the zxing fallback, manual entry always on
 * screen, the store the shopper is in, and the result card. Images never leave the video element.
 *
 * `/scan?code=<ean>` runs the lookup without the camera, as if the code had been typed (deep links
 * and the full-stack suite). A code that fails the check digit shows the manual-entry error and
 * makes no request.
 */
export function ScanScreen() {
  return (
    <Suspense fallback={<div aria-busy="true" />}>
      <ScanScreenInner />
    </Suspense>
  );
}

function ScanScreenInner() {
  const shopper = useShopper();
  const stores = useScanStores(shopper);
  // The hook is null outside a Next router (component tests), which simply means "no code".
  const params = useSearchParams() as ReturnType<typeof useSearchParams> | null;
  const urlCode = params?.get("code")?.trim() || null;
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [manual, setManual] = useState(urlCode ?? "");
  const [manualError, setManualError] = useState<string | null>(() => {
    if (!urlCode) return null;
    const check = checkBarcode(urlCode);
    return check.ok ? null : BARCODE_ERRORS[check.reason];
  });
  const urlHandled = useRef<string | null>(null);
  const manualId = useId();
  const storeSelectId = useId();

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const startedAt = useRef(0);
  const input = useRef<"camera" | "manual">("camera");
  // One scan attempt is "open" from the camera tap (or the manual search) until it ends. Every
  // ended attempt reports `scan_completed`, and `scan_started` is sent first if it was not yet
  // (the camera engine is only known once the decoder is up). Nothing about the code is kept.
  const attempt = useRef({
    open: false,
    startedSent: false,
    engine: undefined as ScanEngine | undefined,
  });
  const cameraEngine = useRef<ScanEngine | undefined>(undefined);
  // The detector callback outlives renders; it reads the freshest shopper and store from here.
  const latest = useRef({ lat: 0, lon: 0, radiusM: 5000, storeId: null as number | null });
  useEffect(() => {
    latest.current = {
      lat: shopper?.lat ?? 0,
      lon: shopper?.lon ?? 0,
      radiusM: shopper?.radiusM ?? 5000,
      storeId: stores.storeId,
    };
  });

  const release = useCallback(() => {
    stopStream(streamRef.current);
    streamRef.current = null;
  }, []);

  const openAttempt = useCallback((engine?: ScanEngine) => {
    const a = attempt.current;
    a.open = true;
    if (engine) a.engine = engine;
    if (!a.startedSent && engine) {
      a.startedSent = true;
      reportScanStarted(engine);
    }
  }, []);

  const endAttempt = useCallback((outcome: ScanOutcome) => {
    const a = attempt.current;
    if (!a.open) return;
    if (!a.startedSent) reportScanStarted(a.engine);
    reportScanCompleted({
      outcome,
      durationMs: performance.now() - startedAt.current,
      engine: a.engine,
    });
    attempt.current = { open: false, startedSent: false, engine: undefined };
  }, []);

  const lookup = useCallback(
    async (code: string, via: "camera" | "manual") => {
      input.current = via;
      if (startedAt.current === 0) startedAt.current = performance.now();
      // A retry after an error starts a new attempt; a camera read continues the open one.
      if (!attempt.current.open) openAttempt(via === "manual" ? "manual" : cameraEngine.current);
      setPhase({ kind: "loading", code });
      const { lat, lon, radiusM, storeId } = latest.current;
      try {
        const result = await lookupBarcode(code, { lat, lon, radiusM, storeId });
        recordScan(
          result.found ? "found" : "not_found",
          via,
          performance.now() - startedAt.current,
        );
        endAttempt(outcomeOf(result));
        setPhase({ kind: "result", result });
      } catch {
        recordScan("failed", via, 0);
        endAttempt("error");
        setPhase({ kind: "lookup-error", code });
      }
    },
    [openAttempt, endAttempt],
  );

  async function startCamera() {
    setPhase({ kind: "starting" });
    startedAt.current = performance.now();
    attempt.current = { open: true, startedSent: false, engine: undefined };
    const cam = await requestCamera();
    if (!cam.ok) {
      recordScan("failed", "camera", 0);
      endAttempt("error");
      setPhase({ kind: "camera-error", reason: cam.reason });
      return;
    }
    streamRef.current = cam.stream;
    setPhase({ kind: "scanning" });
  }

  // A code in the URL is looked up once the shopper and the nearby stores are known, so the lookup
  // names the store the shopper is in. No camera, no permission prompt.
  const ready = Boolean(shopper) && !stores.loading;
  useEffect(() => {
    if (!urlCode || !ready) return;
    let cancelled = false;
    // Deferred a tick: the lookup sets state, and an effect must not do that synchronously.
    queueMicrotask(() => {
      if (cancelled || urlHandled.current === urlCode) return;
      urlHandled.current = urlCode;
      const check = checkBarcode(urlCode);
      if (!check.ok) return; // the error is already on the manual field
      startedAt.current = performance.now();
      openAttempt("manual");
      void lookup(check.code, "manual");
    });
    return () => {
      cancelled = true;
    };
  }, [urlCode, ready, lookup, openAttempt]);

  // While scanning, the detector reads the video; the first valid code ends the camera.
  const scanning = phase.kind === "scanning";
  useEffect(() => {
    if (!scanning) return;
    const video = videoRef.current;
    const stream = streamRef.current;
    if (!video || !stream) return;
    let cancelled = false;
    let session: ScanSession | null = null;
    startDetector(video, stream, (code) => {
      if (cancelled) return;
      release();
      void lookup(code, "camera");
    })
      .then((s) => {
        if (cancelled) {
          s.stop();
          return;
        }
        session = s;
        cameraEngine.current = s.engine;
        openAttempt(s.engine);
      })
      .catch(() => {
        if (cancelled) return;
        release();
        recordScan("failed", "camera", 0);
        endAttempt("error");
        setPhase({ kind: "camera-error", reason: "unsupported" });
      });
    return () => {
      cancelled = true;
      session?.stop();
    };
  }, [scanning, lookup, release, openAttempt, endAttempt]);

  // Leaving the screen always turns the camera off, and ends an attempt still open.
  useEffect(
    () => () => {
      release();
      endAttempt("cancelled");
    },
    [release, endAttempt],
  );

  function stopCamera() {
    release();
    endAttempt("cancelled");
    setPhase({ kind: "idle" });
  }

  function submitManual(e: FormEvent) {
    e.preventDefault();
    const check = checkBarcode(manual);
    if (!check.ok) {
      setManualError(BARCODE_ERRORS[check.reason]);
      return;
    }
    setManualError(null);
    release();
    endAttempt("cancelled"); // typing a code abandons a camera attempt that was still open
    startedAt.current = performance.now();
    openAttempt("manual");
    void lookup(check.code, "manual");
  }

  function again() {
    release();
    endAttempt("cancelled");
    startedAt.current = 0;
    setManual("");
    setPhase({ kind: "idle" });
  }

  const cameraBusy = phase.kind === "starting" || phase.kind === "scanning";
  const storeRef = stores.selected;
  const gapStore = storeRef ? { storeId: storeRef.storeId, name: storeRef.label } : null;

  return (
    <div className={styles.page}>
      <p className={styles.intro}>
        כוונו את המצלמה אל הברקוד שעל המוצר. נראה כאן מה המחיר, איפה הכי זול באזור ואיזה תחליף זול
        יותר יש.
      </p>

      <div className={controls.field}>
        <label htmlFor={storeSelectId} className={controls.label}>
          באיזה סניף את עכשיו?
        </label>
        <select
          id={storeSelectId}
          className={controls.input}
          value={stores.storeId ?? ""}
          disabled={stores.loading || stores.options.length === 0}
          onChange={(e) => stores.choose(Number(e.target.value))}
          data-testid="scan-store"
        >
          {stores.loading ? <option value="">טוענת סניפים…</option> : null}
          {!stores.loading && stores.options.length === 0 ? (
            <option value="">לא נמצאו סניפים באזור</option>
          ) : null}
          {stores.options.map((o) => (
            <option key={o.storeId} value={o.storeId}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {phase.kind === "scanning" || phase.kind === "starting" ? (
        <Card className={styles.cameraCard} data-testid="scan-camera">
          <div className={styles.viewport}>
            <video
              ref={videoRef}
              className={styles.video}
              playsInline
              muted
              aria-label="תצוגת המצלמה"
              data-testid="scan-video"
            />
            <div className={styles.frame} aria-hidden="true" />
          </div>
          <p role="status" className={styles.lineMeta}>
            {phase.kind === "starting" ? "פותחת את המצלמה…" : "מחפשת ברקוד…"}
          </p>
          <Button
            variant="outline"
            size="sm"
            iconStart={<IconClose size={16} />}
            onClick={stopCamera}
          >
            עצירת המצלמה
          </Button>
        </Card>
      ) : null}

      {phase.kind === "idle" || phase.kind === "camera-error" ? (
        <Card as="section" aria-labelledby="camera-heading">
          <h2 id="camera-heading" className={styles.sectionTitle}>
            סריקה במצלמה
          </h2>
          <p className={controls.hint}>
            המצלמה משמשת רק לקריאת הברקוד. לא נשמרות תמונות והן לא עוזבות את המכשיר. הדפדפן יבקש
            אישור כשתלחצי על הכפתור.
          </p>
          {phase.kind === "camera-error" ? (
            <p className={styles.error} role="alert" data-testid="scan-camera-error">
              <IconInfo size={15} /> {CAMERA_MESSAGES[phase.reason]}
            </p>
          ) : null}
          <Button
            iconStart={<IconBarcode size={18} />}
            onClick={() => void startCamera()}
            disabled={cameraBusy}
          >
            {phase.kind === "camera-error" ? "ניסיון נוסף" : "הפעלת המצלמה"}
          </Button>
        </Card>
      ) : null}

      <Card as="section" aria-labelledby="manual-heading">
        <h2 id="manual-heading" className={styles.sectionTitle}>
          הקלדת ברקוד ידנית
        </h2>
        <form onSubmit={submitManual} className={controls.stack} noValidate>
          <div className={controls.field}>
            <label htmlFor={manualId} className={controls.label}>
              ברקוד (13 ספרות, או 8 במוצרים קטנים)
            </label>
            <input
              id={manualId}
              className={controls.input}
              inputMode="numeric"
              autoComplete="off"
              dir="ltr"
              placeholder="7290000000000"
              value={manual}
              aria-invalid={manualError ? true : undefined}
              aria-describedby={manualError ? `${manualId}-error` : undefined}
              onChange={(e) => {
                setManual(e.target.value);
                setManualError(null);
              }}
            />
            {manualError ? (
              <p id={`${manualId}-error`} className={controls.error} role="alert">
                {manualError}
              </p>
            ) : null}
          </div>
          <Button type="submit" variant="secondary" disabled={!shopper}>
            חיפוש
          </Button>
        </form>
      </Card>

      <div aria-live="polite" aria-busy={phase.kind === "loading"}>
        {phase.kind === "loading" ? (
          <Card aria-label="מחפשת את המוצר" data-testid="scan-loading">
            <Skeleton width="60%" height={22} />
            <Skeleton height={44} />
            <Skeleton height={44} />
          </Card>
        ) : null}

        {phase.kind === "lookup-error" ? (
          <Card role="alert" data-testid="scan-error">
            <p>לא הצלחנו לבדוק את הברקוד. בדקי את החיבור ונסי שוב.</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void lookup(phase.code, input.current)}
            >
              נסי שוב
            </Button>
          </Card>
        ) : null}

        {phase.kind === "result" && phase.result.found ? (
          <ResultCard result={phase.result} store={gapStore} />
        ) : null}

        {phase.kind === "result" && !phase.result.found ? (
          <Card as="section" aria-labelledby="notfound-heading" data-testid="scan-notfound">
            <h2 id="notfound-heading" className={styles.sectionTitle}>
              לא מצאנו את הברקוד הזה
            </h2>
            <p>
              הברקוד <span dir="ltr">{phase.result.barcode}</span> לא מקושר אצלנו למוצר. ייתכן שזה
              קוד פנימי של הרשת ולא ברקוד אמיתי. לא ננחש מוצר.
            </p>
            <p className={controls.hint}>
              אפשר להקליד ברקוד אחר, לחפש את המוצר ברשימה, או לדווח לנו.
            </p>
            <div className={styles.addRow}>
              {gapStore ? (
                <ReportGapButton
                  label="דווחי על פער"
                  context={{
                    storeId: gapStore.storeId,
                    storeName: gapStore.name,
                    itemName: `ברקוד ${phase.result.barcode}`,
                  }}
                />
              ) : null}
              <Button variant="outline" size="sm" onClick={again}>
                סריקה נוספת
              </Button>
            </div>
          </Card>
        ) : null}

        {phase.kind === "result" && phase.result.found ? (
          <Button variant="outline" onClick={again} className={styles.again}>
            סריקת מוצר נוסף
          </Button>
        ) : null}
      </div>
    </div>
  );
}

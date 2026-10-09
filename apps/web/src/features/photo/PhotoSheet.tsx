"use client";

import { useEffect, useId, useRef, useState, type ChangeEvent, type ReactNode } from "react";
import { parseImage, parseList, type ParsedRow, type ParseImageResponse } from "@/api/client";
import { BottomSheet, Button, IconInfo } from "@/components/ui";
import { getImageConsent, setImageConsent } from "@/features/consent/imageConsent";
import { unresolvedRow } from "@/features/recipe/scale";
import { LegalNotice } from "@/i18n/LegalNotice";
import { useT } from "@/i18n/LocaleProvider";
import { photoMessages } from "@/i18n/messages/photo";
import { CameraIcon } from "./CameraIcon";
import { prepareImage } from "./imageFile";
import {
  classifyPhotoError,
  isRetryable,
  now,
  outcomeOfError,
  reportImageParsed,
} from "./photoErrors";
import type { PhotoErrorKind } from "./photoErrors";
import { PhotoPreview, type PreviewSelection } from "./PhotoPreview";
import styles from "./Photo.module.css";

type Kind = ParseImageResponse["kind"];
type Attempt = { kind: Kind; file: File };

type Stage =
  | { name: "choose" }
  | { name: "consent"; serverAsked: boolean }
  | { name: "reading" }
  | { name: "preview"; result: ParseImageResponse }
  | { name: "empty" }
  | { name: "error"; kind: PhotoErrorKind };

export type PhotoSheetProps = {
  open: boolean;
  /** Called for every way out of the sheet (close button, Escape, scrim, "type instead"). */
  onClose: () => void;
  /** The rows the person confirmed. Nothing reaches the list before this. */
  onAdd: (rows: ParsedRow[]) => void;
  /** "להקליד במקום": the parent puts the cursor in the list input once the sheet is closed. */
  onTypeInstead?: () => void;
  flexDefaults?: Record<string, "exact" | "any_brand" | "close">;
};

/**
 * Photo to list (receipts #61, handwritten lists #68). One sheet, one flow:
 *
 *   choose (receipt or list; camera or file) -> [consent, once] -> reading -> preview -> list
 *
 * Nothing is uploaded before the person agreed (`imageConsent.ts`), and nothing reaches the list
 * before they confirm the preview. The file is validated and downscaled in the browser first
 * (`imageFile.ts`). Every failure has its own message and a retry or the way back to typing.
 * Focus: the sheet focuses its first control on open; after that each step moves focus to its own
 * heading or message (`focusRef`), so a screen reader hears where it is and a keyboard user is
 * never left on a control that just disappeared.
 */
export function PhotoSheet({ open, onClose, onAdd, onTypeInstead, flexDefaults }: PhotoSheetProps) {
  const t = useT(photoMessages);
  const cameraInput = useRef<HTMLInputElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const pickedKind = useRef<Kind>("receipt");
  const abort = useRef<AbortController | null>(null);
  const focusRef = useRef<HTMLElement | null>(null);
  const seenOpen = useRef(false);
  const groupId = useId();

  const [stage, setStage] = useState<Stage>({ name: "choose" });
  /** The prepared photo of the current attempt; a retry and the consent step reuse it. */
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [problem, setProblem] = useState<PhotoErrorKind | null>(null);
  const [adding, setAdding] = useState(false);
  const [selection, setSelection] = useState<PreviewSelection | null>(null);

  function reset() {
    abort.current?.abort();
    abort.current = null;
    setAttempt(null);
    setStage({ name: "choose" });
    setProblem(null);
    setAdding(false);
    setSelection(null);
  }

  function close() {
    reset();
    onClose();
  }

  function typeInstead() {
    close();
    // After the sheet's own focus return to its opener.
    if (onTypeInstead) setTimeout(onTypeInstead, 0);
  }

  // Leaving the page mid-request cancels it.
  useEffect(() => () => abort.current?.abort(), []);

  // Move focus to the new step's heading or message. The first render is the sheet's own focus.
  const focusKey = `${stage.name}:${stage.name === "error" ? stage.kind : ""}:${problem ?? ""}`;
  useEffect(() => {
    if (!open) {
      seenOpen.current = false;
      return;
    }
    if (!seenOpen.current) {
      seenOpen.current = true;
      return;
    }
    focusRef.current?.focus();
  }, [open, focusKey]);

  function choose(kind: Kind, withCamera: boolean) {
    pickedKind.current = kind;
    setProblem(null);
    (withCamera ? cameraInput : fileInput).current?.click();
  }

  async function onPicked(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    // Reset so choosing the same file again (after a failure) fires another change event.
    e.target.value = "";
    if (!file) return;
    const kind = pickedKind.current;
    // The attempt is cancellable from here, not only once the request starts: "ביטול" or closing
    // the sheet while the photo is still being prepared must stop the upload that would follow.
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setAttempt(null);
    setProblem(null);
    setStage({ name: "reading" });
    let prepared: File;
    try {
      prepared = await prepareImage(file);
    } catch (err) {
      if (controller.signal.aborted) return;
      const reason = classifyPhotoError(err);
      reportImageParsed({ kind, outcome: outcomeOfError(reason) });
      setStage({ name: "choose" });
      setProblem(reason);
      return;
    }
    if (controller.signal.aborted) return;
    const next = { kind, file: prepared };
    setAttempt(next);
    await upload(next, controller);
  }

  async function upload(current: Attempt | null, controller = new AbortController()) {
    if (!current) return;
    // The one gate: no consent, no request (`parseImage` refuses too).
    if (!getImageConsent()) {
      setStage({ name: "consent", serverAsked: false });
      return;
    }
    abort.current = controller;
    setStage({ name: "reading" });
    const started = now();
    try {
      const result = await parseImage(current.kind, current.file, true, {
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      const empty = result.items.length === 0 && result.unresolved.length === 0;
      reportImageParsed({
        kind: current.kind,
        outcome: empty ? "empty" : "parsed",
        itemCount: result.items.length,
        durationMs: now() - started,
      });
      setStage(empty ? { name: "empty" } : { name: "preview", result });
    } catch (err) {
      if (controller.signal.aborted) return;
      console.error("DEBUGFLAKE upload error", err, (err as { cause?: unknown })?.cause);
      const kind = classifyPhotoError(err);
      reportImageParsed({
        kind: current.kind,
        outcome: outcomeOfError(kind),
        durationMs: now() - started,
      });
      setStage({ name: "error", kind });
    }
  }

  function agree() {
    setImageConsent(true);
    void upload(attempt);
  }

  function cancelReading() {
    abort.current?.abort();
    abort.current = null;
    setAttempt(null);
    setStage({ name: "choose" });
  }

  /** Confirm: the person's selection becomes list rows; edited lines try `/parse-list` first. */
  async function add() {
    if (!selection || selection.count === 0 || adding) return;
    setAdding(true);
    const { rows, edited, kept } = selection.build();
    let reparsed: ParsedRow[] = [];
    if (edited.length > 0) {
      try {
        reparsed = (await parseList({ text: edited.join("\n"), flex_defaults: flexDefaults })).rows;
      } catch {
        // The line is still the person's own words: it joins the list as an unmatched row.
        reparsed = edited.map(unresolvedRow);
      }
    }
    reset();
    onAdd([...rows, ...reparsed, ...kept.map(unresolvedRow)]);
  }

  function errorMessage(kind: PhotoErrorKind): string {
    switch (kind) {
      case "consent":
        return t("errConsent");
      case "too-large":
      case "too-big":
        return t("errTooLarge");
      case "type":
      case "not-image":
        return t("errType");
      case "quota":
        return t("errQuota");
      case "unavailable":
        return t("errUnavailable");
      case "network":
        return t("errNetwork");
      default:
        return t("errGeneric");
    }
  }

  const heading = (text: string, props: { role?: "status" } = {}) => (
    <h3
      className={styles.stageTitle}
      ref={(el) => {
        focusRef.current = el;
      }}
      tabIndex={-1}
      {...props}
    >
      {text}
    </h3>
  );

  let body: ReactNode = null;
  let footer: ReactNode = null;

  if (stage.name === "choose") {
    const problemText =
      problem === "not-image"
        ? t("errNotImage")
        : problem === "too-big"
          ? t("errTooBig")
          : problem
            ? t("errUnreadableFile")
            : null;
    body = (
      <div className={styles.body}>
        <p
          className={styles.lead}
          tabIndex={-1}
          ref={(el) => {
            if (!problemText) focusRef.current = el;
          }}
        >
          {t("chooseLead")}
        </p>
        {problemText ? (
          <p
            className={styles.callout}
            role="alert"
            tabIndex={-1}
            ref={(el) => {
              focusRef.current = el;
            }}
            data-testid="photo-problem"
          >
            <IconInfo size={16} />
            {problemText}
          </p>
        ) : null}
        {(["receipt", "list"] as const).map((kind) => {
          const title = t(kind === "receipt" ? "receiptTitle" : "listTitle");
          return (
            <section key={kind} className={styles.kindCard} aria-labelledby={`${groupId}-${kind}`}>
              <h4 id={`${groupId}-${kind}`} className={styles.kindTitle}>
                {title}
              </h4>
              <p className={styles.hint}>{t(kind === "receipt" ? "receiptHelp" : "listHelp")}</p>
              <div className={styles.kindActions}>
                <Button
                  size="sm"
                  iconStart={<CameraIcon size={18} />}
                  aria-label={t("cameraFor", { what: title })}
                  onClick={() => choose(kind, true)}
                  data-testid={`photo-${kind}-camera`}
                >
                  {t("camera")}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  aria-label={t("pickFileFor", { what: title })}
                  onClick={() => choose(kind, false)}
                  data-testid={`photo-${kind}-file`}
                >
                  {t("pickFile")}
                </Button>
              </div>
            </section>
          );
        })}
        <p className={styles.hint} data-testid="photo-privacy">
          {t("choosePrivacy")}
        </p>
      </div>
    );
  } else if (stage.name === "consent") {
    body = (
      <div className={styles.body} data-testid="photo-consent">
        {heading(t("consentTitle"))}
        {stage.serverAsked ? (
          <p className={styles.callout} role="alert">
            <IconInfo size={16} />
            {t("consentServerAsked")}
          </p>
        ) : null}
        <p className={styles.lead}>{t("consentBody")}</p>
        <LegalNotice />
      </div>
    );
    footer = (
      <div className={styles.actions}>
        <Button variant="outline" onClick={close} data-testid="photo-consent-decline">
          {t("consentDecline")}
        </Button>
        <Button onClick={agree} data-testid="photo-consent-agree">
          {t("consentAgree")}
        </Button>
      </div>
    );
  } else if (stage.name === "reading") {
    body = (
      <div className={styles.body} aria-busy="true" data-testid="photo-reading">
        {heading(t("reading"), { role: "status" })}
        <div className={styles.progress} aria-hidden="true">
          <span className={styles.progressBar} />
        </div>
        <p className={styles.hint}>{t("readingSub")}</p>
      </div>
    );
    footer = (
      <div className={styles.actions}>
        <Button variant="outline" onClick={cancelReading} data-testid="photo-cancel">
          {t("cancel")}
        </Button>
      </div>
    );
  } else if (stage.name === "preview" && attempt) {
    body = (
      <PhotoPreview
        result={stage.result}
        file={attempt.file}
        headingRef={(el) => {
          focusRef.current = el;
        }}
        onSelectionChange={setSelection}
      />
    );
    footer = (
      <div className={styles.actions}>
        <Button variant="outline" onClick={reset} data-testid="photo-back">
          {t("back")}
        </Button>
        <Button
          onClick={() => void add()}
          disabled={!selection || selection.count === 0 || adding}
          data-testid="photo-add"
        >
          {adding ? t("adding") : t("addButton", { count: selection?.count ?? 0 })}
        </Button>
      </div>
    );
  } else if (stage.name === "empty") {
    body = (
      <div className={styles.body} data-testid="photo-empty">
        {heading(t("emptyTitle"))}
        <p className={styles.lead}>{t("emptyBody")}</p>
      </div>
    );
    footer = (
      <div className={styles.actions}>
        <Button variant="outline" onClick={typeInstead} data-testid="photo-type">
          {t("typeInstead")}
        </Button>
        <Button onClick={reset} data-testid="photo-another">
          {t("anotherImage")}
        </Button>
      </div>
    );
  } else if (stage.name === "error") {
    const kind = stage.kind;
    body = (
      <div className={styles.body}>
        <p
          className={styles.callout}
          role="alert"
          tabIndex={-1}
          ref={(el) => {
            focusRef.current = el;
          }}
          data-testid="photo-error"
          data-kind={kind}
        >
          <IconInfo size={16} />
          {errorMessage(kind)}
        </p>
      </div>
    );
    footer = (
      <div className={styles.actions}>
        <Button variant="outline" onClick={typeInstead} data-testid="photo-type">
          {t("typeInstead")}
        </Button>
        {isRetryable(kind) && attempt ? (
          <Button onClick={() => void upload(attempt)} data-testid="photo-retry">
            {t("retry")}
          </Button>
        ) : kind === "consent" && attempt ? (
          <Button
            onClick={() => setStage({ name: "consent", serverAsked: true })}
            data-testid="photo-reconsent"
          >
            {t("errConsentAction")}
          </Button>
        ) : kind === "quota" ? null : (
          <Button onClick={reset} data-testid="photo-another">
            {t("anotherImage")}
          </Button>
        )}
      </div>
    );
  }

  return (
    <>
      {/* Outside the dialog on purpose: the sheet's focus trap would otherwise count them. */}
      <input
        ref={cameraInput}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        tabIndex={-1}
        onChange={(e) => void onPicked(e)}
        data-testid="photo-input-camera"
      />
      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        hidden
        tabIndex={-1}
        onChange={(e) => void onPicked(e)}
        data-testid="photo-input-file"
      />
      <BottomSheet
        open={open}
        onClose={close}
        eyebrow={t("sheetEyebrow")}
        title={t("sheetTitle")}
        footer={footer}
      >
        {body}
      </BottomSheet>
    </>
  );
}

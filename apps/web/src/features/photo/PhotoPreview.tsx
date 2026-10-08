"use client";

import { useEffect, useMemo, useState, type Ref } from "react";
import type { ParsedRow, ParseImageResponse } from "@/api/client";
import { Price, Tag } from "@/components/ui";
import { CHAINS } from "@/features/profile/chains";
import { useT } from "@/i18n/LocaleProvider";
import { photoMessages } from "@/i18n/messages/photo";
import styles from "./Photo.module.css";

/** What the person ticked, as the sheet's "add" button needs it. */
export type PreviewSelection = {
  /** Rows that will be added: ticked matches plus ticked lines with text. */
  count: number;
  build: () => {
    /** Ticked matches, as the server resolved them. */
    rows: ParsedRow[];
    /** Ticked unresolved lines the person rewrote: they go through `/parse-list` once more. */
    edited: string[];
    /** Ticked unresolved lines left as read: they join the list as unmatched rows. */
    kept: string[];
  };
};

export type PhotoPreviewProps = {
  result: ParseImageResponse;
  /** The prepared photo, shown small on this device only (an object URL, never uploaded again). */
  file: Blob;
  headingRef: Ref<HTMLHeadingElement>;
  onSelectionChange: (selection: PreviewSelection) => void;
};

type Line = { original: string; text: string; checked: boolean };

function chainName(hint: string | null | undefined): string | null {
  if (!hint) return null;
  return CHAINS.find((c) => c.apiId === hint || c.id === hint)?.name ?? null;
}

/**
 * The read-back before anything joins the list (the recipe preview's pattern): matches that are
 * sure are ticked, matches that need confirmation sit in an amber group and start unticked, and
 * the lines that were read but not matched are editable and start unticked. A receipt adds its
 * summary (chain, printed total, number of lines). The photo itself is shown beside it, so what was
 * read can be checked against what was written.
 */
export function PhotoPreview({ result, file, headingRef, onSelectionChange }: PhotoPreviewProps) {
  const t = useT(photoMessages);
  // A row the server could not match is an unresolved line, whatever list it arrived in.
  const matched = useMemo(() => result.items.filter((r) => !r.not_found), [result.items]);
  const sure = useMemo(() => matched.filter((r) => !r.needs_confirmation), [matched]);
  const unsure = useMemo(() => matched.filter((r) => r.needs_confirmation), [matched]);
  const [sureOn, setSureOn] = useState<boolean[]>(() => sure.map(() => true));
  const [unsureOn, setUnsureOn] = useState<boolean[]>(() => unsure.map(() => false));
  const [lines, setLines] = useState<Line[]>(() => [
    ...result.unresolved.map((text) => ({ original: text, text, checked: false })),
    ...result.items
      .filter((r) => r.not_found)
      .map((r) => ({ original: r.input_text, text: r.input_text, checked: false })),
  ]);

  // An object URL for this device only; revoked when the preview goes away.
  const [photoUrl] = useState<string | null>(() =>
    typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : null,
  );
  useEffect(
    () => () => {
      if (photoUrl) URL.revokeObjectURL(photoUrl);
    },
    [photoUrl],
  );

  const selection = useMemo<PreviewSelection>(() => {
    const ticked = lines.filter((l) => l.checked && l.text.trim() !== "");
    return {
      count: sureOn.filter(Boolean).length + unsureOn.filter(Boolean).length + ticked.length,
      build: () => ({
        rows: [...sure.filter((_, i) => sureOn[i]), ...unsure.filter((_, i) => unsureOn[i])],
        edited: ticked.filter((l) => l.text.trim() !== l.original.trim()).map((l) => l.text.trim()),
        kept: ticked.filter((l) => l.text.trim() === l.original.trim()).map((l) => l.text.trim()),
      }),
    };
  }, [sure, unsure, sureOn, unsureOn, lines]);

  useEffect(() => {
    onSelectionChange(selection);
  }, [selection, onSelectionChange]);

  const receipt = result.kind === "receipt" ? result.receipt : null;
  const chain = chainName(receipt?.chain_hint);

  return (
    <div className={styles.body} data-testid="photo-preview">
      <div className={styles.previewHead}>
        {photoUrl ? (
          // A blob: URL for this device only; next/image cannot optimize it and should not.
          // eslint-disable-next-line @next/next/no-img-element
          <img className={styles.thumb} src={photoUrl} alt={t("photoAlt")} />
        ) : null}
        <h3 className={styles.stageTitle} ref={headingRef} tabIndex={-1}>
          {t(result.kind === "receipt" ? "previewTitleReceipt" : "previewTitleList")}
        </h3>
      </div>

      {receipt ? (
        <section
          className={styles.summary}
          aria-labelledby="photo-summary"
          data-testid="photo-receipt-summary"
        >
          <h4 id="photo-summary" className={styles.groupTitle}>
            {t("summaryHeading")}
          </h4>
          <dl className={styles.facts}>
            <div>
              <dt>{t("summaryChain")}</dt>
              <dd data-testid="photo-chain">
                {chain ?? receipt.store_hint ?? t("summaryChainUnknown")}
                {chain && receipt.store_hint ? ` · ${receipt.store_hint}` : ""}
              </dd>
            </div>
            <div>
              <dt>{t("summaryTotal")}</dt>
              <dd data-testid="photo-total">
                {receipt.total ? (
                  <Price amount={receipt.total} fractionDigits={2} />
                ) : (
                  t("summaryTotalUnknown")
                )}
              </dd>
            </div>
            <div>
              <dt>{t("summaryLines")}</dt>
              <dd data-testid="photo-line-count">
                <span dir="ltr">
                  {receipt.lines && receipt.lines.length > 0
                    ? receipt.lines.length
                    : result.items.length + result.unresolved.length}
                </span>
              </dd>
            </div>
          </dl>
        </section>
      ) : null}

      {sure.length > 0 ? (
        <section aria-labelledby="photo-sure">
          <h4 id="photo-sure" className={styles.groupTitle}>
            {t("recognizedHeading", { count: sure.length })}
          </h4>
          <ul className={styles.rows}>
            {sure.map((row, i) => (
              <ReadRow
                key={`${row.input_text}-${i}`}
                row={row}
                checked={sureOn[i] ?? false}
                onChange={(on) => setSureOn((prev) => prev.map((v, j) => (j === i ? on : v)))}
              />
            ))}
          </ul>
        </section>
      ) : null}

      {unsure.length > 0 ? (
        <section aria-labelledby="photo-unsure" className={styles.amber} data-testid="photo-unsure">
          <h4 id="photo-unsure" className={styles.groupTitle}>
            {t("unsureHeading", { count: unsure.length })}
          </h4>
          <p className={styles.amberHint}>{t("unsureHint")}</p>
          <ul className={styles.rows}>
            {unsure.map((row, i) => (
              <ReadRow
                key={`${row.input_text}-${i}`}
                row={row}
                unsure
                checked={unsureOn[i] ?? false}
                onChange={(on) => setUnsureOn((prev) => prev.map((v, j) => (j === i ? on : v)))}
              />
            ))}
          </ul>
        </section>
      ) : null}

      {lines.length > 0 ? (
        <section aria-labelledby="photo-unresolved" data-testid="photo-unresolved">
          <h4 id="photo-unresolved" className={styles.groupTitle}>
            {t("unresolvedHeading", { count: lines.length })}
          </h4>
          <p className={styles.hint}>{t("unresolvedHint")}</p>
          <ul className={styles.rows}>
            {lines.map((line, i) => (
              <li key={i} className={styles.lineRow} data-testid="photo-unresolved-row">
                <input
                  type="checkbox"
                  className={styles.check}
                  checked={line.checked}
                  aria-label={t("includeRow", { name: line.original })}
                  onChange={(e) =>
                    setLines((prev) =>
                      prev.map((l, j) => (j === i ? { ...l, checked: e.target.checked } : l)),
                    )
                  }
                />
                <input
                  type="text"
                  className={styles.field}
                  value={line.text}
                  aria-label={t("unresolvedField", { text: line.original })}
                  autoComplete="off"
                  onChange={(e) =>
                    setLines((prev) =>
                      prev.map((l, j) =>
                        // Typing in a line means the person wants it.
                        j === i ? { ...l, text: e.target.value, checked: true } : l,
                      ),
                    )
                  }
                />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {result.deleted ? (
        <p className={styles.deleted} data-testid="photo-deleted">
          {t("deletedLine")}
        </p>
      ) : null}
    </div>
  );
}

function ReadRow({
  row,
  checked,
  onChange,
  unsure = false,
}: {
  row: ParsedRow;
  checked: boolean;
  onChange: (on: boolean) => void;
  unsure?: boolean;
}) {
  const t = useT(photoMessages);
  const name = row.canonical?.display_name_he ?? row.input_text;
  const weighed = row.is_weighed || row.unit === "kg";
  // What was read next to what it was matched to, when they differ (D10: show the work).
  const showRead = Boolean(row.canonical) && row.input_text.trim() !== name.trim();
  return (
    <li className={styles.row} data-testid={unsure ? "photo-unsure-row" : "photo-row"}>
      <label className={styles.rowLabel}>
        <input
          type="checkbox"
          className={styles.check}
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className={styles.rowText}>
          <span className={styles.rowLine}>
            <span className={styles.qty}>
              <span dir="ltr">{row.quantity}</span>
              {weighed ? ` ${t("kgUnit")}` : ""}
            </span>
            <span className={styles.name}>{name}</span>
            {unsure ? <Tag variant="unverified">{t("unsureTag")}</Tag> : null}
          </span>
          {showRead ? (
            <span className={styles.read}>{t("readAs", { text: row.input_text })}</span>
          ) : null}
        </span>
      </label>
    </li>
  );
}

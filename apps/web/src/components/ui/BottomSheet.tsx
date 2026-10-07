"use client";

import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { IconClose } from "./icons";
import styles from "./BottomSheet.module.css";

export type BottomSheetProps = {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  /** Small line above the title ("רמת גמישות לפריט"). */
  eyebrow?: ReactNode;
  children?: ReactNode;
  /** Sticky action area (buttons). */
  footer?: ReactNode;
  /** Hide the close button when the footer already has a cancel action. */
  hideCloseButton?: boolean;
  className?: string;
};

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Modal bottom sheet (flexibility sheet, substitution card). Accessible dialog:
 * role="dialog" + aria-modal, labelled by the title, focus moves in on open and is trapped,
 * Escape and the scrim close it, focus returns to the opener on close, page scroll is locked.
 * Centered with a max width on desktop.
 */
export function BottomSheet({
  open,
  onClose,
  title,
  eyebrow,
  children,
  footer,
  hideCloseButton,
  className,
}: BottomSheetProps) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const raf = requestAnimationFrame(() => {
      const dialog = dialogRef.current;
      if (!dialog) return;
      const first = dialog.querySelector<HTMLElement>(FOCUSABLE);
      (first ?? dialog).focus();
    });
    return () => {
      cancelAnimationFrame(raf);
      document.body.style.overflow = prevOverflow;
      opener?.focus();
    };
  }, [open]);

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Escape") {
      e.stopPropagation();
      onClose();
      return;
    }
    if (e.key !== "Tab") return;
    const dialog = dialogRef.current;
    if (!dialog) return;
    const items = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE));
    if (items.length === 0) {
      e.preventDefault();
      dialog.focus();
      return;
    }
    const first = items[0]!;
    const last = items[items.length - 1]!;
    const active = document.activeElement;
    if (e.shiftKey && (active === first || active === dialog)) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
  }

  // Sheets open on user action, so they never render during SSR.
  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div className={styles.layer} onKeyDown={onKeyDown}>
      <div
        className={styles.scrim}
        onClick={onClose}
        aria-hidden="true"
        data-testid="sheet-scrim"
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={[styles.sheet, className].filter(Boolean).join(" ")}
      >
        <div className={styles.handle} aria-hidden="true" />
        <div className={styles.header}>
          <div className={styles.titles}>
            {eyebrow ? <div className={styles.eyebrow}>{eyebrow}</div> : null}
            <h2 id={titleId} className={styles.title}>
              {title}
            </h2>
          </div>
          {hideCloseButton ? null : (
            <button type="button" className={styles.close} onClick={onClose} aria-label="סגירה">
              <IconClose size={18} />
            </button>
          )}
        </div>
        <div className={styles.body}>{children}</div>
        {footer ? <div className={styles.footer}>{footer}</div> : null}
      </div>
    </div>,
    document.body,
  );
}

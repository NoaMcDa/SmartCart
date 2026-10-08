"use client";

import { useState } from "react";
import type { ParsedRow } from "@/api/client";
import { Button } from "@/components/ui";
import { useT } from "@/i18n/LocaleProvider";
import { photoMessages } from "@/i18n/messages/photo";
import { listActions, useList } from "@/state/list";
import { CameraIcon } from "./CameraIcon";
import { PhotoSheet } from "./PhotoSheet";

export type PhotoEntryProps = {
  /** Said once rows were added ("נוספו N פריטים מהצילום…"), for the list builder's status line. */
  onAdded?: (message: string) => void;
  /** "להקליד במקום": put the cursor in the list input. */
  onTypeInstead?: () => void;
};

/**
 * The "מצילום" button of the list builder and the sheet behind it (receipt and handwritten list
 * photos, issues #61 and #68). Confirmed rows go straight into the list store, where uncertain
 * matches show the list's normal amber confirmation.
 */
export function PhotoEntry({ onAdded, onTypeInstead }: PhotoEntryProps) {
  const t = useT(photoMessages);
  const { state } = useList();
  const [open, setOpen] = useState(false);

  function add(rows: ParsedRow[]) {
    listActions.add(rows);
    setOpen(false);
    onAdded?.(t("addedHint", { count: rows.length }));
  }

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        iconStart={<CameraIcon size={16} />}
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        data-testid="photo-open"
      >
        {t("entryButton")}
      </Button>
      <PhotoSheet
        open={open}
        onClose={() => setOpen(false)}
        onAdd={add}
        onTypeInstead={onTypeInstead}
        flexDefaults={state.flexDefaults}
      />
    </>
  );
}

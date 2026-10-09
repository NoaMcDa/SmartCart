"use client";

import { useT } from "@/i18n/LocaleProvider";
import { phase2Messages, type Phase2MessageKey } from "@/i18n/messages/phase2";
import pageStyles from "./phase2.module.css";

/** The `<h1>` of a phase 2 route, in the UI language (the page itself is a server component). */
export function PageTitle({ id }: { id: Phase2MessageKey }) {
  const t = useT(phase2Messages);
  return <h1 className={pageStyles.title}>{t(id)}</h1>;
}

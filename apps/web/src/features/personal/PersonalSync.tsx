"use client";

import { useEffect, useRef } from "react";
import { getPersonal as fetchPersonal, putPersonal, type PersonalData } from "@/api/client";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { useAuth } from "@/features/auth/AuthProvider";
import {
  EMPTY_DOC,
  docKey,
  isEmptyHistory,
  mergeDocs,
  normalizeDoc,
  sanitizeDoc,
  type PersonalDoc,
} from "./personalDoc";
import { getPersonal, personalActions, usePersonal } from "./personalState";

const PUSH_DELAY_MS = 800;

const isDefaultPrefs = (doc: PersonalDoc) =>
  doc.prefs.learn && !doc.prefs.value_packs && doc.prefs.updated_at === null;

/**
 * Renders nothing. While signed in, keeps the account copy of the person's habits
 * (`/me/personal`) and the device copy as one document: on sign-in the two are merged (trips and
 * signals by id, the newer preferences win) and the device copy is replaced by the union; afterwards
 * each change is sent after a short pause. Anonymous visitors never reach it: without a session
 * this component makes no request and the habits stay on the device.
 *
 * Nothing is sent when the merged document equals what the account already holds, and a document
 * with no history and default preferences is never created on the account.
 */
export function PersonalSync() {
  const { status } = useAuth();
  const { doc } = usePersonal();
  const hydrated = useRef(false);
  const lastSent = useRef<string>("");

  useEffect(() => {
    if (status !== "signed-in") {
      hydrated.current = false;
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        ensureApiAuth();
        const server = await fetchPersonal();
        if (cancelled) return;
        const serverDoc = server.exists ? sanitizeDoc(server) : EMPTY_DOC;
        const local = getPersonal();
        const merged = mergeDocs(local, serverDoc);
        if (docKey(merged) !== docKey(local)) personalActions.replace(merged);
        const worthStoring = !(isEmptyHistory(merged) && isDefaultPrefs(merged));
        if (docKey(merged) !== docKey(serverDoc) && (server.exists || worthStoring)) {
          await putPersonal(merged as PersonalData);
          if (cancelled) return;
        }
        lastSent.current = docKey(merged);
        // Signed out (or another account) while this ran: it must not mark the next session as
        // loaded, or that session's first local change would be pushed over its stored document.
        if (cancelled) return;
        hydrated.current = true;
      } catch {
        // Offline or API down: stay on the device, try again on the next sign-in or change.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [status]);

  useEffect(() => {
    if (status !== "signed-in" || !hydrated.current) return;
    const key = docKey(doc);
    if (key === lastSent.current) return;
    const timer = setTimeout(() => {
      void putPersonal(normalizeDoc(doc) as PersonalData)
        .then(() => {
          lastSent.current = key;
        })
        .catch(() => undefined);
    }, PUSH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [status, doc]);

  return null;
}

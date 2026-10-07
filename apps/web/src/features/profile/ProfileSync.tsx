"use client";

import { useEffect, useRef } from "react";
import { useTheme } from "@/components/theme/ThemeProvider";
import { useAuth } from "@/features/auth/AuthProvider";
import { getListState, listActions, useFlexDefaults } from "@/state/list";
import {
  fetchServerProfile,
  fromServerProfile,
  pushServerProfile,
  toProfileUpdate,
} from "./profileApi";
import { getProfile, updateProfile, useProfile } from "./profileState";

/**
 * Renders nothing. Mirrors the local profile and the remembered flexibility defaults to
 * PUT /me/profile while signed in:
 * - on sign-in it loads the stored profile; if one exists it replaces the local copy (and the
 *   theme and the flexibility defaults), otherwise the local answers are uploaded;
 * - afterwards each local change is pushed after a short pause.
 */
export function ProfileSync() {
  const { status } = useAuth();
  const profile = useProfile();
  const flex = useFlexDefaults();
  const { preference, setPreference } = useTheme();
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
        const server = await fetchServerProfile();
        if (cancelled) return;
        if (server.exists) {
          updateProfile(fromServerProfile(server, getProfile()));
          // Replace the remembered category defaults with the stored ones.
          const stored = server.flex_defaults ?? {};
          const current = getListState().flexDefaults;
          for (const id of Object.keys(current)) {
            if (!(id in stored)) listActions.setFlexDefault(id, null);
          }
          for (const [id, level] of Object.entries(stored)) listActions.setFlexDefault(id, level);
          setPreference(server.theme);
          lastSent.current = JSON.stringify(
            toProfileUpdate(getProfile(), server.theme, getListState().flexDefaults),
          );
        } else {
          const body = toProfileUpdate(getProfile(), preference, getListState().flexDefaults);
          await pushServerProfile(body);
          lastSent.current = JSON.stringify(body);
        }
        hydrated.current = true;
      } catch {
        // Offline or API down: stay local, try again on the next sign-in or change.
      }
    })();
    return () => {
      cancelled = true;
    };
    // preference is read once at sign-in on purpose.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  useEffect(() => {
    if (status !== "signed-in" || !hydrated.current) return;
    const body = toProfileUpdate(profile, preference, flex);
    const json = JSON.stringify(body);
    if (json === lastSent.current) return;
    const timer = setTimeout(() => {
      void pushServerProfile(body)
        .then(() => {
          lastSent.current = json;
        })
        .catch(() => undefined);
    }, 800);
    return () => clearTimeout(timer);
  }, [status, profile, preference, flex]);

  return null;
}

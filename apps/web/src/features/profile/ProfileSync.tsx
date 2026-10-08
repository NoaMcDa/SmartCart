"use client";

import { useEffect, useRef } from "react";
import { useTheme } from "@/components/theme/ThemeProvider";
import { useAuth } from "@/features/auth/AuthProvider";
import { loadBudget, saveBudget, useBudget } from "@/features/budget/budgetState";
import { getListState, listActions, useFlexDefaults } from "@/state/list";
import {
  fetchServerProfile,
  fromServerProfile,
  pushServerProfile,
  toProfileUpdate,
} from "./profileApi";
import { getProfile, updateProfile, useProfile } from "./profileState";

/**
 * Renders nothing. Mirrors the local profile, the remembered flexibility defaults and the monthly
 * budget (#70) to PUT /me/profile while signed in. `monthly_budget` is sent only when the person
 * changed it (an omitted value keeps the stored one, null clears it), never with every save:
 * - on sign-in it loads the stored profile; if one exists it replaces the local copy (and the
 *   theme and the flexibility defaults), otherwise the local answers are uploaded;
 * - afterwards each local change is pushed after a short pause.
 */
export function ProfileSync() {
  const { status } = useAuth();
  const profile = useProfile();
  const flex = useFlexDefaults();
  const budget = useBudget();
  const { preference, setPreference } = useTheme();
  const hydrated = useRef(false);
  const lastSent = useRef<string>("");
  // The budget the account holds (null = none); `monthly_budget` goes in a save only when it differs.
  const lastBudget = useRef<number | null>(null);

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
          const base = toProfileUpdate(getProfile(), server.theme, getListState().flexDefaults);
          lastSent.current = JSON.stringify(base);
          // The account's budget wins on a device that has none or another one; a device with a
          // budget the account lacks offers it once.
          const serverBudget = server.monthly_budget == null ? null : Number(server.monthly_budget);
          const local = loadBudget();
          lastBudget.current = null;
          if (serverBudget !== null && Number.isFinite(serverBudget)) {
            if (serverBudget !== local) saveBudget(serverBudget);
            lastBudget.current = serverBudget;
          } else if (local !== null) {
            await pushServerProfile({ ...base, monthly_budget: local });
            lastBudget.current = local;
          }
        } else {
          const base = toProfileUpdate(getProfile(), preference, getListState().flexDefaults);
          const local = loadBudget();
          await pushServerProfile(local === null ? base : { ...base, monthly_budget: local });
          lastSent.current = JSON.stringify(base);
          lastBudget.current = local;
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
    const base = toProfileUpdate(profile, preference, flex);
    const json = JSON.stringify(base);
    const budgetChanged = budget !== lastBudget.current;
    if (json === lastSent.current && !budgetChanged) return;
    const body = budgetChanged ? { ...base, monthly_budget: budget } : base;
    const timer = setTimeout(() => {
      void pushServerProfile(body)
        .then(() => {
          lastSent.current = json;
          lastBudget.current = budget;
        })
        .catch(() => undefined);
    }, 800);
    return () => clearTimeout(timer);
  }, [status, profile, preference, flex, budget]);

  return null;
}

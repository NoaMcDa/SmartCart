"use client";

import { useEffect, useSyncExternalStore } from "react";
import { useAuth } from "@/features/auth/AuthProvider";
import {
  getBetaState,
  getServerBetaState,
  loadBetaMembership,
  resetBetaState,
  subscribeBeta,
  type BetaState,
} from "./betaState";

/**
 * The beta membership as React state. It asks the API once the person is signed in (or when this
 * build cannot sign in at all: the mock and local development, like the other `/me` screens) and
 * forgets the answer on sign-out. Before the answer `member` is false, so nothing flashes.
 */
export function useBetaMembership(): BetaState {
  const auth = useAuth();
  const state = useSyncExternalStore(subscribeBeta, getBetaState, getServerBetaState);
  const canAsk = auth.status === "signed-in" || (!auth.configured && auth.status !== "loading");

  useEffect(() => {
    if (auth.status === "loading") return;
    if (canAsk) void loadBetaMembership();
    else resetBetaState();
  }, [auth.status, canAsk]);

  return state;
}

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

export type BetaMembershipOptions = {
  /**
   * Ask the API even with no session, when this build cannot sign in at all (the mock and local
   * development, where the API answers anonymous callers). Only the join page sets it: a person
   * opened it on purpose. Anything that is mounted in passing, like the feedback entry in Profile,
   * leaves it off, so a signed-out visit never calls `GET /me/beta`.
   */
  askWithoutSession?: boolean;
};

/**
 * The beta membership as React state. It asks the API only once the person is signed in, and
 * forgets the answer on sign-out; with no session the state is "not a member" and no request is
 * made (`GET /me/beta` needs an account). Before the answer `member` is false, so nothing flashes.
 */
export function useBetaMembership({
  askWithoutSession = false,
}: BetaMembershipOptions = {}): BetaState {
  const auth = useAuth();
  const state = useSyncExternalStore(subscribeBeta, getBetaState, getServerBetaState);
  const canAsk =
    auth.status === "signed-in" ||
    (askWithoutSession && !auth.configured && auth.status !== "loading");

  useEffect(() => {
    if (auth.status === "loading") return;
    if (canAsk) void loadBetaMembership();
    else resetBetaState();
  }, [auth.status, canAsk]);

  // Never hand out an answer that belongs to another session (or to the join page's dev lookup).
  return canAsk ? state : getServerBetaState();
}

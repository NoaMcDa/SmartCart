/**
 * "מחקי את הנתונים שלי" (issues #30 and #55, D11).
 *
 * Signed in, it erases on the server first: every saved list (DELETE /me/lists/{id}) and the
 * profile content (PUT /me/profile with the defaults, no location and consent off). Only when the
 * server confirms does it clear the device (profile, last result, shopping session, savings
 * history, list inbox), and then it calls `DELETE /me`, which removes the `profiles` row and the
 * Supabase auth user (the email address). If the first step fails, local data is kept so the user
 * can try again and the result says what failed.
 *
 * If `DELETE /me` itself fails the content is already gone but the hosted account remains: the
 * result reports `accountRowRemains` so the UI shows the hosted-account notice, and only then. In
 * every case that reaches the device step the person is signed out afterwards.
 */
import { api, ApiError, deleteMe } from "@/api/client";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { toProfileUpdate } from "./profileApi";
import { DEFAULT_PROFILE, resetProfileCache } from "./profileState";
import { clearLocalData } from "./storage";

export type DeleteResult =
  | { ok: true; signedIn: boolean; listsDeleted: number; accountRowRemains: boolean }
  | { ok: false; error: string };

export async function deleteMyData(options: {
  signedIn: boolean;
  signOut: () => Promise<void>;
}): Promise<DeleteResult> {
  let listsDeleted = 0;
  if (options.signedIn) {
    ensureApiAuth();
    try {
      const lists = await api.GET("/me/lists");
      if (lists.data === undefined || !lists.response.ok) {
        throw new ApiError(lists.response.status, lists.error);
      }
      for (const list of lists.data) {
        const res = await api.DELETE("/me/lists/{list_id}", {
          params: { path: { list_id: list.id } },
        });
        if (!res.response.ok && res.response.status !== 404) {
          throw new ApiError(res.response.status, res.error);
        }
        listsDeleted += 1;
      }
      const reset = await api.PUT("/me/profile", { body: toProfileUpdate(DEFAULT_PROFILE) });
      if (reset.data === undefined || !reset.response.ok) {
        throw new ApiError(reset.response.status, reset.error);
      }
    } catch {
      return {
        ok: false,
        error: "לא הצלחנו למחוק מהשרת. הנתונים במכשיר נשארו כדי שאפשר יהיה לנסות שוב.",
      };
    }
  }
  clearLocalData();
  resetProfileCache();
  let accountRowRemains = false;
  if (options.signedIn) {
    // Needs the token, so before signing out.
    try {
      await deleteMe();
    } catch {
      accountRowRemains = true;
    }
  }
  await options.signOut();
  return { ok: true, signedIn: options.signedIn, listsDeleted, accountRowRemains };
}

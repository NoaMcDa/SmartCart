import { API_BASE_URL } from "./helpers";

/** Fails fast, with the fix, when the demo API is not running. */
export default async function globalSetup(): Promise<void> {
  try {
    const res = await fetch(`${API_BASE_URL}/health`);
    const body = (await res.json()) as { status?: string };
    if (res.ok && body.status === "ok") return;
    throw new Error(`/health answered ${res.status}`);
  } catch (err) {
    throw new Error(
      `The demo API is not reachable at ${API_BASE_URL} (${String(err)}). ` +
        "Start it from the repo root with scripts/demo/up.sh, or set DEMO_API_BASE_URL.",
    );
  }
}

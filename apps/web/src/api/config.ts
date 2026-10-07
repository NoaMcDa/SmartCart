/**
 * API settings, read from public env vars (inlined at build time).
 * NEXT_PUBLIC_API_BASE_URL  FastAPI origin (services/api). Default: local uvicorn.
 * NEXT_PUBLIC_API_MOCK=1    answer every API call from the MSW handlers in src/mocks, in process,
 *                           on the server and in the browser. No backend needed.
 */
export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

export const API_MOCK = process.env.NEXT_PUBLIC_API_MOCK === "1";

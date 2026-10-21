/**
 * What `msw` and `@/mocks/handlers` resolve to in a build that does not have NEXT_PUBLIC_API_MOCK=1
 * (next.config.ts, `turbopack.resolveAlias`). `src/api/client.ts` imports both behind its mock
 * switch; the switch is off in production, but a bundler still follows a dynamic import, so
 * without this alias the MSW library and every mock handler (invented prices) would be built into
 * the production bundle as lazy chunks. With it they are two empty exports, and the real mock
 * transport exists only in builds that ask for it (`npm run dev:mock`, the screen-reader plan).
 */
export const handlers: never[] = [];

export async function getResponse(): Promise<undefined> {
  return undefined;
}

/** MSW server for unit tests: `server.listen()` in a test file, then call the API helpers. */
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);

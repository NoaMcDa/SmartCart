import { defineMessages } from "../messages";

/**
 * Units that `src/lib/format.ts` writes next to numbers (distance).
 * Arabic machine-drafted, needs native-speaker review (#73).
 */
export const formatMessages = defineMessages({
  he: {
    meters: "{n} מ'",
    kilometers: '{n} ק"מ',
  },
  ar: {
    meters: "{n} م",
    kilometers: "{n} كم",
  },
});

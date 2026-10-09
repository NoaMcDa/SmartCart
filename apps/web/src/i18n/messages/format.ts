import { defineMessages } from "../messages";

/**
 * Units that `src/lib/format.ts` writes next to numbers (distance), and the words that mark a distance
 * as approximate when the store is only placed at its town centre.
 * Arabic machine-drafted, needs native-speaker review (#73).
 */
export const formatMessages = defineMessages({
  he: {
    meters: "{n} מ'",
    kilometers: '{n} ק"מ',
    // A distance to a store whose point is only a town centre (`distance_approximate`).
    approxDistance: "כ־{distance}",
    approxNote: "מיקום משוער",
    approxWithNote: "{distance} · {note}",
    approxHint: "המרחק משוער: מיקום הסניף נקבע לפי מרכז היישוב ולא לפי הכתובת שלו.",
  },
  ar: {
    meters: "{n} م",
    kilometers: "{n} كم",
    approxDistance: "نحو {distance}",
    approxNote: "الموقع تقريبي",
    approxWithNote: "{distance} · {note}",
    approxHint: "المسافة تقريبية: موقع الفرع محدّد بحسب مركز البلدة وليس بحسب عنوانه.",
  },
});

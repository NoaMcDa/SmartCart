import { defineMessages } from "../messages";

/**
 * Page headings of the phase 2 routes (`app/(phase2)`): scan, alerts, share, accept. Arabic
 * machine-drafted, needs native-speaker review (#73). The browser tab title (route metadata) is
 * static on the server and stays Hebrew.
 */
export const phase2Messages = defineMessages({
  he: {
    scan: "סריקת ברקוד",
    alerts: "התראות",
    share: "שיתוף הרשימה",
    accept: "הצטרפות לרשימה משותפת",
  },
  // Arabic machine-drafted, needs native-speaker review (#73).
  ar: {
    scan: "مسح الباركود",
    alerts: "التنبيهات",
    share: "مشاركة القائمة",
    accept: "الانضمام إلى قائمة مشتركة",
  },
});

export type Phase2MessageKey = keyof (typeof phase2Messages)["he"];

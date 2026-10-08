import { defineMessages } from "../messages";

/**
 * App shell chrome besides the navigation (`nav.ts`): the skip link and the placeholder note.
 * Arabic machine-drafted, needs native-speaker review (#73).
 */
export const shellMessages = defineMessages({
  he: {
    skipLink: "דילוג לתוכן",
    underConstruction: "המסך הזה עדיין בבנייה.",
  },
  ar: {
    skipLink: "تخطي إلى المحتوى",
    underConstruction: "هذه الشاشة قيد الإنشاء بعد.",
  },
});

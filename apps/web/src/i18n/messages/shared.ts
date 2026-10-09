import { defineMessages } from "../messages";

/**
 * Short phrases that several feature screens repeat (the prefix of an update time, the checkout
 * disclaimer). Feature-specific copy lives in the feature's own module.
 * Arabic machine-drafted, needs native-speaker review (#73).
 */
export const sharedMessages = defineMessages({
  he: {
    pricesUpdated: "מחירים עודכנו",
    checkoutGoverns: "המחיר הקובע הוא בקופה.",
    reportShort: "דיווח",
  },
  ar: {
    pricesUpdated: "تم تحديث الأسعار",
    checkoutGoverns: "السعر المعتمد هو السعر عند الصندوق.",
    reportShort: "إبلاغ",
  },
});

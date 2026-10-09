import { defineMessages } from "../messages";

/**
 * Report-a-gap sheet and button (features/feedback). A trust signal on every price. Arabic
 * machine-drafted, needs native-speaker review (#73).
 */
export const feedbackMessages = defineMessages({
  he: {
    reasonPriceDiffers: "המחיר שונה",
    reasonWrongProduct: "מוצר לא נכון",
    reasonPromoWrong: "מבצע חסר או שגוי",
    subjectDefault: "המחיר שמוצג",
    eyebrow: "דיווח על פער",
    thanks: "תודה על הדיווח",
    sentBody: "הדיווח התקבל ויעזור לנו לבדוק את המחיר. לא נשנה מחיר אוטומטית בלי בדיקה.",
    close: "סגירה",
    factStore: "סניף",
    factShown: "המחיר שהוצג",
    updatedAt: "עודכן {time}",
    reasonLegend: "מה לא מסתדר? (לא חובה)",
    actualLabel: "המחיר במדף או בקופה (לא חובה)",
    noteLabel: "הערה (לא חובה)",
    sendError: "לא הצלחנו לשלוח את הדיווח. בדקי את החיבור ונסי שוב.",
    sending: "שולחת…",
    send: "שליחה",
    reportGap: "דווחי על פער",
    reportGapAria: "{label}: {subject}",
  },
  // Arabic machine-drafted, needs native-speaker review (#73).
  ar: {
    reasonPriceDiffers: "السعر مختلف",
    reasonWrongProduct: "منتج غير صحيح",
    reasonPromoWrong: "عرض ناقص أو خاطئ",
    subjectDefault: "السعر المعروض",
    eyebrow: "الإبلاغ عن فرق",
    thanks: "شكرًا على البلاغ",
    sentBody: "تم استلام البلاغ وسيساعدنا على فحص السعر. لن نغيّر السعر تلقائيًا دون فحص.",
    close: "إغلاق",
    factStore: "الفرع",
    factShown: "السعر المعروض",
    updatedAt: "حُدّث {time}",
    reasonLegend: "ما الذي لا يتطابق؟ (اختياري)",
    actualLabel: "السعر على الرف أو في الصندوق (اختياري)",
    noteLabel: "ملاحظة (اختياري)",
    sendError: "تعذّر إرسال البلاغ. تحقق من الاتصال وحاول مرة أخرى.",
    sending: "جارٍ الإرسال…",
    send: "إرسال",
    reportGap: "الإبلاغ عن فرق",
    reportGapAria: "{label}: {subject}",
  },
});

export type FeedbackMessageKey = keyof (typeof feedbackMessages)["he"];

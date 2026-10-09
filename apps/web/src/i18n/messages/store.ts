import { defineMessages } from "../messages";

/**
 * In-store mode (`features/store`): the checklist, the progress card and the finish sheet. The
 * department names come from `profile.ts` (`dept_*`); `departmentOther` is the one that is not
 * a taxonomy department.
 * Arabic machine-drafted, needs native-speaker review (#73).
 */
export const storeMessages = defineMessages({
  he: {
    title: "מצב חנות",
    emptyTitle: "אין קנייה פעילה",
    emptyBody:
      'בחרי חנות בתוצאות ההשוואה ולחצי "התחילי קנייה". הרשימה תישמר במכשיר ותעבוד גם בלי קליטה.',
    emptyCta: "לתוצאות ההשוואה",
    offline: "אין חיבור. הרשימה נשמרה במכשיר והסימונים נשמרים.",
    collectedOf: "נאספו {checked} מתוך {total}",
    inCart: "בעגלה {checked} מתוך {all}",
    progressLabel: "התקדמות הקנייה",
    missing_one: "{n} פריטים לא נמצאו בחנות הזו",
    missing_two: "{n} פריטים לא נמצאו בחנות הזו",
    missing_few: "{n} פריטים לא נמצאו בחנות הזו",
    missing_many: "{n} פריטים לא נמצאו בחנות הזו",
    substituteLabel: "תחליף",
    estimatedShort: "מחיר משוער",
    updated: "עודכן {time}",
    footer: "המחיר הקובע הוא בקופה. מחירים עודכנו {time}.",
    finish: "סיימתי לקנות",
    marked: "סומן: {name}",
    undo: "ביטול",
    sheetTitle: "סיכום הקנייה",
    backToShop: "חזרה לקנייה",
    finishConfirm: "סיום וניקוי",
    collectedDt: "נאספו",
    ofTotal: "{checked} מתוך {total}",
    itemsTotal: "סכום הפריטים שנאספו",
    netSaved: "חיסכון נטו שנרשם",
    noneCollected: "לא נאספו פריטים",
    noBaseline: "אין חנות בסיס, לכן אין חיסכון להציג",
    notCollected: "לא נאספו ({n})",
    budgetLabel: "לרשום בתקציב החודשי",
    budgetDesc:
      "יירשמו {total} {scope}, לפי המחירים שהוצגו ולא לפי קבלה. רק תאריך, חנות, סכום ומספר פריטים.",
    scopePlan: "(כל {n} הפריטים בחנות הזו, כי לא סומן דבר)",
    scopeChecked: "({n} פריטים שנאספו)",
    sheetNote: "בסיום, הרשימה נמחקת מהמכשיר והחיסכון נרשם בפרופיל. המחיר הקובע הוא בקופה.",
    departmentOther: "אחר",
  },
  // Machine-drafted; needs native-speaker review (#73).
  ar: {
    title: "وضع المتجر",
    emptyTitle: "لا يوجد تسوق نشط",
    emptyBody:
      "اختر متجرًا من نتائج المقارنة واضغط «ابدأ التسوق». ستُحفظ القائمة على جهازك وتعمل حتى بدون تغطية.",
    emptyCta: "إلى نتائج المقارنة",
    offline: "لا يوجد اتصال. القائمة محفوظة على الجهاز والعلامات تُحفظ.",
    collectedOf: "تم جمع {checked} من {total}",
    inCart: "في العربة {checked} من {all}",
    progressLabel: "تقدّم التسوق",
    missing_one: "{n} صنف غير موجود في هذا المتجر",
    missing_two: "صنفان غير موجودين في هذا المتجر",
    missing_few: "{n} أصناف غير موجودة في هذا المتجر",
    missing_many: "{n} صنفًا غير موجود في هذا المتجر",
    substituteLabel: "بديل",
    estimatedShort: "سعر تقديري",
    updated: "تم التحديث {time}",
    footer: "السعر المعتمد هو السعر عند الصندوق. تم تحديث الأسعار {time}.",
    finish: "انتهيت من التسوق",
    marked: "تم التأشير: {name}",
    undo: "تراجع",
    sheetTitle: "ملخص التسوق",
    backToShop: "العودة إلى التسوق",
    finishConfirm: "إنهاء ومسح",
    collectedDt: "تم جمعه",
    ofTotal: "{checked} من {total}",
    itemsTotal: "مجموع الأصناف التي جُمعت",
    netSaved: "التوفير الصافي المسجّل",
    noneCollected: "لم يُجمع أي صنف",
    noBaseline: "لا يوجد متجر أساسي، لذلك لا يوجد توفير لعرضه",
    notCollected: "لم تُجمع ({n})",
    budgetLabel: "تسجيل في الميزانية الشهرية",
    budgetDesc:
      "سيُسجَّل {total} {scope}، حسب الأسعار المعروضة وليس حسب الإيصال. التاريخ والمتجر والمبلغ وعدد الأصناف فقط.",
    scopePlan: "(كل الأصناف الـ {n} في هذا المتجر، لأنه لم يُؤشَّر على شيء)",
    scopeChecked: "({n} من الأصناف التي جُمعت)",
    sheetNote:
      "عند الانتهاء تُحذف القائمة من الجهاز ويُسجَّل التوفير في الملف الشخصي. السعر المعتمد هو السعر عند الصندوق.",
    departmentOther: "أخرى",
  },
});

export type StoreMessageKey = keyof (typeof storeMessages)["he"];

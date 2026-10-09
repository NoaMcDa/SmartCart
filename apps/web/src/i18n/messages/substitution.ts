import { defineMessages } from "../messages";

/**
 * Substitution card (features/substitution): every substitute is labeled with its reason, a
 * trust signal. Arabic machine-drafted, needs native-speaker review (#73).
 */
export const substitutionMessages = defineMessages({
  he: {
    eyebrow: "החלפה <ltr>{index}</ltr> מתוך <ltr>{count}</ltr> · {chain}",
    title: "החלפנו את <b>{original}</b> ב-<b>{substitute}</b>",
    originalFallback: "המוצר המקורי",
    yourList: "ברשימה שלך",
    atYourStore: "בסופר שלך, {store}",
    noOriginalPrice: "אין מחיר להשוואה בסופר שלך",
    substituteTag: "התחליף",
    saving: "חיסכון <perUnit/> × <ltr>{quantity}</ltr> {units}",
    unitSingular: "יחידה",
    unitPlural: "יחידות",
    noSaving: "אין חיסכון במחיר המדף בהחלפה הזו",
    whyTitle: "למה זה תחליף מתאים",
    tagsLabel: "השוואת תכונות",
    sourceByName: "לפי שם המוצר בקובץ השקיפות",
    confidence: "ביטחון <ltr>{percent}</ltr>",
    priceUpdated: "מחיר עודכן",
    checkoutGoverns: "המחיר הקובע הוא בקופה.",
    methodology: "איך אנחנו מחליטים מה תחליף מתאים",
    continueLast: "בסדר, חזרה לתוצאות",
    continueNext: "בסדר, להחלפה הבאה",
    keepOriginal: "השאירי את המקורי",
    notGood: "לא תחליף טוב",

    // View states
    loading: "טוען את פרטי ההחלפה",
    loadError: "לא הצלחנו לטעון את ההחלפה.",
    retry: "נסי שוב",
    notFoundTitle: "לא מצאנו את ההחלפה הזו",
    notFoundBody:
      "ייתכן שהרשימה השתנתה מאז, או שהפריט כבר מוגדר כמוצר מדויק. אפשר לחזור לתוצאות ולראות את ההחלפות העדכניות.",
    backToResults: "חזרה לתוצאות",

    // Messages shown after the answer (actions.ts); {name} is ": <product>" or empty
    flashKept: "השארנו את המוצר המקורי{name}. הסל חושב מחדש לפי מוצר מדויק.",
    flashRejected: "תודה, הדיווח נשמר ונבדק. חזרנו למוצר המקורי{name}.",
    flashRejectFailed: "לא הצלחנו לשלוח את הדיווח, אבל חזרנו למוצר המקורי והסל חושב מחדש.",
  },
  // Arabic machine-drafted, needs native-speaker review (#73).
  ar: {
    eyebrow: "استبدال <ltr>{index}</ltr> من <ltr>{count}</ltr> · {chain}",
    title: "استبدلنا <b>{original}</b> بـ<b>{substitute}</b>",
    originalFallback: "المنتج الأصلي",
    yourList: "في قائمتك",
    atYourStore: "في سوبرماركتك، {store}",
    noOriginalPrice: "لا يوجد سعر للمقارنة في سوبرماركتك",
    substituteTag: "البديل",
    saving: "توفير <perUnit/> × <ltr>{quantity}</ltr> {units}",
    unitSingular: "وحدة",
    unitPlural: "وحدات",
    noSaving: "لا يوجد توفير في سعر الرف في هذا الاستبدال",
    whyTitle: "لماذا هو بديل مناسب",
    tagsLabel: "مقارنة الخصائص",
    sourceByName: "حسب اسم المنتج في ملف الشفافية",
    confidence: "الثقة <ltr>{percent}</ltr>",
    priceUpdated: "حُدّث السعر",
    checkoutGoverns: "السعر المعتمد هو سعر الصندوق.",
    methodology: "كيف نقرر ما هو البديل المناسب",
    continueLast: "حسنًا، العودة إلى النتائج",
    continueNext: "حسنًا، إلى الاستبدال التالي",
    keepOriginal: "إبقاء الأصلي",
    notGood: "ليس بديلًا جيدًا",

    loading: "جارٍ تحميل تفاصيل الاستبدال",
    loadError: "تعذّر تحميل الاستبدال.",
    retry: "حاول مرة أخرى",
    notFoundTitle: "لم نجد هذا الاستبدال",
    notFoundBody:
      "ربما تغيّرت القائمة منذ ذلك الحين، أو أن الصنف أصبح محدّدًا كمنتج بعينه. يمكنك العودة إلى النتائج ورؤية الاستبدالات الحالية.",
    backToResults: "العودة إلى النتائج",

    flashKept: "أبقينا المنتج الأصلي{name}. أُعيد حساب السلة حسب منتج بعينه.",
    flashRejected: "شكرًا، تم حفظ البلاغ وسيُفحص. عدنا إلى المنتج الأصلي{name}.",
    flashRejectFailed: "تعذّر إرسال البلاغ، لكننا عدنا إلى المنتج الأصلي وأُعيد حساب السلة.",
  },
});

export type SubstitutionMessageKey = keyof (typeof substitutionMessages)["he"];

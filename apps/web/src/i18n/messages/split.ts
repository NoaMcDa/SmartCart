import { defineMessages } from "../messages";

/**
 * The split view (`features/split`): the two-store board, the savings waterfall, and the reasons
 * an item cannot move (`savings.ts`, which has no React). Counted nouns live in `counts.ts`.
 * Arabic machine-drafted, needs native-speaker review (#73).
 */
export const splitMessages = defineMessages({
  he: {
    title: "פיצול סל",
    errTitle: "לא הצלחנו לחשב את הפיצול",
    errBody: "בדקי את החיבור ונסי שוב מתוצאות ההשוואה.",
    noneTitle: "אין עדיין השוואה לפצל",
    noneBody:
      "כשתשווי רשימה נציג כאן את הפיצול בין שתי חנויות, ותוכלי להזיז פריטים ביניהן ולראות איך החיסכון משתנה.",
    noSplitTitle: "אין פיצול משתלם לרשימה הזו",
    noSplitBody:
      "אחרי נסיעה ואחרי השווי של עצירה נוספת, קנייה בחנות אחת משתלמת יותר. אפשר לשנות את שווי העצירה בפרופיל.",
    backToCompare: "חזרה להשוואה",

    moveBlocked: "לא ניתן להעביר את {name}: {reason}",
    moveBlockedNoName: "לא ניתן להעביר: {reason}",
    moved: "{name} הועבר ל{store}.",
    movedNet: " חיסכון נטו ₪{net}.",
    itemFallback: "הפריט",
    otherStoreFallback: "החנות השנייה",
    restored: "הפיצול המומלץ שוחזר.",

    heroNet: "חיסכון נטו מול {home}",
    homeFallback: "החנות שלי",
    warnNoSave: "אחרי הנסיעה והעצירה הנוספת, החלוקה הזו כבר לא חוסכת. אפשר להחזיר פריטים או לאפס.",
    baselineMissing: "בלי חנות בסיס אי אפשר להציג חיסכון נטו. בחרי את הסופר שלך {link}.",
    inProfile: "בפרופיל",
    factTotal: "סה״כ לקנייה",
    factExtraTime: "זמן נוסף",
    minutes: "דק'",
    factPrices: "מחירים",
    updatedPlural: "עודכנו",
    updatedShort: "עודכן",

    hint: 'גררי פריט אל החנות השנייה, או השתמשי בכפתור "העברה" בכל שורה.',
    reset: "איפוס לפיצול המומלץ",
    tabsLabel: "חנויות בפיצול",
    subtotal: "סכום ביניים",
    emptyColumn: "אין פריטים בחנות הזו. אפשר לקנות הכול בחנות אחת.",
    estimatedShort: "מחיר משוער",
    substituteLabel: "תחליף",
    blockedBecause: "{reason}, לכן אי אפשר להעביר",
    moveTo: "העברה ל{chain}",
    moveAria: "העברת {item} ל{chain}",
    start: "התחילי קנייה ב{chain}",
    footer: "המחיר הקובע הוא בקופה. הסכומים מחושבים מהמחירים שנשמרו בהשוואה האחרונה.",

    notFoundAt: "לא נמצא ב{store}",
    noPriceAt: "אין לנו מחיר לפריט הזה ב{store}",
    storeFallback: "החנות",

    // Waterfall
    wfHeading: "מאיפה בא החיסכון",
    wfBase: "מחיר בסיס ב{home}",
    wfChain: "מעבר רשת",
    wfBrand: "החלפת מותג",
    wfPromos: "מבצעים",
    wfTravel: "עלות נסיעה",
    wfExtraStop: "שווי עצירה נוספת",
    wfNet: "חיסכון נטו",
  },
  // Machine-drafted; needs native-speaker review (#73).
  ar: {
    title: "تقسيم السلة",
    errTitle: "لم ننجح في حساب التقسيم",
    errBody: "تحقق من الاتصال وحاول مرة أخرى من نتائج المقارنة.",
    noneTitle: "لا توجد مقارنة لتقسيمها بعد",
    noneBody:
      "عندما تقارن قائمة سنعرض هنا التقسيم بين متجرين، ويمكنك نقل الأصناف بينهما ورؤية كيف يتغيّر التوفير.",
    noSplitTitle: "لا يوجد تقسيم مجدٍ لهذه القائمة",
    noSplitBody:
      "بعد احتساب السفر وقيمة التوقف الإضافي، يصبح التسوق من متجر واحد أوفر. يمكنك تغيير قيمة التوقف الإضافي من الملف الشخصي.",
    backToCompare: "العودة إلى المقارنة",

    moveBlocked: "تعذّر نقل {name}: {reason}",
    moveBlockedNoName: "تعذّر النقل: {reason}",
    moved: "تم نقل {name} إلى {store}.",
    movedNet: " التوفير الصافي ₪{net}.",
    itemFallback: "الصنف",
    otherStoreFallback: "المتجر الآخر",
    restored: "تمت استعادة التقسيم الموصى به.",

    heroNet: "التوفير الصافي مقارنةً بـ {home}",
    homeFallback: "متجري",
    warnNoSave:
      "بعد السفر والتوقف الإضافي، لم يعد هذا التقسيم يوفّر. يمكنك إعادة أصناف أو إعادة الضبط.",
    baselineMissing: "بدون متجر أساسي لا يمكن عرض التوفير الصافي. اختر سوبرماركتك من {link}.",
    inProfile: "الملف الشخصي",
    factTotal: "المجموع للشراء",
    factExtraTime: "وقت إضافي",
    minutes: "دقيقة",
    factPrices: "الأسعار",
    updatedPlural: "تم تحديثها",
    updatedShort: "تم التحديث",

    hint: "اسحب صنفًا إلى المتجر الآخر، أو استخدم زر «نقل» في كل سطر.",
    reset: "العودة إلى التقسيم الموصى به",
    tabsLabel: "المتاجر في التقسيم",
    subtotal: "المجموع الجزئي",
    emptyColumn: "لا توجد أصناف في هذا المتجر. يمكنك شراء كل شيء من متجر واحد.",
    estimatedShort: "سعر تقديري",
    substituteLabel: "بديل",
    blockedBecause: "{reason}، لذلك لا يمكن النقل",
    moveTo: "نقل إلى {chain}",
    moveAria: "نقل {item} إلى {chain}",
    start: "ابدأ التسوق في {chain}",
    footer: "السعر المعتمد هو السعر عند الصندوق. المبالغ محسوبة من الأسعار المحفوظة في آخر مقارنة.",

    notFoundAt: "غير موجود في {store}",
    noPriceAt: "لا يوجد لدينا سعر لهذا الصنف في {store}",
    storeFallback: "المتجر",

    wfHeading: "من أين يأتي التوفير",
    wfBase: "السعر الأساسي في {home}",
    wfChain: "تغيير السلسلة",
    wfBrand: "تبديل الماركة",
    wfPromos: "العروض",
    wfTravel: "تكلفة السفر",
    wfExtraStop: "قيمة التوقف الإضافي",
    wfNet: "التوفير الصافي",
  },
});

export type SplitMessageKey = keyof (typeof splitMessages)["he"];

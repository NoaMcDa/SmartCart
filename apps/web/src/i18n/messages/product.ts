import { defineMessages } from "../messages";

/**
 * Product detail (features/product): variants by unit price, the price at every store with its
 * update time, the checkout line. Arabic machine-drafted, needs native-speaker review (#73).
 */
export const productMessages = defineMessages({
  he: {
    pageTitle: "פרטי מוצר",
    categoryNav: "קטגוריה",
    addToList: "הוספה לרשימה",
    added: "נוסף לרשימה",
    loadingPrices: "טוענת מחירים",
    loadError: "לא הצלחנו לטעון את המחירים. בדקי את החיבור ונסי שוב.",
    noPrice: "אין עדיין מחיר למוצר הזה בסניפים שברדיוס שבחרת. אפשר להגדיל את הרדיוס בפרופיל.",
    variantsHeading: "וריאנטים לפי מחיר ליחידה",
    cheapestAt: "הכי זול ב{store} · נמכר ב-<ltr>{count}</ltr> סניפים",
    estimatedWeighed: "מחיר משוער (שקילה)",
    substitute: "תחליף",
    storesHeading: "מחיר בכל סניף",
    tableCaption: "מחירים לפי סניף, מהזול ליקר",
    colStore: "סניף",
    colShelf: "מחיר מדף",
    colFinal: "מחיר סופי",
    colReport: "דיווח",
    estimatedShort: "משוער",
    clubPromo: "מבצע מועדון",
    clubPromoNamed: "מבצע מועדון · {club}",
    clubOnly: "רק לחברי המועדון",
    updated: "עודכן {time}",
    reportShort: "דיווח",
    footnote: "המחיר הקובע הוא בקופה. מחירים מקבצי השקיפות של הרשתות.",
    perUnitDefault: "ליחידה",
    // Price-history store options
    historyMine: "הסניף שלי",
    historyMineChain: "הסניף שלי · {chain}",
    historyCheapest: "הכי זול בקרבתך · {chain}",
    historyBase: "מחיר בסיס של הרשת",
    // formatUpdated
    today: "היום",
  },
  // Arabic machine-drafted, needs native-speaker review (#73).
  ar: {
    pageTitle: "تفاصيل المنتج",
    categoryNav: "الفئة",
    addToList: "إضافة إلى القائمة",
    added: "تمت الإضافة إلى القائمة",
    loadingPrices: "جارٍ تحميل الأسعار",
    loadError: "تعذّر تحميل الأسعار. تحقق من الاتصال وحاول مرة أخرى.",
    noPrice:
      "لا يوجد بعد سعر لهذا المنتج في الفروع ضمن النطاق الذي اخترته. يمكنك توسيع النطاق من الملف الشخصي.",
    variantsHeading: "الأنواع حسب السعر للوحدة",
    cheapestAt: "الأرخص في {store} · يُباع في <ltr>{count}</ltr> فروع",
    estimatedWeighed: "سعر تقديري (بالوزن)",
    substitute: "بديل",
    storesHeading: "السعر في كل فرع",
    tableCaption: "الأسعار حسب الفرع، من الأرخص إلى الأغلى",
    colStore: "الفرع",
    colShelf: "سعر الرف",
    colFinal: "السعر النهائي",
    colReport: "إبلاغ",
    estimatedShort: "تقديري",
    clubPromo: "عرض لأعضاء النادي",
    clubPromoNamed: "عرض لأعضاء النادي · {club}",
    clubOnly: "لأعضاء النادي فقط",
    updated: "حُدّث {time}",
    reportShort: "إبلاغ",
    footnote: "السعر المعتمد هو سعر الصندوق. الأسعار من ملفات الشفافية التي تنشرها السلاسل.",
    perUnitDefault: "للوحدة",
    historyMine: "فرعي",
    historyMineChain: "فرعي · {chain}",
    historyCheapest: "الأرخص بالقرب منك · {chain}",
    historyBase: "السعر الأساسي للسلسلة",
    today: "اليوم",
  },
});

export type ProductMessageKey = keyof (typeof productMessages)["he"];

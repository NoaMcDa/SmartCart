import { defineMessages } from "../messages";

/**
 * Store map (features/map). Arabic machine-drafted, needs native-speaker review (#73). Brand
 * names (OpenStreetMap) stay Latin; the shekel sign and numbers stay left-to-right.
 */
export const mapMessages = defineMessages({
  he: {
    title: "מפת סניפים",
    errorTitle: "לא הצלחנו לטעון את הסניפים",
    errorBody: "בדקי את החיבור ונסי שוב מתוצאות ההשוואה.",
    toResults: "לתוצאות ההשוואה",
    emptyTitle: "אין עדיין השוואה להציג על המפה",
    emptyBody: "אחרי שתשווי רשימה נציג כאן את הסניפים שברדיוס, כל אחד עם סכום הסל שלו.",
    backToList: "חזרה לתצוגת רשימה",
    approxNote:
      "המרחק לסניף עם כתובת מדויקת נכון, אבל הכיוון שלו על המפה מוצג בקירוב עד שנוסיף כתובות סניפים מדויקות.",
    legendLabel: "מקרא המפה",
    legendExact: "סימון מלא: סניף שהכתובת שלו ידועה",
    legendApprox:
      "סימון חלול ומקווקו: מיקום משוער. מסומן אזור סביב מרכז היישוב ולא הכתובת של הסניף, והמרחק אליו הוא הערכה.",
    mapUnavailable: "המפה לא זמינה במכשיר הזה, מוצג תרשים. ",
    attribution:
      "נתוני המפה: © <osm>תורמי OpenStreetMap</osm>. הדפדפן טוען את המפה מ-OpenStreetMap, ראי <privacy>מדיניות הפרטיות</privacy>.",
    storesHeading: "הסניפים ברדיוס",
    storeRowAria: "{store}, {distance}, סל ₪{total}. לפרטים",
    recommended: "מומלץ",
    cheapest: "הכי זול",
    missingShort: "חסרים {count}",
    checkoutGoverns: "המחיר הקובע הוא בקופה.",
    toCard: "לכרטיס בתוצאות",
    startShopping: "התחילי קנייה",

    // Store details
    distance: "מרחק",
    basketTotal: "סכום הסל",
    netSavingVs: "חיסכון נטו מול {home}",
    netSaving: "חיסכון נטו",
    estimatedTravel: "הערכה, כולל נסיעה",
    pickHome: "כדי לראות חיסכון בחרי את הסופר שלך <profile>בפרופיל</profile>",
    missingItems: "חסרים {count} פריטים",
    basketComplete: "הסל מלא",
    substitutes: "{count} תחליפים",
    pricesUpdated: "מחירים עודכנו {time}",
    reportPriceGap: "דווחי על פער במחיר",

    // Pins
    pinBasket: "{chain}, סל ₪{total}",
    listSep: ", ",
    pinMissingItems: "חסרים {count} פריטים",
    pinTap: ". לחצי לפרטים",
    flagMissing: "חסרים <ltr>{count}</ltr>",
    myLocation: "המיקום שלי, מעוגל לשכונה",
    fallbackLabel: "תרשים סניפים, מפה לא זמינה במכשיר הזה",
  },
  // Arabic machine-drafted, needs native-speaker review (#73).
  ar: {
    title: "خريطة الفروع",
    errorTitle: "تعذّر تحميل الفروع",
    errorBody: "تحقق من الاتصال وحاول مرة أخرى من نتائج المقارنة.",
    toResults: "إلى نتائج المقارنة",
    emptyTitle: "لا توجد مقارنة لعرضها على الخريطة بعد",
    emptyBody: "بعد مقارنة قائمة، سنعرض هنا الفروع ضمن النطاق، لكل فرع مجموع سلّته.",
    backToList: "العودة إلى عرض القائمة",
    approxNote:
      "المسافة إلى فرع عنوانه معروف دقيقة، لكن اتجاهه على الخريطة معروض تقريبيًا إلى أن نضيف عناوين الفروع بدقة.",
    legendLabel: "دليل الخريطة",
    legendExact: "علامة ممتلئة: فرع عنوانه معروف",
    legendApprox:
      "علامة فارغة ومنقّطة: موقع تقريبي. تُعرض منطقة حول مركز البلدة وليس عنوان الفرع، والمسافة إليه تقديرية.",
    mapUnavailable: "الخريطة غير متاحة على هذا الجهاز، يُعرض مخطط بدلًا منها. ",
    attribution:
      "بيانات الخريطة: © <osm>مساهمو OpenStreetMap</osm>. يحمّل المتصفح الخريطة من OpenStreetMap، انظر <privacy>سياسة الخصوصية</privacy>.",
    storesHeading: "الفروع ضمن النطاق",
    storeRowAria: "{store}، {distance}، سلة ₪{total}. للتفاصيل",
    recommended: "موصى به",
    cheapest: "الأرخص",
    missingShort: "ينقص {count}",
    checkoutGoverns: "السعر المعتمد هو سعر الصندوق.",
    toCard: "إلى بطاقة الفرع في النتائج",
    startShopping: "ابدأ التسوّق",

    distance: "المسافة",
    basketTotal: "مجموع السلة",
    netSavingVs: "صافي التوفير مقابل {home}",
    netSaving: "صافي التوفير",
    estimatedTravel: "تقدير، يشمل السفر",
    pickHome: "لرؤية التوفير، اختر سوبرماركتك <profile>في الملف الشخصي</profile>",
    missingItems: "ينقص {count} أصناف",
    basketComplete: "السلة كاملة",
    substitutes: "{count} بدائل",
    pricesUpdated: "حُدّثت الأسعار {time}",
    reportPriceGap: "الإبلاغ عن فرق في السعر",

    pinBasket: "{chain}، سلة ₪{total}",
    listSep: "، ",
    pinMissingItems: "ينقص {count} أصناف",
    pinTap: ". اضغط للتفاصيل",
    flagMissing: "ناقص <ltr>{count}</ltr>",
    myLocation: "موقعي، مقرَّب إلى مستوى الحي",
    fallbackLabel: "مخطط الفروع، الخريطة غير متاحة على هذا الجهاز",
  },
});

export type MapMessageKey = keyof (typeof mapMessages)["he"];

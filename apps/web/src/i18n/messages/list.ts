import { defineMessages } from "../messages";

/**
 * The list builder, a list row with its confirmation, the basket estimate panel and the
 * flexibility sheet (`features/list`). The Arabic example in `placeholder` uses ASCII commas on
 * purpose: it is also the text a person may paste back into the box.
 * Arabic machine-drafted, needs native-speaker review (#73).
 */
export const listMessages = defineMessages({
  he: {
    // Builder
    placeholder: "חלב, 2 רסק עגבניות, סלמון…",
    share: "שיתוף",
    listSection: "הרשימה",
    addLabel: "הוסיפי פריטים לרשימה",
    voiceLabel: "הכתבה קולית",
    pasteLabel: "הדבקת רשימה",
    add: "הוסיפי",
    fromRecipe: "ממתכון",
    voiceUnsupported: "הכתבה קולית לא זמינה בדפדפן הזה. אפשר להקליד או להדביק את הרשימה.",
    identifying: "מזהה פריטים…",
    emptyTitle: "הרשימה ריקה",
    emptyText:
      'הדביקי רשימה או כתבי פריטים מופרדים בפסיק, למשל "{example}". נזהה כל פריט, נציע רמת גמישות ונשווה בין הסניפים הקרובים.',
    notFoundTitle: "לא זוהו",
    notFoundNote: "לא ייכללו בהשוואה",
    notFoundRow: 'לא מצאנו את "{text}"',
    notFoundHint: "נסי לכתוב אחרת או לדווח לנו על פער",
    edit: "עריכה",
    editLabel: "עריכת {text}",
    remove: "הסרה",
    removeLabel: "הסרת {text}",
    clear: "ניקוי הרשימה",
    parseFailed: "לא הצלחנו לזהות את הרשימה. בדקי את החיבור ונסי שוב.",
    dictatedAdded: "נוספו {count} פריטים מההכתבה. בדקי את הפריטים שמסומנים לאישור.",
    recipeAdded:
      'נוספו {count} פריטים מהמתכון "{title}"{portions}. בדקי את הפריטים שמסומנים לאישור.',
    recipePortions: " ל-{servings} מנות",
    clipboardEmpty: "הלוח ריק. העתיקי רשימה ונסי שוב.",
    clipboardDenied: "אין גישה ללוח. הדביקי בתיבה עם Ctrl+V או לחיצה ארוכה.",

    // Row and confirmation
    estimatedTag: "מחיר משוער · שקיל",
    kg: 'ק"ג',
    removeAria: "הסרת {name}",
    confirmGroup: "אישור הפריט {text}",
    confirmQuestion: 'כתבת "{text}". התכוונת ל{suggestion}?',
    yesAria: "כן, {suggestion}",
    yes: "כן",
    chooseOther: "בחרי אחר",
    otherOptions: "אפשרויות אחרות",

    // Estimate panel
    estimatePanel: "הערכת סל",
    estimateRange: 'הערכת סל ב-{stores} סניפים עד {km} ק"מ',
    noEstimate: "אין עדיין הערכה",
    addItems: "הוסיפי פריטים",
    atHome: "בסופר שלך, {chain}",
    cheapestNow: "הזול ביותר כרגע",
    toCheck: "פריטים לבדיקה",
    compare: "השווי",
    flexTitle: "גמישות ברשימה",
    flexNote: 'ככל שיותר פריטים ב"כל מותג", החיסכון גדל. אפשר לשנות לכל פריט בנפרד.',

    // Flexibility sheet
    sheetEyebrow: "רמת גמישות לפריט",
    sheetLegend: "רמת גמישות",
    allowLegend: "אפשר לוותר על:",
    categoryDefault: "ברירת המחדל לקטגוריה: {level}",
    appliesTo: "חל על פריטים חדשים ועל הפריטים מהסוג הזה ברשימה. אפשר לשנות בפרופיל.",
    save: "שמרי",
    cancel: "ביטול",
  },
  // Machine-drafted; needs native-speaker review (#73).
  ar: {
    placeholder: "حليب, 2 معجون بندورة, سلمون…",
    share: "مشاركة",
    listSection: "القائمة",
    addLabel: "أضف أصنافًا إلى القائمة",
    voiceLabel: "إملاء صوتي",
    pasteLabel: "لصق قائمة",
    add: "إضافة",
    fromRecipe: "من وصفة",
    voiceUnsupported: "الإملاء الصوتي غير متاح في هذا المتصفح. يمكنك كتابة القائمة أو لصقها.",
    identifying: "جارٍ التعرّف على الأصناف…",
    emptyTitle: "القائمة فارغة",
    emptyText:
      'الصق قائمة أو اكتب أصنافًا مفصولة بفاصلة، مثلًا "{example}". سنتعرّف على كل صنف ونقترح مستوى المرونة ونقارن بين الفروع القريبة.',
    notFoundTitle: "لم يُتعرَّف عليها",
    notFoundNote: "لن تُدرج في المقارنة",
    notFoundRow: 'لم نجد "{text}"',
    notFoundHint: "جرّب كتابتها بشكل مختلف أو أبلغنا عن نقص في البيانات",
    edit: "تعديل",
    editLabel: "تعديل {text}",
    remove: "إزالة",
    removeLabel: "إزالة {text}",
    clear: "مسح القائمة",
    parseFailed: "لم ننجح في التعرّف على القائمة. تحقق من الاتصال وحاول مرة أخرى.",
    dictatedAdded:
      "تمت إضافة {count} من الأصناف من الإملاء الصوتي. راجع الأصناف المعلَّمة للتأكيد.",
    recipeAdded:
      'تمت إضافة {count} من الأصناف من الوصفة "{title}"{portions}. راجع الأصناف المعلَّمة للتأكيد.',
    recipePortions: " لعدد {servings} من الحصص",
    clipboardEmpty: "الحافظة فارغة. انسخ قائمة وحاول مرة أخرى.",
    clipboardDenied: "لا يوجد وصول إلى الحافظة. الصق في الحقل بـ Ctrl+V أو بالضغط المطوّل.",

    estimatedTag: "سعر تقديري · بالوزن",
    kg: "كغ",
    removeAria: "إزالة {name}",
    confirmGroup: "تأكيد الصنف {text}",
    confirmQuestion: 'كتبت "{text}". هل تقصد {suggestion}؟',
    yesAria: "نعم، {suggestion}",
    yes: "نعم",
    chooseOther: "اختر غيره",
    otherOptions: "خيارات أخرى",

    estimatePanel: "تقدير السلة",
    estimateRange: "تقدير السلة في {stores} فروع حتى {km} كم",
    noEstimate: "لا يوجد تقدير بعد",
    addItems: "أضف أصنافًا",
    atHome: "في سوبرماركتك، {chain}",
    cheapestNow: "الأرخص حاليًا",
    toCheck: "أصناف للمراجعة",
    compare: "قارن",
    flexTitle: "المرونة في القائمة",
    flexNote: 'كلما زاد عدد الأصناف في "أي ماركة" زاد التوفير. يمكنك التغيير لكل صنف على حدة.',

    sheetEyebrow: "مستوى المرونة للصنف",
    sheetLegend: "مستوى المرونة",
    allowLegend: "يمكن التنازل عن:",
    categoryDefault: "الإعداد الافتراضي للفئة: {level}",
    appliesTo:
      "ينطبق على الأصناف الجديدة وعلى أصناف هذا النوع في القائمة. يمكنك التغيير من الملف الشخصي.",
    save: "حفظ",
    cancel: "إلغاء",
  },
});

export type ListMessageKey = keyof (typeof listMessages)["he"];

import { defineMessages } from "../messages";

/**
 * Cart handoff to a chain's own online store (issue #72). A link the browser opens, nothing
 * fetched.
 * Arabic machine-drafted, needs native-speaker review (#73).
 */
export const handoffMessages = defineMessages({
  he: {
    action: "המשך באתר הרשת",
    actionLabel: "המשך באתר של {chain}",
    sheetEyebrow: "המשך באתר הרשת",
    sheetTitle: "הרשימה שלך ב{chain}",
    intro:
      "הפריטים לא עוברים לעגלה באתר באופן אוטומטי. אפשר להעתיק את הרשימה, לשתף אותה, או לחפש כל פריט באתר של הרשת.",
    disclaimer:
      "המחירים, הזמינות ודמי המשלוח באתר הרשת עשויים להיות שונים מהמחירים בחנות, והמחיר הקובע הוא בקופה.",
    referralLabel: "קישור שותפים",
    referralNote:
      "הקישורים ל{chain} הם קישורי שותפים: ייתכן שנקבל עמלה בלי עלות נוספת עבורך. זה לא משפיע על הדירוג, על המחירים ועל החיסכון.",
    copy: "העתקת הרשימה",
    copied: "הרשימה הועתקה.",
    copyFailed: "לא הצלחנו להעתיק אוטומטית. סימנו את הרשימה, אפשר להעתיק אותה ידנית.",
    share: "שיתוף בטלפון",
    shareTitle: "רשימת קניות ל{chain}",
    openSite: "לאתר הרשת",
    textLabel: "הרשימה להעתקה",
    itemsTitle: "חיפוש פריט באתר",
    searchItem: "חיפוש באתר",
    searchItemLabel: "חיפוש {name} באתר של {chain}",
    noItems: "אין פריטים לשלוח מהחנות הזו.",
    listLine: "{name} × {quantity}",
  },
  // Machine-drafted; needs native-speaker review (#73).
  ar: {
    action: "المتابعة في موقع السلسلة",
    actionLabel: "المتابعة في موقع {chain}",
    sheetEyebrow: "المتابعة في موقع السلسلة",
    sheetTitle: "قائمتك في {chain}",
    intro:
      "لا تنتقل الأصناف إلى العربة في الموقع تلقائيًا. يمكنك نسخ القائمة أو مشاركتها أو البحث عن كل صنف في موقع السلسلة.",
    disclaimer:
      "قد تختلف الأسعار والتوفر ورسوم التوصيل في موقع السلسلة عن الأسعار في المتجر، والسعر المعتمد هو السعر عند الصندوق.",
    referralLabel: "رابط شراكة",
    referralNote:
      "الروابط إلى {chain} هي روابط شراكة: قد نحصل على عمولة دون أي تكلفة إضافية عليك. هذا لا يؤثر على الترتيب أو الأسعار أو التوفير.",
    copy: "نسخ القائمة",
    copied: "تم نسخ القائمة.",
    copyFailed: "لم ننجح في النسخ تلقائيًا. حدّدنا القائمة، ويمكنك نسخها يدويًا.",
    share: "مشاركة عبر الهاتف",
    shareTitle: "قائمة تسوق لـ {chain}",
    openSite: "إلى موقع السلسلة",
    textLabel: "القائمة للنسخ",
    itemsTitle: "البحث عن صنف في الموقع",
    searchItem: "بحث في الموقع",
    searchItemLabel: "البحث عن {name} في موقع {chain}",
    noItems: "لا توجد أصناف لإرسالها من هذا المتجر.",
    listLine: "{name} × {quantity}",
  },
});

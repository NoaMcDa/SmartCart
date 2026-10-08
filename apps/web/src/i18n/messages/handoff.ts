import { defineMessages } from "../messages";

/** Cart handoff to a chain's own online store (issue #72). A link the browser opens, nothing fetched. */
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
  // TODO ar: copy of the Hebrew; needs translation and native-speaker review (#73).
  ar: {
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
});

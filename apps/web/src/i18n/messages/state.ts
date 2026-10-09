import { defineMessages } from "../messages";

/**
 * User-facing text produced by `src/state/{flex,list,shopper}.ts`: the flexibility sheet copy, the
 * soft attributes a user may allow to differ, the "remember" label and fallbacks.
 * Arabic machine-drafted, needs native-speaker review (#73).
 */
export const stateMessages = defineMessages({
  he: {
    otherDepartment: "שונות",
    defaultCity: "מודיעין",

    rememberGeneric: "זכרי בחירה זו לכל המוצרים מהסוג הזה",
    rememberLeaf: "זכרי בחירה זו לכל סוגי {leaf}",
    rememberLeafDefinite: "זכרי בחירה זו לכל סוגי ה{leaf}",

    exactExplanation: "רק הברקוד שבחרת, בלי החלפות.",
    exactExample: "לדוגמה: אותו יצרן, אותה אריזה ואותו גודל.",
    anyBrandExplanation: "אותו מוצר מכל יצרן, כולל מותג פרטי. התכונות החשובות נשמרות.",
    anyBrandExample: "לדוגמה: מותג פרטי במקום מותג מוכר, באותו גודל ובאותו סוג.",
    closeExplanation: "גם גודל, אריזה או הרכב קצת שונים. תמיד מסומן כתחליף.",
    closeExample: "לדוגמה: אריזה גדולה יותר או טעם דומה, עם הסבר מה שונה.",

    milkExactExplanation: "רק הברקוד שבחרת.",
    milkExactExample: "לדוגמה: תנובה, 3%, קרטון 1 ליטר.",
    milkAnyBrandExplanation: "אותו מוצר מכל יצרן.",
    milkAnyBrandExample: "תנובה, טרה, יטבתה, מותג פרטי. נשמר: 3% שומן, טרי, 1 ליטר.",
    milkCloseExplanation: "גם אחוז שומן, אריזה או גודל אחרים. תמיד מסומן כתחליף.",
    milkCloseExample: "לדוגמה: 1% או 2%, שקית במקום קרטון.",

    softPackSize: "גודל אריזה אחר",
    softPackaging: "קרטון או שקית",
    softFatPct: "אחוז שומן אחר",
    softVariety: "זן אחר",
    softPackagingType: "סוג אריזה אחר",
    softFlavor: "טעם או גרסה דומים",
  },
  ar: {
    otherDepartment: "متفرقات",
    defaultCity: "موديعين",

    rememberGeneric: "حفظ هذا الاختيار لكل المنتجات من هذا النوع",
    rememberLeaf: "حفظ هذا الاختيار لكل أنواع {leaf}",
    rememberLeafDefinite: "حفظ هذا الاختيار لكل أنواع {leaf}",

    exactExplanation: "الباركود الذي اخترته فقط، بدون بدائل.",
    exactExample: "مثال: نفس المُصنِّع ونفس العبوة ونفس الحجم.",
    anyBrandExplanation:
      "نفس المنتج من أي مُصنِّع، بما في ذلك الماركة الخاصة. تبقى الخصائص المهمة كما هي.",
    anyBrandExample: "مثال: ماركة خاصة بدل ماركة معروفة، بنفس الحجم ونفس النوع.",
    closeExplanation: "حتى لو اختلف الحجم أو العبوة أو التركيبة قليلًا. يُعلَّم دائمًا كبديل.",
    closeExample: "مثال: عبوة أكبر أو نكهة مشابهة، مع شرح لما يختلف.",

    milkExactExplanation: "الباركود الذي اخترته فقط.",
    milkExactExample: "مثال: Tnuva، 3%، علبة كرتون 1 لتر.",
    milkAnyBrandExplanation: "نفس المنتج من أي مُصنِّع.",
    milkAnyBrandExample: "Tnuva، Tara، Yotvata، ماركة خاصة. يبقى: 3% دسم، طازج، 1 لتر.",
    milkCloseExplanation: "حتى لو اختلفت نسبة الدسم أو العبوة أو الحجم. يُعلَّم دائمًا كبديل.",
    milkCloseExample: "مثال: 1% أو 2%، كيس بدل علبة كرتون.",

    softPackSize: "حجم عبوة مختلف",
    softPackaging: "كرتون أو كيس",
    softFatPct: "نسبة دسم مختلفة",
    softVariety: "صنف مختلف",
    softPackagingType: "نوع عبوة مختلف",
    softFlavor: "نكهة أو نسخة مشابهة",
  },
});

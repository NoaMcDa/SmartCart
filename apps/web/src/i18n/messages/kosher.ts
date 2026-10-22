import { defineMessages } from "../messages";

/**
 * The kosher filter (features/kosher; docs/matching.md, "Kosher"): the profile control, the label on
 * a line, a swap and a substitute, and the notes on the results. The transparency files have no
 * kosher field, so every statement here is "according to the item's name": a certification is shown
 * only when the name says it, and a name that says nothing is "unknown", never "fine".
 * Arabic machine-drafted, needs native-speaker review (#73).
 */
export const kosherMessages = defineMessages({
  he: {
    // The control (Profile, onboarding)
    levelLegend: "רמת כשרות",
    levelNone: "ללא",
    level_none: "ללא העדפה",
    level_regular: "כשר",
    level_mehadrin: "מהדרין",
    level_badatz: 'בד"ץ',
    level_badatz_eida: 'בד"ץ העדה החרדית',
    level_badatz_beit_yosef: 'בד"ץ בית יוסף',
    level_badatz_chatam_sofer: 'בד"ץ חתם סופר',
    level_badatz_agudat: 'בד"ץ אגודת ישראל',
    level_landau: "הרב לנדא",
    level_rabbanut_mehadrin: "רבנות מהדרין",
    specificLabel: "השגחה מסוימת",
    specificAny: "לא משנה",
    onlyStated: "רק מוצרים שהכשרות שלהם מצוינת בשם",
    onlyStatedHint:
      "בלי האפשרות הזו, מוצר ששמו לא מציין כשרות יוצג עם התווית ״כשרות לא ידועה — בדקו על האריזה״. איתה הוא לא יוצג בכלל, וחנות שאין בה מוצר מתאים תציג אותו כחסר.",
    passover: "כשר לפסח",
    passoverHint:
      "סינון נפרד: רק מוצר ששמו מציין ״כשר לפסח״ נחשב מתאים, ומוצר שאומר שאינו כשר לפסח לא יוצג.",
    notice:
      "קבצי הרשתות לא כוללים כשרות. אנחנו קוראים רק מילים מפורשות בשם המוצר (למשל מהדרין או בד״ץ), ולא מניחים כשרות לפי יצרן או מותג. מוצר ששמו מציין כשרות אחרת מזו שבחרת לא יוצג. אין בזה תחליף לבדיקת האריזה.",

    // The label (a line, a swap, a substitute)
    labelsAria: "כשרות",
    meets: "כשרות לפי שם המוצר: {mark}",
    unknown: "כשרות לא ידועה — בדקו על האריזה",
    passoverMeets: "כשר לפסח, לפי שם המוצר",
    passoverUnknown: "כשרות לפסח לא ידועה — בדקו על האריזה",
    markSeparator: ", ",
    mark_kosher: "כשר",
    mark_rabbanut: "רבנות",
    mark_rabbanut_mehadrin: "רבנות מהדרין",
    mark_mehadrin: "מהדרין",
    mark_badatz: 'בד"ץ',
    mark_badatz_eida: 'בד"ץ העדה החרדית',
    mark_badatz_beit_yosef: 'בד"ץ בית יוסף',
    mark_badatz_chatam_sofer: 'בד"ץ חתם סופר',
    mark_badatz_agudat: 'בד"ץ אגודת ישראל',
    mark_landau: "הרב לנדא",

    // Results
    activeNote: "סינון כשרות פעיל: {level}. לא מוצג מוצר ששמו מציין כשרות אחרת.",
    activeNoteOnlyStated: "סינון כשרות פעיל: {level}. מוצגים רק מוצרים שהכשרות שלהם מצוינת בשם.",
    activeNotePassover: "כשר לפסח",
    changeInProfile: "שינוי בפרופיל",
    missingNote: "יש בסניף, אבל לא במוצר שעומד בסינון הכשרות שלך",
    hitNone: "אין מוצר שעומד בסינון הכשרות",
    hitUnknown: "כשרות לא ידועה — בדקו על האריזה",
    hitMeets: "יש מוצר שהכשרות שלו מצוינת בשם",
  },
  // Arabic machine-drafted, needs native-speaker review (#73).
  ar: {
    levelLegend: "مستوى الكاشير",
    levelNone: "بدون",
    level_none: "بدون تفضيل",
    level_regular: "كاشير",
    level_mehadrin: "مهدرين",
    level_badatz: "بداتس",
    level_badatz_eida: "بداتس العيدا هحريديت",
    level_badatz_beit_yosef: "بداتس بيت يوسف",
    level_badatz_chatam_sofer: "بداتس حاتم سوفر",
    level_badatz_agudat: "بداتس أغودات يسرائيل",
    level_landau: "الحاخام لانداو",
    level_rabbanut_mehadrin: "مهدرين الحاخامية",
    specificLabel: "إشراف محدد",
    specificAny: "لا فرق",
    onlyStated: "فقط المنتجات التي يذكر اسمها الكاشير",
    onlyStatedHint:
      "بدون هذا الخيار، يُعرض المنتج الذي لا يذكر اسمه الكاشير مع التسمية «الكاشير غير معروف — تحققوا من العبوة». معه لا يُعرض إطلاقًا، والفرع الذي لا يوجد فيه منتج مناسب يعرضه كمفقود.",
    passover: "كاشير للفصح",
    passoverHint:
      "فلتر منفصل: فقط المنتج الذي يذكر اسمه «كاشير للفصح» يُعدّ مناسبًا، والمنتج الذي يذكر أنه ليس كاشير للفصح لا يُعرض.",
    notice:
      "ملفات السلاسل لا تتضمن الكاشير. نقرأ فقط الكلمات الصريحة في اسم المنتج (مثل مهدرين أو بداتس) ولا نفترض الكاشير بحسب المصنّع أو العلامة التجارية. المنتج الذي يذكر اسمه كاشير مختلفًا عمّا اخترته لا يُعرض. هذا لا يغني عن فحص العبوة.",

    labelsAria: "الكاشير",
    meets: "الكاشير حسب اسم المنتج: {mark}",
    unknown: "الكاشير غير معروف — تحققوا من العبوة",
    passoverMeets: "كاشير للفصح، حسب اسم المنتج",
    passoverUnknown: "الكاشير للفصح غير معروف — تحققوا من العبوة",
    markSeparator: "، ",
    mark_kosher: "كاشير",
    mark_rabbanut: "الحاخامية",
    mark_rabbanut_mehadrin: "مهدرين الحاخامية",
    mark_mehadrin: "مهدرين",
    mark_badatz: "بداتس",
    mark_badatz_eida: "بداتس العيدا هحريديت",
    mark_badatz_beit_yosef: "بداتس بيت يوسف",
    mark_badatz_chatam_sofer: "بداتس حاتم سوفر",
    mark_badatz_agudat: "بداتس أغودات يسرائيل",
    mark_landau: "الحاخام لانداو",

    activeNote: "فلتر الكاشير مفعّل: {level}. لا يُعرض منتج يذكر اسمه كاشيرًا مختلفًا.",
    activeNoteOnlyStated:
      "فلتر الكاشير مفعّل: {level}. تُعرض فقط المنتجات التي يذكر اسمها الكاشير.",
    activeNotePassover: "كاشير للفصح",
    changeInProfile: "التغيير من الملف الشخصي",
    missingNote: "موجود في الفرع، لكن ليس بمنتج يوافق فلتر الكاشير لديك",
    hitNone: "لا يوجد منتج يوافق فلتر الكاشير",
    hitUnknown: "الكاشير غير معروف — تحققوا من العبوة",
    hitMeets: "يوجد منتج يذكر اسمه الكاشير",
  },
});

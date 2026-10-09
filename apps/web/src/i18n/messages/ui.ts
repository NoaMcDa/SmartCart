import { defineMessages } from "../messages";

/**
 * Design-system components (`src/components/ui`): trust tags, update times, the quantity stepper,
 * the bottom sheet and the flexibility chips.
 * Arabic machine-drafted, needs native-speaker review (#73).
 */
export const uiMessages = defineMessages({
  he: {
    promoConfidenceTitle: "ביטחון בניתוח המבצע מקובץ המחירים",
    promoUnchecked: "לא נבדק",
    promoConfidence: "ביטחון {percent}%",

    updatedToday: "היום {time}",
    updatedYesterday: "אתמול {time}",
    updatedDaysAgo: "לפני {days} ימים",
    updatedTwoDaysAgo: "לפני {days} ימים",
    updatedPrefix: "עודכן",
    updatedUnknown: "מועד העדכון לא ידוע",

    stepperGroup: "כמות: {label}",
    stepperDecrease: "הפחיתי כמות של {label}",
    stepperIncrease: "הוסיפי כמות של {label}",
    stepperValue: "כמות {value}",

    sheetClose: "סגירה",

    flexExact: "מוצר מדויק",
    flexAnyBrand: "כל מותג",
    flexClose: "תחליף קרוב",
    flexLevelAria: "רמת גמישות: {label}",
  },
  ar: {
    promoConfidenceTitle: "درجة الثقة في تحليل العرض من ملف الأسعار",
    promoUnchecked: "لم يُفحص",
    promoConfidence: "الثقة {percent}%",

    updatedToday: "اليوم {time}",
    updatedYesterday: "أمس {time}",
    updatedDaysAgo: "قبل {days} أيام",
    updatedTwoDaysAgo: "قبل يومين",
    updatedPrefix: "تم التحديث",
    updatedUnknown: "وقت التحديث غير معروف",

    stepperGroup: "الكمية: {label}",
    stepperDecrease: "تقليل كمية {label}",
    stepperIncrease: "زيادة كمية {label}",
    stepperValue: "الكمية {value}",

    sheetClose: "إغلاق",

    flexExact: "المنتج المحدد",
    flexAnyBrand: "أي ماركة",
    flexClose: "بديل قريب",
    flexLevelAria: "مستوى المرونة: {label}",
  },
});

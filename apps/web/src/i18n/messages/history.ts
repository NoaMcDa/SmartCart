import { defineMessages } from "../messages";

/**
 * Price history block and chart (features/history). Arabic machine-drafted, needs
 * native-speaker review (#73). Prices and dates stay left-to-right islands.
 */
export const historyMessages = defineMessages({
  he: {
    title: "היסטוריית מחירים",
    rangeLabel: "טווח הזמן",
    range30: "30 יום",
    range90: "90 יום",
    metricLabel: "סוג המחיר",
    metricUnit: "ליחידה",
    metricShelf: "מדף",
    storeLabel: "הסניף:",
    loading: "טוענת את ההיסטוריה",
    loadError: "לא הצלחנו לטעון את היסטוריית המחירים. נסי שוב בעוד רגע.",
    lastUpdated: "המחיר האחרון עודכן",
    checkoutGoverns: "המחיר הקובע הוא בקופה.",

    // Chart
    axisUnit: "מחיר ליחידה",
    axisShelf: "מחיר מדף",
    axisCaption: "{axis}, בשקלים",
    axisCaptionUnit: "{axis} ({unit}), בשקלים",
    empty:
      "אין עדיין נתוני מחיר לתקופה הזו. ההיסטוריה מתחילה מהיום שבו התחלנו לאסוף מחירים, ואין השלמה של ימים קודמים.",
    promoDetail: ". מבצע: {promo}",
    promoMeta: " ({audience}, {confidence})",
    legendLabel: "מקרא",
    legendPrice: "מחיר",
    legendPromoPeriod: "תקופת מבצע",
    legendPromoDay: "יום מבצע (נקודה)",
    legendNoData: "אין נתונים",
    tooltipHint: "הצביעי על נקודת מבצע כדי לראות את פרטיה.",
    summary:
      "ב-{days} הימים האחרונים המחיר ({axis}) נע בין <min/> ל-<max/>, והמחיר האחרון הוא <latest/>.",
    summaryPromos: "היו {count} תקופות מבצע (כ-{days} ימים).",
    summaryNoPromos: "לא היו תקופות מבצע.",
    summaryGaps: "ב-{days} ימים אין נתונים, והם מסומנים כרווח בלי קו.",
    summaryNoGaps: "אין ימים חסרים.",
    gapNote: "ימים ללא נתונים מוצגים כרווח מקוקו ולא כקו ישר: לא ממלאים מחיר שלא ראינו.",
    promoListLabel: "תקופות מבצע",
    tableCaption: "נתוני המחיר לפי תאריך, מהישן לחדש",
    colDate: "תאריך",
    colPromo: "מבצע",
    none: "אין",

    // Promo labels (series.ts)
    promoEveryone: "מבצע לכולם",
    promoClub: "מבצע מועדון",
    promoClubNamed: "מבצע מועדון · {club}",
    confNotChecked: "ביטחון במבצע: לא נבדק",
    confPercent: "ביטחון במבצע: {percent}%",
  },
  // Arabic machine-drafted, needs native-speaker review (#73).
  ar: {
    title: "سجل الأسعار",
    rangeLabel: "الفترة الزمنية",
    range30: "30 يومًا",
    range90: "90 يومًا",
    metricLabel: "نوع السعر",
    metricUnit: "للوحدة",
    metricShelf: "سعر الرف",
    storeLabel: "الفرع:",
    loading: "جارٍ تحميل السجل",
    loadError: "تعذّر تحميل سجل الأسعار. حاول مرة أخرى بعد قليل.",
    lastUpdated: "آخر تحديث للسعر",
    checkoutGoverns: "السعر المعتمد هو سعر الصندوق.",

    axisUnit: "السعر للوحدة",
    axisShelf: "سعر الرف",
    axisCaption: "{axis}، بالشيكل",
    axisCaptionUnit: "{axis} ({unit})، بالشيكل",
    empty:
      "لا توجد بعد بيانات أسعار لهذه الفترة. يبدأ السجل من اليوم الذي بدأنا فيه جمع الأسعار، ولا نملأ الأيام السابقة.",
    promoDetail: ". عرض: {promo}",
    promoMeta: " ({audience}، {confidence})",
    legendLabel: "دليل الرموز",
    legendPrice: "السعر",
    legendPromoPeriod: "فترة العرض",
    legendPromoDay: "يوم عرض (نقطة)",
    legendNoData: "لا توجد بيانات",
    tooltipHint: "أشِر إلى نقطة عرض لترى تفاصيلها.",
    summary: "في آخر {days} يومًا تراوح السعر ({axis}) بين <min/> و<max/>، وآخر سعر هو <latest/>.",
    summaryPromos: "كانت هناك {count} فترات عروض (نحو {days} يومًا).",
    summaryNoPromos: "لم تكن هناك فترات عروض.",
    summaryGaps: "لا توجد بيانات في {days} أيام، وهي معلَّمة كفراغ بلا خط.",
    summaryNoGaps: "لا توجد أيام ناقصة.",
    gapNote:
      "تظهر الأيام التي لا بيانات فيها كفراغ مخطَّط وليس كخط مستقيم: لا نملأ سعرًا لم نشاهده.",
    promoListLabel: "فترات العروض",
    tableCaption: "بيانات السعر حسب التاريخ، من الأقدم إلى الأحدث",
    colDate: "التاريخ",
    colPromo: "العرض",
    none: "لا يوجد",

    promoEveryone: "عرض للجميع",
    promoClub: "عرض لأعضاء النادي",
    promoClubNamed: "عرض لأعضاء النادي · {club}",
    confNotChecked: "الثقة بالعرض: لم تُفحص",
    confPercent: "الثقة بالعرض: {percent}%",
  },
});

export type HistoryMessageKey = keyof (typeof historyMessages)["he"];

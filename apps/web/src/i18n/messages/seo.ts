import { defineMessages } from "../messages";

/**
 * Shared parts of the static SEO pages (features/seo): shell, trust note, tables, quality metric,
 * basket index, product and category pages. Arabic machine-drafted, needs native-speaker review
 * (#73).
 *
 * The server HTML of these pages is always Hebrew (it is what search engines index); these
 * messages only switch on the client after hydration. Catalog names (products, categories,
 * chains) are Hebrew data and are not translated here.
 */
export const seoMessages = defineMessages({
  he: {
    // Shell
    skipLink: "דילוג לתוכן",
    footerCommitment: "SmartCart אינה מוכרת מידע על משתמשים ואינה מדרגת לפי מי שמשלם.",
    checkoutGoverns: "המחיר הקובע הוא בקופה.",
    footerMethodology: "איך אנחנו משווים מחירים",
    footerBasketIndex: "מדד הסל החודשי",
    footerAccessibility: "הצהרת נגישות",

    // Components
    breadcrumbsLabel: "נתיב הניווט",
    home: "בית",
    trustLabel: "אמינות ועדכון",
    trustDate: "{label} <time/>.",
    trustBody:
      "<b>{checkout}</b> המחירים מגיעים מקבצי השקיפות שהרשתות מחויבות לפרסם בחוק. ייתכנו הפרשים בין המחיר כאן למחיר בסניף.",
    pricesAsOf: "המחירים נכונים לתאריך",
    catalogAsOf: "נתוני הקטלוג עודכנו בתאריך",
    ctaLabel: "בניית רשימה",
    ctaButton: "בני רשימת קניות",
    ctaMethodology: "רוצה לראות את זה על הרשימה שלך? הדביקי אותה והשוואי בין הסופרים הקרובים.",
    ctaBasket: "הסל שלך שונה מהסל הממוצע. הדביקי את הרשימה שלך וראי איפה היא זולה.",
    ctaProduct: "רוצה לדעת איפה {name} זול לך? הוסיפי אותו לרשימה והשוואי את הסל כולו.",
    ctaCategory: "קונה {name}? הדביקי את הרשימה שלך וראי איפה הכי זול לסל כולו.",
    priceCaption: "מחיר {unit} בכל רשת",
    colChain: "רשת",
    colMedian: "מחיר חציוני",
    colCheapest: "הזול ביותר",
    colStores: "סניפים",
    estimatedWeighed: "הערכה, מוצר במשקל",
    flexExact: "רק המוצר עצמו, לפי ברקוד.",
    flexAnyBrand: "אותו מוצר מכל מותג: המאפיינים החשובים נשארים זהים.",
    flexClose: "תחליף קרוב: מאפיינים משניים, כמו גודל אריזה, יכולים להשתנות.",
    noPrices:
      "עדיין לא נטענו מחירים למוצר הזה. כשקבצי השקיפות של הרשתות ייטענו, המחירים יופיעו כאן עם תאריך העדכון.",
    kindMeasured: "נמדד",
    kindEstimate: "הערכה",
    kindTarget: "יעד",
    kindLaw: "לפי החוק",
    listSep: ", ",

    // Quality metric
    qmUnavailable: "איכות ההתאמה טרם נמדדה.",
    qmUnavailableHint: "המדד יופיע כאן אחרי ההרצה הראשונה של בדיקת ההתאמות על סט ההערכה.",
    qmHeadline: "<ltr>{percent}</ltr> מההחלפות נכונות בסט ההערכה",
    qmSynthetic: " (סינתטי עד שיהיו נתונים אמיתיים)",
    qmCaption: "דיוק לפי רמת גמישות",
    qmColLevel: "רמה",
    qmColCorrect: "החלפות נכונות",
    qmColSample: "גודל המדגם",
    qmDefinition:
      "<b>הגדרה.</b> מתוך ההחלפות שהמערכת מציגה למשתמש לפי רמת גמישות, אחוז ההחלפות שסט ההערכה מסמן כנכונות לאותה רמה. החלפות שנשלחות לבדיקה אנושית אינן נספרות כמוצגות. אחוזים מעוגלים כלפי מטה.",
    qmSet: "<b>סט ההערכה.</b> <ltr>{pairs}</ltr> זוגות על <ltr>{items}</ltr> פריטים. {note}",
    qmSetSynthetic:
      "הסט נוצר מתבניות ולא מפריטים אמיתיים מהרשתות, ולכן המספר מראה שמנגנון הבדיקה פועל ושהכללים הקשיחים נשמרים, ואינו הערכה של הדיוק על מוצרים אמיתיים.",
    qmSetReal: "הסט תויג ידנית מפריטים אמיתיים.",
    qmMeasured: "<b>תאריך מדידה.</b> <time/>.",
    qmTarget:
      "<b>יעד.</b> היעד שלנו הוא דיוק של <ltr>{percent}</ltr> ברמת כל מותג<kind/>. זה יעד ולא תוצאה: הוא יימדד על נתונים אמיתיים ועל דחיות של משתמשים בבטא.",

    // Basket tables
    basketCaption: "סך הסל הקבוע בכל רשת, {month}",
    basketCaptionDate: "סך הסל הקבוע בכל רשת, {month} (מחירים נכונים לתאריך <time/>)",
    basketColTotal: "סך הסל",
    basketColDelta: "הפרש מהזולה",
    basketColPct: "הפרש באחוזים",
    includesEstimates: "כולל מחירי הערכה",
    cheapestChain: "הזולה ביותר",
    unranked: "לא מדורגות, כי חסרים להן מחירים לחלק מהסל: {list}.",
    unrankedItem: "{name} ({count} פריטים)",
    pressReport: "הדוח התמציתי לעיתונות, {month}",
    basketDefinitionCaption: "הסל הקבוע, גרסה {version}: {count} מוצרים",
    basketColProduct: "מוצר",
    basketColAmount: "כמות בסל",
    basketColUnit: "מחיר נמדד ל",

    // Product page
    productLede: "מחיר {unit} של {name} בכל רשת, לפי קבצי השקיפות של הרשתות.",
    productLedeKg: "מוצר שנמכר במשקל, והמחיר הוא הערכה לק״ג.",
    estimatedPriceWeighed: "מחיר מוערך, מוצר במשקל",
    pricesByChain: "מחירים לפי רשת",
    medianNote: "מחיר חציוני: החציון בין סניפי הרשת. מבצעים כלולים, חוץ ממבצעי מועדון.",
    sameProduct: "מה נחשב אותו מוצר",
    sameProductBody:
      'ברמת "כל מותג" אנחנו משווים רק מוצרים שהמאפיינים הבאים בהם זהים. מותג וגודל אריזה יכולים להשתנות, והמחיר מושווה ליחידת מידה.',
    productType: "סוג המוצר",
    relatedProducts: "מוצרים קרובים",

    // Category page
    categoryLede:
      "השוואת מחירים ל{name} בין רשתות הסופר, לפי קבצי השקיפות של הרשתות. בקטגוריה יש {count} מוצרים מייצגים, וכל אחד מושווה לפי מחיר ליחידת מידה.",
    subCategories: "תתי-קטגוריות",
    productsCount: "{count} מוצרים",
    popularProducts: "המוצרים הנפוצים",
    categoryProducts: "מוצרים בקטגוריה",
    startingFrom: "החל מ-<price/> {unit}",
    noPricesYet: "עדיין אין מחירים",

    // Basket index page
    biTitle: "מדד הסל החודשי",
    biLede:
      "כל חודש אנחנו מתמחרים סל קבוע של {count} מוצרי יסוד בכל רשת. הסל לא משתנה בתוך גרסה, כדי שאפשר יהיה להשוות בין חודשים. המדד מראה כמה הסל עולה בכל רשת ומה ההפרש מהזולה, ואינו חיסכון: החיסכון שלך נמדד מול החנות שלך, ברשימה שלך.",
    biPrevious: "חודשים קודמים",
    biEmptyTitle: "המדד הראשון טרם פורסם",
    biEmptyBody:
      "המדד הראשון יתפרסם אחרי שנתוני המחירים ייטענו וייבדקו. עד אז אפשר לראות כאן את הסל שיתומחר.",
    biBasket: "הסל הקבוע",
    biBasketSummary: "רשימת המוצרים והכמויות (גרסה {version})",
    biBasketNote: "הרכב הסל והכמויות נבחרו בשיקול דעת ואינם סל צריכה שנמדד <kind/>.",
    biHow: "איך המדד מחושב",
    biHow1: "המחיר של רשת לכל מוצר הוא החציוני בין סניפיה, חנויות פיזיות בלבד, ליחידת מידה.",
    biHow2: "מבצעים כלולים, חוץ ממבצעי מועדון. מחירי מוצרים במשקל הם הערכה.",
    biHow3: "רשת שחסר לה מחיר למוצר בסל לא מדורגת, והחסרים מפורטים.",
    biHow4:
      "לפני פרסום נבדקים פריטים חסרים, שינויים חריגים מהחודש הקודם ועדכניות המחירים. מדד שנכשל בבדיקה לא מתפרסם.",
    biHow5: "הפרשי מחירים בין סניפים של אותה רשת אינם מופיעים במדד.",
    biFullMethod: "המתודולוגיה המלאה",
    biUpdatedLabel: "עודכן לאחרונה:",
  },
  // Arabic machine-drafted, needs native-speaker review (#73).
  ar: {
    skipLink: "تخطَّ إلى المحتوى",
    footerCommitment: "لا تبيع SmartCart معلومات عن المستخدمين ولا ترتّب النتائج حسب من يدفع.",
    checkoutGoverns: "السعر المعتمد هو سعر الصندوق.",
    footerMethodology: "كيف نقارن الأسعار",
    footerBasketIndex: "مؤشر السلة الشهري",
    footerAccessibility: "بيان الوصول",

    breadcrumbsLabel: "مسار التنقل",
    home: "الرئيسية",
    trustLabel: "الموثوقية والتحديث",
    trustDate: "{label} <time/>.",
    trustBody:
      "<b>{checkout}</b> تأتي الأسعار من ملفات الشفافية التي تلتزم السلاسل بنشرها بموجب القانون. قد توجد فروق بين السعر هنا والسعر في الفرع.",
    pricesAsOf: "الأسعار صحيحة بتاريخ",
    catalogAsOf: "حُدّثت بيانات الكتالوج بتاريخ",
    ctaLabel: "بناء قائمة",
    ctaButton: "ابنِ قائمة تسوّق",
    ctaMethodology: "تريد أن ترى هذا على قائمتك؟ الصقها وقارن بين أقرب السوبرماركتات.",
    ctaBasket: "سلّتك تختلف عن السلة المتوسطة. الصق قائمتك وانظر أين هي أرخص.",
    ctaProduct: "تريد أن تعرف أين {name} أرخص لك؟ أضفه إلى القائمة وقارن السلة كلها.",
    ctaCategory: "تشتري {name}؟ الصق قائمتك وانظر أين الأرخص للسلة كلها.",
    priceCaption: "السعر {unit} في كل سلسلة",
    colChain: "السلسلة",
    colMedian: "السعر الوسيط",
    colCheapest: "الأرخص",
    colStores: "الفروع",
    estimatedWeighed: "تقدير، منتج بالوزن",
    flexExact: "المنتج نفسه فقط، حسب الباركود.",
    flexAnyBrand: "المنتج نفسه من أي علامة تجارية: تبقى الخصائص المهمة متطابقة.",
    flexClose: "بديل قريب: قد تتغير الخصائص الثانوية، مثل حجم العبوة.",
    noPrices:
      "لم يتم بعد تحميل أسعار لهذا المنتج. عند تحميل ملفات الشفافية للسلاسل ستظهر الأسعار هنا مع تاريخ التحديث.",
    kindMeasured: "مقيس",
    kindEstimate: "تقدير",
    kindTarget: "هدف",
    kindLaw: "بحسب القانون",
    listSep: "، ",

    qmUnavailable: "لم تُقَس جودة المطابقة بعد.",
    qmUnavailableHint: "سيظهر المؤشر هنا بعد التشغيل الأول لفحص المطابقات على مجموعة التقييم.",
    qmHeadline: "<ltr>{percent}</ltr> من الاستبدالات صحيحة في مجموعة التقييم",
    qmSynthetic: " (اصطناعية إلى أن تتوفر بيانات حقيقية)",
    qmCaption: "الدقة حسب مستوى المرونة",
    qmColLevel: "المستوى",
    qmColCorrect: "الاستبدالات الصحيحة",
    qmColSample: "حجم العيّنة",
    qmDefinition:
      "<b>التعريف.</b> من بين الاستبدالات التي يعرضها النظام للمستخدم حسب مستوى المرونة، نسبة الاستبدالات التي تعتبرها مجموعة التقييم صحيحة لذلك المستوى. الاستبدالات التي تُرسل إلى مراجعة بشرية لا تُحتسب معروضة. تُقرَّب النسب إلى الأسفل.",
    qmSet: "<b>مجموعة التقييم.</b> <ltr>{pairs}</ltr> زوجًا من <ltr>{items}</ltr> صنفًا. {note}",
    qmSetSynthetic:
      "أُنشئت المجموعة من قوالب وليس من أصناف حقيقية من السلاسل، لذلك يُظهر الرقم أن آلية الفحص تعمل وأن القواعد الصارمة تُحترم، وهو ليس تقديرًا للدقة على منتجات حقيقية.",
    qmSetReal: "وُسمت المجموعة يدويًا من أصناف حقيقية.",
    qmMeasured: "<b>تاريخ القياس.</b> <time/>.",
    qmTarget:
      "<b>الهدف.</b> هدفنا هو دقة <ltr>{percent}</ltr> على مستوى أي علامة تجارية<kind/>. هذا هدف وليس نتيجة: سيُقاس على بيانات حقيقية وعلى رفض المستخدمين في النسخة التجريبية.",

    basketCaption: "مجموع السلة الثابتة في كل سلسلة، {month}",
    basketCaptionDate: "مجموع السلة الثابتة في كل سلسلة، {month} (الأسعار صحيحة بتاريخ <time/>)",
    basketColTotal: "مجموع السلة",
    basketColDelta: "الفرق عن الأرخص",
    basketColPct: "الفرق بالنسبة المئوية",
    includesEstimates: "تشمل أسعارًا تقديرية",
    cheapestChain: "الأرخص",
    unranked: "غير مصنَّفة، لأن أسعار جزء من السلة ناقصة عندها: {list}.",
    unrankedItem: "{name} ({count} أصناف)",
    pressReport: "الملخص الصحفي، {month}",
    basketDefinitionCaption: "السلة الثابتة، الإصدار {version}: {count} منتجًا",
    basketColProduct: "المنتج",
    basketColAmount: "الكمية في السلة",
    basketColUnit: "السعر مقيس لكل",

    productLede: "السعر {unit} لـ{name} في كل سلسلة، حسب ملفات الشفافية للسلاسل.",
    productLedeKg: "منتج يُباع بالوزن، والسعر تقدير للكيلوغرام.",
    estimatedPriceWeighed: "سعر تقديري، منتج بالوزن",
    pricesByChain: "الأسعار حسب السلسلة",
    medianNote: "السعر الوسيط: الوسيط بين فروع السلسلة. العروض مشمولة، عدا عروض النادي.",
    sameProduct: "ما الذي يُعتبر المنتج نفسه",
    sameProductBody:
      'على مستوى "أي علامة تجارية" نقارن فقط المنتجات التي تتطابق فيها الخصائص التالية. يمكن أن تختلف العلامة التجارية وحجم العبوة، ويُقارَن السعر لكل وحدة قياس.',
    productType: "نوع المنتج",
    relatedProducts: "منتجات قريبة",

    categoryLede:
      "مقارنة أسعار {name} بين سلاسل السوبرماركت، حسب ملفات الشفافية للسلاسل. في هذه الفئة {count} منتجًا ممثِّلًا، ويُقارَن كل منها بالسعر لكل وحدة قياس.",
    subCategories: "الفئات الفرعية",
    productsCount: "{count} منتجات",
    popularProducts: "المنتجات الشائعة",
    categoryProducts: "منتجات الفئة",
    startingFrom: "ابتداءً من <price/> {unit}",
    noPricesYet: "لا توجد أسعار بعد",

    biTitle: "مؤشر السلة الشهري",
    biLede:
      "كل شهر نسعّر سلة ثابتة من {count} منتجًا أساسيًا في كل سلسلة. لا تتغير السلة ضمن الإصدار الواحد، لكي يمكن المقارنة بين الأشهر. يوضح المؤشر كم تكلّف السلة في كل سلسلة وما الفرق عن الأرخص، وهو ليس توفيرًا: توفيرك يُقاس مقابل متجرك، على قائمتك.",
    biPrevious: "الأشهر السابقة",
    biEmptyTitle: "لم يُنشر المؤشر الأول بعد",
    biEmptyBody:
      "سيُنشر المؤشر الأول بعد تحميل بيانات الأسعار وفحصها. حتى ذلك الحين يمكنك أن ترى هنا السلة التي ستُسعَّر.",
    biBasket: "السلة الثابتة",
    biBasketSummary: "قائمة المنتجات والكميات (الإصدار {version})",
    biBasketNote: "تركيب السلة وكمياتها اختيرا بتقدير ولا يمثلان سلة استهلاك مقيسة <kind/>.",
    biHow: "كيف يُحسب المؤشر",
    biHow1: "سعر السلسلة لكل منتج هو الوسيط بين فروعها، المتاجر الفعلية فقط، لكل وحدة قياس.",
    biHow2: "العروض مشمولة، عدا عروض النادي. أسعار المنتجات بالوزن تقديرية.",
    biHow3: "السلسلة التي ينقصها سعر منتج في السلة لا تُصنَّف، وتُذكر الأصناف الناقصة.",
    biHow4:
      "قبل النشر تُفحص الأصناف الناقصة والتغيّرات الشاذة عن الشهر السابق وحداثة الأسعار. المؤشر الذي يفشل في الفحص لا يُنشر.",
    biHow5: "فروق الأسعار بين فروع السلسلة نفسها لا تظهر في المؤشر.",
    biFullMethod: "المنهجية الكاملة",
    biUpdatedLabel: "آخر تحديث:",
  },
});

export type SeoMessageKey = keyof (typeof seoMessages)["he"];

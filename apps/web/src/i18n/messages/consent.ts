import { defineMessages } from "../messages";

/**
 * The first-visit consent sheet for the closed beta's usage events and the Profile switch that
 * turns them off (issue #40, docs/beta-plan.md section 3). The wording follows the proposed
 * consent text there and has NOT had a legal review; the Arabic carries the "translation, the
 * Hebrew governs" line (`LegalNotice`) until a lawyer has read it.
 * Arabic machine-drafted, needs native-speaker review (#73).
 */
export const consentMessages = defineMessages({
  he: {
    eyebrow: "בטא סגורה",
    title: "עוזרות לנו לבדוק את ההחלפות?",
    accept: "אני מסכימה",
    decline: "לא, תודה",
    intro:
      "כדי לבדוק אם ההחלפות שהמערכת מציעה טובות, נשמרים אצלנו אירועי שימוש בסיסיים בלבד. האפליקציה עובדת אותו דבר גם אם תסרבי.",
    storedHeading: "מה נשמר",
    stored1: "מתי נפתחה האפליקציה וכמה זמן לקח להגיע לתוצאות.",
    stored2:
      'כמה החלפות הוצגו, כמה סימנת כ"לא תחליף טוב" ועל איזה זוג מוצרים, ואיזו רמת גמישות בחרת.',
    stored3: "מזהה אקראי של הדפדפן, ומזהה המשתמש שלך אם התחברת.",
    notStoredHeading: "מה לא נשמר",
    notStored: "תוכן הרשימה שלך, טקסט חופשי, שם, כתובת, טלפון, מיקום מדויק, קבלות או מזהי מכשיר.",
    footerNote:
      "המידע נשמר בשרתים של SmartCart בלבד, לא נמכר ולא מועבר לרשתות או לאחרים, ויימחק או יהפוך לסטטיסטיקה אנונימית עד שישה חודשים אחרי סוף הבטא. אפשר לצאת בכל רגע {profile} ולבקש למחוק את כל הנתונים. {policy}",
    profileLink: "בפרופיל",
    policyLink: "למדיניות הפרטיות",

    // Profile switch
    dnt: 'הדפדפן שלך שולח אות "Do Not Track", ולכן לא נשמרים אירועי שימוש מהבטא.',
    switchLabel: "אירועי שימוש לבדיקת הבטא",
    descUnset:
      "עוד לא ענית. כל עוד לא אישרת, לא נשמר דבר. נשמרים רק אירועים בסיסיים, בלי תוכן הרשימה.",
    descSet:
      "נשמרים רק אירועים בסיסיים, בלי תוכן הרשימה ובלי טקסט חופשי. כיבוי עוצר את השליחה מיד.",
  },
  // Machine-drafted; needs native-speaker review (#73).
  ar: {
    eyebrow: "نسخة تجريبية مغلقة",
    title: "هل تساعدنا في فحص الاستبدالات؟",
    accept: "أوافق",
    decline: "لا، شكرًا",
    intro:
      "لفحص ما إذا كانت الاستبدالات التي يقترحها النظام جيدة، نحفظ لدينا أحداث استخدام أساسية فقط. يعمل التطبيق بالطريقة نفسها حتى لو رفضت.",
    storedHeading: "ما الذي يُحفظ",
    stored1: "متى فُتح التطبيق وكم استغرق الوصول إلى النتائج.",
    stored2:
      "كم استبدالًا عُرض، وكم منها علّمته «ليس بديلًا جيدًا» وعلى أي زوج من المنتجات، وأي مستوى مرونة اخترت.",
    stored3: "معرّف عشوائي للمتصفح، ومعرّف المستخدم الخاص بك إذا سجّلت الدخول.",
    notStoredHeading: "ما الذي لا يُحفظ",
    notStored:
      "محتوى قائمتك، أو نص حر، أو الاسم أو العنوان أو الهاتف أو الموقع الدقيق أو الإيصالات أو معرّفات الجهاز.",
    footerNote:
      "تُحفظ المعلومات على خوادم SmartCart فقط، ولا تُباع ولا تُنقل إلى السلاسل أو إلى أي جهة أخرى، وستُحذف أو تتحول إلى إحصاءات مجهولة خلال ستة أشهر من انتهاء النسخة التجريبية. يمكنك الانسحاب في أي وقت من {profile} وطلب حذف جميع البيانات. {policy}",
    profileLink: "الملف الشخصي",
    policyLink: "سياسة الخصوصية",

    dnt: "متصفحك يرسل إشارة «Do Not Track»، لذلك لا تُحفظ أحداث استخدام من النسخة التجريبية.",
    switchLabel: "أحداث الاستخدام لفحص النسخة التجريبية",
    descUnset:
      "لم تُجب بعد. ما دمت لم توافق لا يُحفظ شيء. تُحفظ أحداث أساسية فقط، بدون محتوى القائمة.",
    descSet: "تُحفظ أحداث أساسية فقط، بدون محتوى القائمة وبدون نص حر. الإيقاف يوقف الإرسال فورًا.",
  },
});

export type ConsentMessageKey = keyof (typeof consentMessages)["he"];

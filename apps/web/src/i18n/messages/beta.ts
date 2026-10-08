import { defineMessages } from "../messages";

/**
 * Closed beta (issue #40): the join page `/beta/join/<code>`, `/beta`, and the feedback entry.
 * The wording about events follows the consent text in docs/beta-plan.md section 3, which has NOT
 * had a legal review. Hebrew is the source; the app addresses the reader in the feminine, as the
 * rest of the screens do.
 */
const he = {
  // page
  pageTitle: "הבטא של SmartCart",
  joinTitle: "הצטרפות לבטא",
  noInviteTitle: "הצטרפות בהזמנה",
  loading: "בודקת…",
  // what the beta is
  introTitle: "על מה הבטא",
  intro:
    "לפני ההשקה אנחנו בודקים את ההתאמות של SmartCart עם קבוצה קטנה של משתמשות ומשתמשים. כשהמערכת מציעה תחליף למוצר ברשימה, ההצעה צריכה להיות באמת טובה. תחליף לא נכון עולה באמון יותר מעשרה תחליפים שלא הוצעו, ולכן בודקים אותו על רשימות אמיתיות.",
  measuredTitle: "מה אנחנו מודדים",
  measured1: 'כמה פעמים סימנת "לא תחליף טוב" מתוך כל ההחלפות שהוצגו, לפי רמת הגמישות.',
  measured2: "כמה זמן עובר מהדבקת הרשימה ועד שהתוצאות על המסך.",
  measured3: "האם חזרת להשתמש באפליקציה בשבועות הבאים.",
  eventsTitle: "אירועי שימוש והסכמה",
  events:
    "המדידה נעשית באירועי שימוש בסיסיים בלבד: מתי נפתחה האפליקציה, כמה החלפות הוצגו וכמה סומנו כלא טובות. כשתלחצי על ההצטרפות נבקש ממך אישור נפרד לכך. אפשר להצטרף גם בלי לאשר: אז לא נשמרים אירועים, ורק המשוב שתכתבי מגיע אלינו. לא נשמר תוכן הרשימה, טקסט חופשי או מיקום מדויק.",
  storedTitle: "מה נשמר עליך",
  stored:
    "מזהה המשתמש שכבר יש לך באפליקציה, הקבוצה שאליה הוזמנת ותאריך ההצטרפות. בלי שם, טלפון או כתובת. אין תשלום, ואין שינוי בשירות למי שלא בבטא.",
  feedbackNoteTitle: "משוב",
  feedbackNote:
    "משוב שתשלחי נשמר עם הקבוצה בלבד, בלי מזהה המשתמש שלך, ולכן לא נוכל למחוק אותו לבקשה. אל תכתבי בו פרטים אישיים.",
  leaveInfoTitle: "איך יוצאים",
  leaveInfo:
    'בכל רגע, בדף הזה: "יציאה מהבטא" מוחקת את הרישום שלך ומכבה את אירועי השימוש. כדי למחוק את כל הנתונים שלך, השתמשי ב"מחקי את הנתונים שלי" בפרופיל.',
  profileLink: "לפרופיל",
  privacyLink: "למדיניות הפרטיות",
  // joining
  joinButton: "הצטרפות לבטא",
  joining: "מצטרפת…",
  signInNote: "כדי להצטרף צריך להתחבר, כך שההצטרפות נשמרת בחשבון שלך.",
  signInButton: "התחברות",
  noInvite: "ההצטרפות לבטא היא בהזמנה. אם קיבלת קישור הזמנה, פתחי אותו כדי להצטרף.",
  errUnknown: "קוד ההזמנה לא מוכר. בדקי שהקישור הועתק במלואו או בקשי קישור חדש.",
  errExpired: "קוד ההזמנה פג תוקף או שכבר נוצלו כל המקומות בו. בקשי קישור חדש.",
  errSignIn: "צריך להתחבר כדי להצטרף.",
  errGeneric: "השרת החזיר שגיאה. נסי שוב בעוד רגע.",
  errOffline: "נראה שאין חיבור לשרת. בדקי את החיבור ונסי שוב.",
  // member
  memberTitle: "את בבטא",
  memberBody: "תודה שאת מצטרפת. הקבוצה שלך: {segment}. אפשר לשלוח משוב בכל רגע.",
  memberEventsOn: "אירועי השימוש מופעלים. אפשר לכבות אותם בפרופיל.",
  memberEventsOff: "אירועי השימוש כבויים, ולכן לא נאסף מידע על השימוש שלך.",
  feedbackButton: "משוב על הבטא",
  // leaving
  leaveButton: "יציאה מהבטא",
  leaveConfirm: "לצאת מהבטא? הרישום שלך יימחק ואירועי השימוש ייכבו.",
  leaveYes: "כן, לצאת",
  leaveCancel: "ביטול",
  leaving: "יוצאת…",
  leftTitle: "יצאת מהבטא",
  leftBody:
    'הרישום שלך נמחק ואירועי השימוש כבויים. האפליקציה ממשיכה לעבוד כרגיל. כדי למחוק את כל הנתונים שלך, השתמשי ב"מחקי את הנתונים שלי" בפרופיל.',
  errLeave: "לא הצלחנו לצאת מהבטא. בדקי את החיבור ונסי שוב.",
  // groups
  seg_large_family: "משפחות גדולות",
  seg_kosher: "שומרי כשרות",
  seg_periphery: "תושבי הפריפריה",
  seg_general: "משתמשים כלליים",
  // feedback sheet
  fbEyebrow: "בטא סגורה",
  fbTitle: "משוב על הבטא",
  fbSentTitle: "תודה על המשוב",
  fbSent: "המשוב התקבל. הוא נשמר עם הקבוצה שלך בלבד, בלי מזהה המשתמש.",
  fbRatingLegend: "איך החוויה עד עכשיו?",
  fbRatingOption: "{n} מתוך 5",
  fbRatingLow: "לא טובה",
  fbRatingHigh: "מצוינת",
  fbTextLabel: "מה עבד ומה לא? (לא חובה)",
  fbTextHint: "אל תכתבי שם, טלפון, כתובת או פרטים אישיים אחרים. המשוב נשמר בלי מזהה המשתמש.",
  fbCount: "{n} מתוך 1000 תווים",
  fbSend: "שליחה",
  fbSending: "שולחת…",
  fbClose: "סגירה",
  fbPickRating: "בחרי דירוג מ-1 עד 5.",
  fbError: "לא הצלחנו לשלוח את המשוב. בדקי את החיבור ונסי שוב.",
} as const;

export const betaMessages = defineMessages({
  he,
  // TODO ar: Hebrew copied until a native speaker translates it (#73).
  ar: { ...he },
});

import { defineMessages } from "../messages";

/**
 * Email one-time-code sign-in sheet (`src/features/auth/SignInSheet.tsx`).
 * Arabic machine-drafted, needs native-speaker review (#73).
 */
export const authMessages = defineMessages({
  he: {
    title: "התחברות",
    eyebrow: "כדי לשמור העדפות ורשימות בין מכשירים",
    unavailable:
      "ההתחברות לא מוגדרת בסביבה הזו. אפשר להמשיך להשתמש באפליקציה בלי חשבון: ההעדפות נשמרות במכשיר בלבד.",
    emailHint: "נשלח קוד חד-פעמי לאימייל. בלי סיסמה, ובלי שיתוף הכתובת עם אף גורם חיצוני.",
    emailLabel: "אימייל",
    sendCode: "שליחת קוד",
    sending: "שולחת…",
    codeSentTo: "שלחנו קוד אל {email}. הקלידי אותו כאן.",
    codeLabel: "קוד אימות",
    verify: "כניסה",
    verifying: "מאמתת…",
    changeEmail: "לשנות כתובת אימייל",
    errorEmailInvalid: "כתובת האימייל לא נראית תקינה.",
    errorSendFailed: "לא הצלחנו לשלוח קוד. נסי שוב בעוד רגע.",
    errorCodeFormat: "הקוד הוא ספרות בלבד, כפי שהגיע באימייל.",
    errorCodeWrong: "הקוד שגוי או שפג תוקפו.",
  },
  ar: {
    title: "تسجيل الدخول",
    eyebrow: "لحفظ التفضيلات والقوائم بين الأجهزة",
    unavailable:
      "تسجيل الدخول غير مُعدّ في هذه البيئة. يمكنك متابعة استخدام التطبيق بدون حساب: تُحفظ التفضيلات على الجهاز فقط.",
    emailHint:
      "سنرسل رمزًا لمرة واحدة إلى بريدك الإلكتروني. بدون كلمة مرور، ودون مشاركة العنوان مع أي جهة خارجية.",
    emailLabel: "البريد الإلكتروني",
    sendCode: "إرسال الرمز",
    sending: "جارٍ الإرسال…",
    codeSentTo: "أرسلنا رمزًا إلى {email}. اكتبه هنا.",
    codeLabel: "رمز التحقق",
    verify: "دخول",
    verifying: "جارٍ التحقق…",
    changeEmail: "تغيير عنوان البريد الإلكتروني",
    errorEmailInvalid: "عنوان البريد الإلكتروني لا يبدو صحيحًا.",
    errorSendFailed: "لم ننجح في إرسال الرمز. حاول مرة أخرى بعد قليل.",
    errorCodeFormat: "الرمز أرقام فقط، كما وصل في البريد الإلكتروني.",
    errorCodeWrong: "الرمز خاطئ أو انتهت صلاحيته.",
  },
});

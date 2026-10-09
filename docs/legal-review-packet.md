# Legal review packet (issues #30, #26, #40)

For the lawyer, and for the owner who sends the packet. It collects, word for word, every
user-facing text on this branch that makes a legal, consent, privacy, accessibility or price-honesty
statement, with the file it lives in, what shows it, the obligation it is meant to answer, and what
the code behind it does. It ends with a numbered list of questions. **It gives no legal conclusion**:
where it says what an obligation is, it quotes how the repository's own research describes it, and
anything the research does not contain is marked **to confirm**.

Why now: the privacy text (#30), the accessibility statement (#26) and the closed-beta consent text
(#40) each say, on the page itself or in the docs, that they have **not** had a legal review
(`docs/unblock.md`: "the legal review" is the only open part of #30; "a legal read of the statement"
is open on #26; "a legal review of the consent text" is open on #40).

Labels follow `docs/README.md`: **verified** means shown by the code or a cited source, **estimate**
means a judgement, **to confirm** means the repository does not establish it.

Every quotation below was checked against the cited file (whitespace and markup aside). A mark such
as ⟨…⟩ stands for a value the page fills in at run time (a count, a date, a name). Hebrew is quoted
as in the code, in the feminine form the app uses for the user.

## 0. Contents

1. [The obligations, as the research describes them](#1-the-obligations-as-the-research-describes-them)
2. [Privacy and consent texts (P1 to P14)](#2-privacy-and-consent-texts)
3. [Accessibility texts (A1 to A3)](#3-accessibility-texts)
4. [Price presentation and trust texts (C1 to C12)](#4-price-presentation-and-trust-texts)
5. [Texts that do not exist on this branch](#5-texts-that-do-not-exist-on-this-branch)
6. [Inconsistencies found while collecting](#6-inconsistencies-found-while-collecting)
7. [Questions for the lawyer](#7-questions-for-the-lawyer)
8. [What to send and what to ask back](#8-what-to-send-and-what-to-ask-back)

## 1. The obligations, as the research describes them

The repository's only sources on the law are two research documents of October 2026 (kept verbatim in
`docs/research/`) and their English summaries. Nothing below is a statement of what the law says.

| ID | Obligation | What the repository says | Where | To confirm |
|---|---|---|---|---|
| O1 | Privacy Protection Law and its amendment 13 | Location and receipts are sensitive: minimize data, process receipts on the device where possible, explicit consent, never sell personal data (**verified** as a research statement, not as legal text) | `docs/product-and-market.md` "Legal rules we follow"; research section 2.4; decisions D10, D11 | Which duties exactly apply to us (registration, notice, security, retention, transfer abroad, privacy officer, data subject rights); whether kosher, diet and allergen preferences are sensitive; what "explicit consent" must look like |
| O2 | Israeli standard 5568 (accessibility of sites and apps) | Equivalent to WCAG 2.0 level AA and applies to apps and sites (**verified** as a research statement); "Hazol already has an accessibility statement" | `docs/product-and-market.md`; research section 2.4; `docs/a11y-report.md` | What the statement must contain, who may certify conformance, whether our size is covered, the contact or coordinator duty, the regulations' own wording |
| O3 | Misleading presentation of prices and savings | The consumer authority said that manipulative use of the data exposes to enforcement and to misleading-claim suits by the public and by the chains; hence: show an update date, say "the price at checkout governs", label every substitute, never show an inflated saving (**verified** as a research statement) | `docs/product-and-market.md`; research section 2.4; decision D10 | The statute and the standard of "misleading" that apply; comparative-claim rules; what staleness is acceptable |
| O4 | Use of the transparency files and of chain content | The files are public by law and meant for app makers, so using them is permitted; never scrape the chains' online stores (images, descriptions), where copyright and terms of use apply (**verified** as a research statement) | `docs/product-and-market.md`; research section 2.4; `CLAUDE.md` | Attribution, trademark use of chain names, any terms of the portals |

The research sentences, verbatim.

File: `docs/product-and-market.md`

> - Avoid misleading presentation: show update date, say "price at checkout governs", label every substitute, never inflate savings.
>
> - Privacy law amendment 13: location and receipts are sensitive. Minimize data, process receipts on device where possible, explicit consent, never sell personal data.
>
> - Accessibility: Israeli standard 5568 (WCAG 2.0 AA equivalent) applies to apps and sites.

File: `docs/research/2026-10-market-research-and-product-plan.he.md`

> **הטעיה:** הרשות הבהירה שמי שישתמש במידע "באופן מניפולטיבי" יהיה חשוף לאכיפה ולתביעות הטעיה מצד הציבור ומצד הרשתות. מכאן נובעים כמה כללים: להציג תאריך עדכון, לכלול הסתייגות ש"המחיר הקובע הוא בקופה" (כמו בהזול), לסמן כל תחליף כתחליף, ולא להציג "חיסכון" מנופח.
>
> **פרטיות:** חוק הגנת הפרטיות ותיקון 13 שלו. נתוני מיקום וקבלות הם מידע רגיש, ולכן צריך מזעור מידע, עיבוד קבלות על המכשיר ככל האפשר, הסכמה מפורשת, ואיסור על מכירת מידע אישי.
>
> **נגישות:** חובת התאמת נגישות לאתרים ולאפליקציות (ת"י 5568, ברמה המקבילה ל-WCAG 2.0 AA).

## 2. Privacy and consent texts

Obligation O1 unless it says otherwise. The product has no third-party analytics or ad SDK (D11) and
sets no cookie today; preferences live in the browser's `localStorage` and, after sign-in, in the
hosted database (Supabase, region not chosen yet; the working choice in
`docs/infra-provisioning.md` section 2.1 is a European region, Frankfurt, an **estimate**). One
exception waits in the code: `apps/web/src/i18n/LocaleProvider.tsx` writes a one-year first-party
cookie for the interface language when the language is changed; nothing in the UI calls it yet
(**verified** by search), and it matters when the Arabic interface (phase 3) gets a switch.

### P1. Privacy policy page

File: `apps/web/src/app/(secondary)/privacy/page.tsx`

Shown at `/privacy`; linked from onboarding step 1, the profile and the beta consent sheet. Its own
last line says it has not had a formal legal review. Answers: O1 (notice of what is collected and why,
no sale), D10, D11.

> **מדיניות פרטיות**
>
> בקצרה: אנחנו אוספים רק מה שצריך כדי להשוות מחירים, לא מוכרים מידע על משתמשים ולא מציגים תוצאות ממומנות.
>
> **מה נשמר ולמה**
>
> **מיקום ורדיוס חיפוש.** כדי למצוא סניפים קרובים ולחשב נסיעה. נשמר רק אחרי אישור מפורש, ורק ברמת שכונה: הקואורדינטות מעוגלות לשלוש ספרות אחרי הנקודה (כ-100 מטר) לפני השמירה. מיקום מדויק אינו נשמר אף פעם. אפשר גם להזין עיר ושכונה במקום מיקום המכשיר.
>
> **הסופר שלי, מועדונים ואמצעי הגעה.** כדי לחשב חיסכון מול החנות שלך ולהציג מבצעי מועדון רק לחברים.
>
> **העדפות כשרות, תזונה ואלרגנים וברירות מחדל לגמישות.** כדי לסנן ולהתאים מוצרים. ההתאמה נשענת על מידע שחולץ אוטומטית ומסומנת "לא מאומת" כשאינה נבדקה.
>
> **רשימות קניות ותוצאות השוואה אחרונות.** במכשיר שלך, ובחשבון אם התחברת.
>
> **דיווחי פער.** כשאת מדווחת שמחיר שונה מהמדף, נשמרים הסניף, הפריט, המחיר שהוצג וההערה שכתבת, כדי שנבדוק את הנתונים. בלי מיקום.
>
> **אימייל.** רק אם בחרת להתחבר, לצורך קוד כניסה חד-פעמי.
>
> **מה אנחנו לא עושים**
>
> לא מוכרים ולא מעבירים מידע על משתמשים לצד שלישי.
>
> אין דירוג ממומן: מקום בתוצאות נקבע לפי המחיר בלבד.
>
> אין בשירות כלי פרסום או מעקב של צד שלישי.
>
> **איפה המידע נמצא**
>
> **במכשיר:** אם לא התחברת, כל ההעדפות נשמרות רק בדפדפן שלך.
>
> **בחשבון:** אם התחברת, ההעדפות והרשימות נשמרות במסד הנתונים של השירות (Supabase), עם הרשאות ברמת שורה כך שרק את יכולה לקרוא אותן.
>
> **מפה:** בעמוד המפה הדפדפן טוען אריחי מפה מ-OpenStreetMap. בקשת האריחים חושפת בפני OpenStreetMap את כתובת ה-IP ואת האזור שמוצג במפה. לא נשלח אליהם שום מידע אחר.
>
> **כמה זמן שומרים**
>
> רשימת הקנייה במצב חנות נמחקת כשמסיימים קנייה, ובכל מקרה אחרי 12 שעות.
>
> שאר ההעדפות נשמרות עד שתמחקי אותן. בפרופיל אפשר לשנות כל דבר, לכבות את השימוש במיקום ולמחוק הכול.
>
> **מחיקת הנתונים שלי**
>
> בפרופיל, תחת "פרטיות ונתונים", הכפתור "מחקי את הנתונים שלי" מוחק מהמכשיר את כל מה שנשמר, ואם התחברת גם את הרשימות השמורות ואת פרטי הפרופיל בחשבון. מחיקה מלאה של החשבון עצמו (כתובת האימייל) תתווסף בקרוב.
>
> נוסח זה מתאר את גרסת ה-MVP וטרם עבר בדיקה משפטית רשמית. המחיר הקובע הוא תמיד בקופה.

Code behind it (**verified** in the files named):

- Location is rounded to 3 decimals (about 100 m) in the browser before it is stored
  (`apps/web/src/features/profile/profileState.ts`, `roundCoord`) and again by a database trigger
  (`services/api/smartcart_api/routes/me.py`), and is stored in the account only with
  `consent_location`.
- Shopping lists, preferences and the last result are in `localStorage`; with an account they are also
  in the hosted database under row-level security.
- The store-mode list expires after 12 hours (`apps/web/src/features/store/session.ts`,
  `SESSION_TTL_MS`).
- The map page loads OpenStreetMap raster tiles from `tile.openstreetmap.org`
  (`apps/web/src/features/map/MapCanvas.tsx`).

### P2. Profile: "Privacy and data" section and the delete-my-data flow

File: `apps/web/src/features/profile/PrivacySection.tsx`

Shown in `/profile`, under the heading "פרטיות ונתונים". Answers: O1 (consent, withdrawal, deletion).

> אנחנו לא מוכרים מידע על משתמשים, לא משתפים אותו עם מפרסמים ולא מציגים תוצאות ממומנות. המיקום נשמר רק ברמת שכונה ורק באישורך. אין בשירות כלי מעקב או פרסום של צד שלישי. למדיניות הפרטיות המלאה
>
> שימוש במיקום
>
> המיקום נשמר מעוגל לשכונה (כ-100 מטר). כיבוי מוחק את המיקום השמור.
>
> ייצוא הנתונים שלי
>
> מחקי את הנתונים שלי
>
> אי אפשר לבטל
>
> למחוק את כל הנתונים שלי?
>
> יימחקו מהמכשיר: המיקום, הרשת והמועדונים, העדפות הכשרות והתזונה, ברירות המחדל, תוצאת ההשוואה האחרונה, הקנייה הפעילה והחיסכון שנצבר.
>
> וגם מהחשבון: כל הרשימות השמורות, פרטי הפרופיל והחשבון עצמו, כולל כתובת האימייל. בסיום תתנתקי.
>
> ביטול
>
> כן, למחוק

After the confirmation (same file):

> הנתונים נמחקו מהמכשיר
>
> החשבון עצמו, כולל כתובת האימייל, נמחק.
>
> הנתונים נמחקו, אבל לא הצלחנו למחוק את החשבון המאוחסן עצמו (כתובת האימייל). התחברי שוב ונסי שוב מהפרופיל.

File: `apps/web/src/features/profile/deleteData.ts`

> לא הצלחנו למחוק מהשרת. הנתונים במכשיר נשארו כדי שאפשר יהיה לנסות שוב.

Code behind it (**verified**): signed in, the flow deletes every saved list and resets the profile on
the server first, then clears the device, then calls `DELETE /me`
(`services/api/smartcart_api/routes/me_delete.py`), which deletes the account and, through cascades,
push subscriptions, price alerts, shares, lists, profile, preferences, substitution feedback and
spend entries. Rows in `events` and `gap_reports` keep existing with the user id set to NULL
(anonymous), and the export button downloads the profile and the savings history as JSON from the
device.

### P3. Onboarding: the "why we ask" texts and the location controls

File: `apps/web/src/features/onboarding/OnboardingFlow.tsx`

Shown at `/onboarding`, three skippable steps; each step has a "למה אנחנו שואלים" box. Answers: O1
(purpose limitation, consent before location, the manual alternative).

> ברוכים הבאים
>
> שלוש שאלות קצרות כדי שההשוואה הראשונה תהיה שלך. אפשר לדלג על כל שלב ולחזור אליו בפרופיל.
>
> איפה את קונה?
>
> כדי להציג סניפים קרובים אליך ולחשב כמה עולה להגיע אליהם. המיקום נשמר רק ברמת שכונה (מעוגל לכ-100 מטר), רק אחרי שאישרת, ואפשר למחוק אותו בכל רגע. לא מוכרים נתונים ולא משתפים אותם. מדיניות הפרטיות
>
> הסופר שלי והמועדונים
>
> כדי לחשב את החיסכון מול החנות שבה את קונה בדרך כלל, ולהציג מבצעי מועדון רק אם את חברה בהם. בלי חנות בסיס לא נציג חיסכון, כי אנחנו לא משווים מול החנות הכי יקרה.
>
> איך את עושה קניות?
>
> כדי לדעת כמה עולה הנסיעה ואם שווה לעצור בחנות נוספת. פיצול הקנייה יוצג רק אם החיסכון נטו, אחרי נסיעה ואחרי השווי שבחרת, באמת משתלם.
>
> למה אנחנו שואלים:

File: `apps/web/src/features/profile/controls/LocationControls.tsx`

The device location is requested only on a tap of the first button, after the explanation above.

> המיקום שלי
>
> אישור שימוש במיקום המכשיר
>
> להזין עיר ושכונה במקום
>
> לא קיבלנו הרשאת מיקום, וזה בסדר. אפשר להזין עיר ושכונה ולהמשיך.
>
> המכשיר לא מספק מיקום. אפשר להזין עיר ושכונה ולהמשיך.
>
> מיקום המכשיר, מעוגל לשכונה
>
> עוד לא הגדרת מיקום.
>
> הסרת המיקום

### P4. Closed-beta usage-events consent (#40)

File: `apps/web/src/features/consent/ConsentSheet.tsx`

Shown once, as a bottom sheet, only in a build that collects beta events
(`NEXT_PUBLIC_BETA_EVENTS=1`) and when the browser does not send Do Not Track. The answer is kept in
`localStorage["sc-events-consent"]`. The file's own comment says: "it has NOT had a legal review, and
the six-month retention is a proposal." Answers: O1 (explicit consent, purpose, retention, withdrawal).

> בטא סגורה
>
> עוזרות לנו לבדוק את ההחלפות?
>
> כדי לבדוק אם ההחלפות שהמערכת מציעה טובות, נשמרים אצלנו אירועי שימוש בסיסיים בלבד. האפליקציה עובדת אותו דבר גם אם תסרבי.
>
> מה נשמר
>
> מתי נפתחה האפליקציה וכמה זמן לקח להגיע לתוצאות.
>
> כמה החלפות הוצגו, כמה סימנת כ"לא תחליף טוב" ועל איזה זוג מוצרים, ואיזו רמת גמישות בחרת.
>
> מזהה אקראי של הדפדפן, ומזהה המשתמש שלך אם התחברת.
>
> מה לא נשמר
>
> תוכן הרשימה שלך, טקסט חופשי, שם, כתובת, טלפון, מיקום מדויק, קבלות או מזהי מכשיר.
>
> המידע נשמר בשרתים של SmartCart בלבד, לא נמכר ולא מועבר לרשתות או לאחרים, ויימחק או יהפוך לסטטיסטיקה אנונימית עד שישה חודשים אחרי סוף הבטא. אפשר לצאת בכל רגע בפרופיל ולבקש למחוק את כל הנתונים. למדיניות הפרטיות
>
> אני מסכימה
>
> לא, תודה

The profile switch that withdraws it:

File: `apps/web/src/features/consent/UsageEventsControl.tsx`

> אירועי שימוש לבדיקת הבטא
>
> עוד לא ענית. כל עוד לא אישרת, לא נשמר דבר. נשמרים רק אירועים בסיסיים, בלי תוכן הרשימה.
>
> נשמרים רק אירועים בסיסיים, בלי תוכן הרשימה ובלי טקסט חופשי. כיבוי עוצר את השליחה מיד.
>
> הדפדפן שלך שולח אות "Do Not Track", ולכן לא נשמרים אירועי שימוש מהבטא.

The proposal this sheet came from (`docs/beta-plan.md` section 3, "Proposed consent text", shown there
as a text with an unchecked box; the app shows the sheet above with two buttons instead):

File: `docs/beta-plan.md`

> אני משתתפת בבטא סגורה של SmartCart. כדי לבדוק אם ההחלפות שהמערכת מציעה טובות, נשמרים אצלנו אירועי שימוש בסיסיים: מתי נפתחה האפליקציה, כמה זמן לקח להגיע לתוצאות, כמה החלפות הוצגו וכמה סימנתי כ"לא תחליף טוב" ועל איזה זוג מוצרים. לא נשמר תוכן הרשימה שלי ולא טקסט חופשי. המידע נשמר בשרתים של SmartCart בלבד, לא נמכר ולא מועבר לרשתות או לאחרים, ויימחק או יהפוך לסטטיסטיקה אנונימית עד שישה חודשים אחרי סוף הבטא. אפשר לצאת בכל רגע ולבקש למחוק את כל הנתונים שלי מהפרופיל.

Code behind it (**verified**, `docs/beta-plan.md` sections 3 and 5): events carry a name and fixed
enumerated or numeric properties; the API rejects any property not on an allowlist; the user id comes
from the sign-in token when there is one, otherwise the row has a random browser session id; the
client sends nothing against the mock API, without consent, or with Do Not Track.

### P5. Sign-in by e-mail code

File: `apps/web/src/features/auth/SignInSheet.tsx`

> התחברות
>
> כדי לשמור העדפות ורשימות בין מכשירים
>
> נשלח קוד חד-פעמי לאימייל. בלי סיסמה, ובלי שיתוף הכתובת עם אף גורם חיצוני.
>
> ההתחברות לא מוגדרת בסביבה הזו. אפשר להמשיך להשתמש באפליקציה בלי חשבון: ההעדפות נשמרות במכשיר בלבד.

File: `apps/web/src/features/alerts/AlertMe.tsx`

> התראות נשמרות בחשבון שלך, כדי שנוכל לשלוח אותן גם כשהאפליקציה סגורה. נשלח קוד חד-פעמי לאימייל, בלי סיסמה.

Code behind it: sign-in is Supabase Auth (e-mail one-time code). Which mail provider sends the code is
**to confirm** (not in the repository).

### P6. Shared lists

File: `apps/web/src/features/share/ShareSheet.tsx`

> הזמנת בני משפחה
>
> שיתוף הרשימה
>
> מי שתקבל את הקישור תתחבר, תצטרף ותראה את הרשימה ואת השינויים בה בזמן אמת. היא לא רואה את המיקום או ההעדפות שלך.
>
> כדי לשתף צריך להתחבר, כך שרק מי שהוזמנה תגיע לרשימה.

### P7. Voice dictation

File: `apps/web/src/features/voice/VoiceSheet.tsx`

Answers: O1 (disclosure of a third-party processor that the page does not control).

> הדפדפן יבקש אישור למיקרופון כשתלחצי על "התחלת הקלטה". אנחנו לא מקליטים ולא שומרים אודיו. הזיהוי נעשה בשירות הדיבור של הדפדפן (למשל בכרום, בשרתים של גוגל, לפי מדיניות הפרטיות שלו), ורק הטקסט שאישרת נשלח אלינו כמו רשימה שהודבקה.

### P8. Barcode scan with the camera

File: `apps/web/src/features/scan/ScanScreen.tsx`

> המצלמה משמשת רק לקריאת הברקוד. לא נשמרות תמונות והן לא עוזבות את המכשיר. הדפדפן יבקש אישור כשתלחצי על הכפתור.

### P9. Recipe from a link

File: `apps/web/src/features/recipe/RecipeSheet.tsx`

> הקישור נשלח לשרת שלנו כדי לקרוא את המתכון, ולא נשמר. אם הקריאה לא מצליחה, אפשר להדביק את הטקסט.

### P10. Price alerts and browser notifications

File: `apps/web/src/features/alerts/PushPanel.tsx`

> נשלח התראה למכשיר כשמוצר יורד מתחת למחיר שקבעת. הדפדפן יבקש אישור כשתלחצי על הכפתור.

### P11. Report a gap

File: `apps/web/src/features/feedback/GapReportSheet.tsx`

What the form collects: store, item, the price shown, an optional reason, an optional price seen on
the shelf and an optional free-text note of up to 300 characters.

> דיווח על פער
>
> מה לא מסתדר? (לא חובה)
>
> המחיר במדף או בקופה (לא חובה)
>
> הערה (לא חובה)
>
> הדיווח התקבל ויעזור לנו לבדוק את המחיר. לא נשנה מחיר אוטומטית בלי בדיקה.

### P12. Store mode and the monthly budget

File: `apps/web/src/features/store/StoreMode.tsx`

> לרשום בתקציב החודשי
>
> לפי המחירים שהוצגו ולא לפי קבלה. רק תאריך, חנות, סכום ומספר פריטים.
>
> בסיום, הרשימה נמחקת מהמכשיר והחיסכון נרשם בפרופיל. המחיר הקובע הוא בקופה.

File: `apps/web/src/features/budget/MonthlyBudgetSection.tsx`

> הסכומים הם לפי המחירים שהוצגו באפליקציה ברגע הקנייה, לא לפי קבלות, ולכן הם הערכה. המחיר הקובע הוא בקופה. החיסכון נטו נמדד תמיד מול הסופר שלך ואחרי נסיעה, באותה שיטה כמו ב"החיסכון שלי". שומרים רק תאריך, חנות, סכום ומספר פריטים, בלי שמות מוצרים.

### P13. Methodology page: neutrality and privacy

File: `apps/web/src/app/(seo)/methodology/page.tsx`

The full page is in C7; these are its privacy statements. They are claims about the product, so they
must stay true when the product changes.

> **פרטיות**
>
> המיקום נשמר מעוגל לרמת שכונה, ורק בהסכמה מפורשת.
>
> קבלות (בעתיד) יעובדו ויימחקו.
>
> לא נמכור מידע אישי, ואין אצלנו רשתות פרסום של צד שלישי.
>
> בבטא הסגורה אנחנו סופרים אירועים בסיסיים בשרת שלנו בלבד (למשל כמה זמן לקח להגיע לתוצאות וכמה החלפות נדחו), בלי תוכן הרשימה ובלי טקסט חופשי.
>
> אפשר למחוק את כל הנתונים מהפרופיל.

The neutrality statements are in C7 and C12.

### P14. D10 and D11, the stated product rules

File: `docs/decisions.md`

> **Decision.** Update timestamp on every price. "Price at checkout governs" footnote. Every substitute labeled and reversible with a visible "why". Confidence shown on promos and extracted attributes ("unverified"). Report-a-gap button feeding quality checks. No sale of user data. No sponsored ranking. Public methodology page and a public matching-quality metric.
>
> **Decision.** Location rounded to neighborhood. Receipts (future) processed and deleted. No third-party ad SDKs in the MVP. Explicit consent for location and receipts.

## 3. Accessibility texts

Obligation O2.

### A1. The accessibility statement

File: `apps/web/src/app/(seo)/accessibility/page.tsx`

Shown at `/accessibility`; linked from the footer of every SEO page. Answers: O2 (a statement exists;
the standard it aims at; what was and was not checked; a way to report a problem).

> **הצהרת נגישות**
>
> אנחנו רוצים ש-SmartCart תהיה שימושית לכולם. היעד שלנו הוא עמידה בתקן הישראלי 5568, שמקביל ל-WCAG 2.0 ברמה AA.
>
> נבדק לאחרונה: ⟨תאריך הבדיקה האחרונה⟩
>
> **מה נבדק**
>
> בדיקה אוטומטית (axe) של כל מסכי האתר, בטלפון ובמחשב, בערכת נושא בהירה ובכהה.
>
> ניגודיות טקסט של לפחות 4.5:1 בכל צמדי הצבעים של ערכת העיצוב, בשתי ערכות הנושא.
>
> שמות נגישים בעברית לכל כפתור שיש בו רק אייקון.
>
> משמעות לא נמסרת בצבע בלבד: ליד כל ירוק, כתום ואדום יש אייקון וטקסט.
>
> מבנה ימין לשמאל אמיתי, ומחירים ומספרים נשארים משמאל לימין בתוך טקסט עברי.
>
> יעדי מגע של לפחות 44 פיקסלים, ומיקוד מקלדת גלוי.
>
> **מה עדיין לא נבדק**
>
> מעבר ידני עם קורא מסך (VoiceOver ב-iOS ו-TalkBack ב-Android) בעברית.
>
> בדיקה משפטית של ההתאמה לתקן 5568 על ידי גורם מוסמך.
>
> השלמת כל המסכים שעדיין בבנייה: הם ייבדקו כשיושלמו.
>
> **נתקלת בבעיה?**
>
> ספרי לנו איפה ומה לא עבד, ואיזה דפדפן, קורא מסך או מכשיר השתמשת. ⟨קישור mailto אם הוגדר NEXT_PUBLIC_CONTACT_EMAIL⟩

When the build sets `NEXT_PUBLIC_CONTACT_EMAIL`, the last paragraph continues with a mailto link;
without it, it ends with the sentence below. **The contact detail is not set today** (**verified**:
`docs/a11y-report.md`).

> פרטי הקשר יפורסמו כאן לפני ההשקה.

### A2. Other texts that serve accessibility

File: `apps/web/src/components/shell/AppShell.tsx`

> דילוג לתוכן

File: `apps/web/src/components/shell/BottomNav.tsx`

The navigation landmark and the scan button are named from `apps/web/src/i18n/messages/nav.ts`
("ניווט ראשי", "סריקת ברקוד"); every icon-only button has a Hebrew `aria-label`. The test plan that
checks what a screen reader says is `docs/screen-reader-test-plan.md`.

### A3. What the audit report says it did and did not do

File: `docs/a11y-report.md`

> This is an automated audit plus a documented list of what only a person can check. **It is not a conformance claim.** The public statement (`/accessibility`) says the same.
>
> **Screen reader pass in Hebrew RTL**, not done.
>
> **A legal read** of the accessibility statement. Not done.

## 4. Price presentation and trust texts

Obligation O3 (and O4 for the data statements). The rule the research states is four-fold: an update
date, "the price at checkout governs", every substitute labeled, no inflated saving. Where each is
implemented:

### C1. "המחיר הקובע הוא בקופה" and the update date, every place they appear

The constant is defined once for the SEO pages (`CHECKOUT_GOVERNS`) and the API sends it as
`disclaimer_he`; the app screens repeat it.

File: `apps/web/src/features/seo/config.ts`

> המחיר הקובע הוא בקופה.

File: `services/api/smartcart_api/schemas.py`

> המחיר הקובע הוא בקופה.

File: `apps/web/src/app/layout.tsx`

The site description, used by search engines and when the page is shared:

> משווים את כל רשימת הקניות בסופרים הקרובים, עם חיסכון נטו לעומת הסופר שלך. המחיר הקובע הוא בקופה.

File: `apps/web/src/features/compare/ResultsView.tsx`

The footnote of the results screen (the first sentence is the API's `disclaimer_he`):

> ⟨res.disclaimer_he⟩ המחירים לפי קבצי שקיפות המחירים של הרשתות, ומבצעי מועדון רק לפי המועדונים שסימנת. החיסכון מחושב תמיד מול הסופר שלך, אחרי נסיעה.
>
> דיווח על פער במחיר

File: `apps/web/src/features/compare/SmartCartCard.tsx`

> · המחיר הקובע הוא בקופה.

File: `apps/web/src/features/substitution/SubstitutionView.tsx`

> המחיר הקובע הוא בקופה.

File: `apps/web/src/features/split/SplitView.tsx`

> המחיר הקובע הוא בקופה. הסכומים מחושבים מהמחירים שנשמרו בהשוואה האחרונה.

File: `apps/web/src/features/store/StoreMode.tsx`

> המחיר הקובע הוא בקופה. מחירים עודכנו ⟨formatTime(session.pricesUpdatedAt)⟩.

File: `apps/web/src/features/product/ProductDetail.tsx`

> המחיר הקובע הוא בקופה. מחירים מקבצי השקיפות של הרשתות.

File: `apps/web/src/features/history/PriceHistory.tsx`

> המחיר הקובע הוא בקופה.

File: `apps/web/src/features/map/MapScreen.tsx`

> המחיר הקובע הוא בקופה.

File: `apps/web/src/features/alerts/AlertMe.tsx`

> המחיר הקובע הוא בקופה. ההתראה מבוססת על מחירי קבצי השקיפות.

File: `apps/web/src/features/alerts/AlertsScreen.tsx`

> המחיר הקובע הוא בקופה. כל התראה כוללת את מועד עדכון המחיר.

File: `apps/web/src/features/budget/BudgetRemaining.tsx`

> לפי המחירים שהוצגו, לא לפי קבלות. המחיר הקובע הוא בקופה.

File: `apps/web/src/features/scan/ResultCard.tsx`

When the price the person typed differs from ours:

> ייתכן שהמחיר בקופה שונה, או שהנתונים שלנו לא מעודכנים.

File: `apps/web/src/features/seo/components.tsx`

The trust block at the foot of every SEO page (the update date comes from the data):

> ⟨label⟩ ⟨formatDateHe(updatedAt)⟩.
>
> **⟨CHECKOUT_GOVERNS⟩** המחירים מגיעים מקבצי השקיפות שהרשתות מחויבות לפרסם בחוק. ייתכנו הפרשים בין המחיר כאן למחיר בסניף.

File: `apps/web/src/app/(seo)/p/[slug]/page.tsx`

The page description of every product page, with and without prices:

> ⟨product.name_he⟩: מה נחשב אותו מוצר ואיך מושווים מחירים לפי מחיר ⟨unit⟩ בין רשתות הסופר בישראל. ⟨CHECKOUT_GOVERNS⟩
>
> מחיר ⟨product.name_he⟩ ⟨unit⟩ בכל רשת סופר בישראל, לפי קבצי השקיפות של הרשתות, עם תאריך עדכון. ⟨CHECKOUT_GOVERNS⟩

File: `apps/web/src/app/(secondary)/privacy/page.tsx`

> המחיר הקובע הוא תמיד בקופה.

### C2. The update time on a price

File: `apps/web/src/components/ui/UpdatedAt.tsx`

Every price shows when it was updated, in Israel time: "today hh:mm", "yesterday hh:mm", "N days ago"
up to a week, then the date (for example 12.09.2026). The default prefix and the formats, and the text
when the time is missing (a missing time is shown, not hidden):

> עודכן
>
> היום ⟨hhmm(d)⟩
>
> אתמול ⟨hhmm(d)⟩
>
> לפני ⟨days⟩ ימים
>
> מועד העדכון לא ידוע

Behavior (**verified**): there is no threshold above which a price is flagged as stale; a price from
a week ago is shown with its date and no warning. The ingestion side quarantines a file older than 36
hours at load (`services/ingest/smartcart_ingest/settings.py`, `stale_file_max_age_hours`).

### C3. Savings: what is claimed and against what

Rule D7 (`CLAUDE.md`): the headline number is the net saving versus the user's own store, never
versus the most expensive chain.

File: `apps/web/src/features/compare/PlanCard.tsx`

> מומלץ
>
> מינימום מאמץ · הסופר שלך
>
> הבסיס שאליו משווים
>
> חוסך ⟨breakdown.net_saving⟩
>
> לעומת ⟨homeName⟩, הסופר שלך
>
> לא זול יותר מהסופר שלך
>
> אחרי נסיעה ועצירות
>
> חיסכון בסל ⟨breakdown.basket_saving⟩, פחות ⟨travel⟩ נסיעה
>
> שווי העצירה הנוספת
>
> לא נמכר בסניף, לא נספר בסך

File: `apps/web/src/features/profile/ProfileScreen.tsx`

> עוד אין חיסכון להציג. אחרי שתסיימי קנייה במצב חנות נחשב כמה באמת חסכת, מול החנות שלך ואחרי נסיעה. אנחנו לא מציגים הערכות.

File: `apps/web/src/features/split/SplitView.tsx`

> בלי חנות בסיס אי אפשר להציג חיסכון נטו. בחרי את הסופר שלך
>
> אחרי הנסיעה והעצירה הנוספת, החלוקה הזו כבר לא חוסכת. אפשר להחזיר פריטים או לאפס.

The travel cost behind "net" is an estimate from the distance, the travel mode the person chose and
the value of an extra stop the person set (`docs/optimizer.md`). **To confirm**: whether the app must
state, next to each net saving, that the travel cost is an estimate.

### C4. Substitutes: labeling, the reason, undo

File: `apps/web/src/features/substitution/SubstitutionView.tsx`

> החלפה ⟨index + 1⟩ מתוך ⟨count⟩ · ⟨store.chain_name⟩
>
> החלפנו את **⟨originalName⟩** ב-**⟨item.display_name_he⟩**
>
> ברשימה שלך
>
> התחליף
>
> למה זה תחליף מתאים
>
> לפי שם המוצר בקובץ השקיפות
>
> · ביטחון ⟨conf⟩
>
> בסדר, חזרה לתוצאות
>
> השאירי את המקורי
>
> לא תחליף טוב
>
> איך אנחנו מחליטים מה תחליף מתאים

File: `apps/web/src/features/compare/SmartCartCard.tsx`

The reason line the smart-cart card shows for a suggested swap, by flexibility level:

> אותו סוג מוצר ואותה כמות, במותג אחר. מתאים לרמת ״כל מותג״.
>
> תחליף קרוב: מוצר דומה מאוד עם הבדל קטן באחד המאפיינים (ראי את התגיות). מתאים לרמת ״תחליף קרוב״.
>
> אותו מוצר בדיוק, במחיר נמוך יותר בסניף הזה.
>
> לא עכשיו
>
> ההחלפה בוטלה והרשימה חזרה למה שהייתה.

File: `apps/web/src/features/compare/SubstitutionsSection.tsx`

> כל החלפה ניתנת לביטול

As documented (the page above, and `docs/catalog.md` section 2): nothing is substituted without a
shown label and "why"; each swap can be undone; "לא תחליף טוב" removes the pair from comparisons until it has been reviewed; the matching
rules never relax fat percentage, fresh versus frozen, flavor or the base of a plant drink at the
"any brand" level (`docs/catalog.md` section 2). Kosher and diet flags are **not** matching rules
because the chains' files do not carry them (**verified**: `docs/catalog.md`); the app marks them
"לא מאומת".

### C5. Promo confidence, estimates, unverified attributes

File: `apps/web/src/components/ui/PromoConfidence.tsx`

> ביטחון בניתוח המבצע מקובץ המחירים
>
> ביטחון ⟨percent⟩%
>
> לא נבדק

File: `apps/web/src/features/list/ListRow.tsx`

> מחיר משוער · שקיל

File: `apps/web/src/app/(seo)/p/[slug]/page.tsx`

> מחיר מוערך, מוצר במשקל

### C6. The structured data on product pages

File: `apps/web/src/features/seo/jsonld.ts`

Search engines read these as offers: one per chain at the median unit price across the chain's
branches, with the chain as the `seller`. The site itself sells nothing.

> מחיר ⟨PER_UNIT[product.base_unit]⟩, חציון בין סניפי הרשת

### C7. Methodology page (public claims about sources, matching, saving, neutrality, quality)

File: `apps/web/src/app/(seo)/methodology/page.tsx`

Shown at `/methodology`. Answers: O3 and O4 (where the data comes from, no scraping, how a saving is
computed, what is not claimed). The page marks every number as measured, estimate, target or by law.

> **איך אנחנו משווים מחירים**
>
> כאן כתוב בלי ז׳רגון מאיפה המחירים, איך אנחנו מחליטים שמוצר מחליף מוצר אחר, איך מחושב החיסכון ומה אנחנו מתחייבים לא לעשות. כל מספר בעמוד מסומן: ⟨סימון: נמדד⟩ נמדד, ⟨סימון: הערכה⟩ הערכה, ⟨סימון: יעד⟩ יעד שעוד לא הושג, או ⟨סימון: לפי החוק⟩ נקבע בחוק.
>
> עודכן לאחרונה: ⟨תאריך העדכון האחרון⟩
>
> **מאיפה המחירים**
>
> המחירים מגיעים רק מקבצי השקיפות שהרשתות הגדולות חייבות לפרסם לפי חוק קידום התחרות בענף המזון ותקנות שקיפות המחירים. הקבצים פתוחים לציבור, ונועדו גם למי שבונה אפליקציות כמונו. אנחנו לא אוספים שום דבר מאתרי הקנייה המקוונים של הרשתות: לא מחירים, לא תמונות ולא תיאורים.
>
> הרשתות חייבות לעדכן את הקובץ תוך שעה משינוי מחיר בקופה ⟨סימון: לפי החוק⟩ . אנחנו טוענים קובץ מלא מדי לילה, ובמהלך היום גם עדכונים של הרשתות שמפרסמות אותם. על כל מחיר מוצג מתי הוא עודכן.
>
> קובץ שנכשל בבדיקות איכות (מחיר אפס, קפיצת מחיר חריגה, ירידה חדה במספר הפריטים, תאריך ישן) לא נטען: הוא נעצר בצד ונבדק.
>
> מחיר בסניף יכול להיות שונה ממחיר הרשת. אנחנו שומרים מחיר בסיס לרשת ויוצאי דופן לפי סניף. מבצעי מועדון וכרטיס אשראי מוצגים רק אם סימנת שאת חברה, עם רמת ביטחון. מוצרים במשקל מסומנים "הערכה".
>
> **המחיר הקובע הוא בקופה.** אם מצאת פער בין מה שמוצג לבין המדף, כפתור "דווחי על פער" שולח אותו לבדיקה.
>
> **איך עובדת ההתאמה**
>
> כל פריט של כל רשת משויך למוצר מייצג אחד בקטלוג שלנו ("מוצר קנוני"), עם רמת ביטחון. כך אפשר להשוות גם מוצרים של מותג הבית, שאין להם ברקוד משותף בין הרשתות. אצלך נקבע, לכל פריט ברשימה, כמה גמישות מותר:
>
> **כללים קשיחים.** מאפיינים שמגדירים את המוצר, כמו אחוז שומן, טרי מול קפוא או טעם, חייבים להיות זהים ברמת "כל מותג". דמיון בשם לא מחליף את הכלל: חלב 3% לא יוחלף בחלב 1%.
>
> **דיוק לפני כיסוי.** עדיף לפספס התאמה מאשר להציג התאמה שגויה. התאמה לא ודאית עוברת לבדיקה אנושית ולא מוצגת. כל החלפה שמוצגת מסומנת, עם הסיבה, ואפשר לבטל אותה.
>
> **מה לא מאומת.** כשרות והעדפות תזונה לא מגיעות בקבצי הרשתות בצורה מובנית, ולכן הן מסומנות "לא מאומת" ואינן כלל התאמה.
>
> לחיצה על "לא תחליף טוב" שולחת את ההתאמה לבדיקה ומוציאה אותה מההשוואות עד שתיבדק. כך משתמשים משפרים את ההתאמות לכולם.
>
> הקטלוג מכיל כרגע ⟨products.count⟩ מוצרים מייצגים ⟨סימון: נמדד⟩ . הרשימה והדירוג שלהם נבחרו בשיקול דעת ולא נמדדו ⟨סימון: הערכה⟩ , והרשימה טרם נסקרה בידי מומחה תחום.
>
> **איך מחושב החיסכון**
>
> המספר הראשי הוא **החיסכון נטו**, תמיד לעומת הסופר שאמרת שאת קונה בו בדרך כלל, ולעולם לא לעומת הרשת היקרה ביותר:
>
> **חיסכון נטו = חיסכון בסל − עלות הנסיעה − מה ששווה לך עצירה נוספת.**
>
> עלות הנסיעה נגזרת מהמרחק ומאופן ההגעה שבחרת. את שווי העצירה הנוספת את קובעת.
>
> השוואה בין מוצרים נעשית לפי מחיר ליחידת מידה (ל-100 גרם, ל-100 מ״ל, ליחידה או לק״ג), כך שגודל אריזה לא מטה את התוצאה.
>
> פיצול הקנייה בין שתי חנויות מוצג רק אם החיסכון נטו שלו עובר סף מינימלי.
>
> **ניטרליות**
>
> אנחנו לא מוכרים מידע על משתמשים, לא לרשתות ולא לאף אחד אחר.
>
> אין דירוג ממומן: סדר התוצאות נקבע לפי מחיר בלבד.
>
> אם נוסיף בעתיד קישורי שותפים לחנויות מקוונות, הם יסומנו בבירור ולא ישפיעו על הדירוג.
>
> אין ב-SmartCart כלי פרסום או מעקב של צד שלישי.
>
> **מדד איכות ההתאמה**
>
> כמה מההחלפות שאנחנו מציגים נכונות? המספר נמשך אוטומטית מהמדידה האחרונה שלנו, ואיננו מוקלד ידנית.
>
> **מדד הסל החודשי**
>
> מדי חודש אנחנו מתמחרים סל קבוע בכל רשת, במדד הסל החודשי. הסל מפורסם וגרסתו קבועה, כדי שאפשר יהיה להשוות בין חודשים. מחיר רשת הוא החציוני בין סניפיה (חנויות פיזיות בלבד). מבצעים כלולים, חוץ ממבצעי מועדון, ומחירי מוצרים במשקל הם הערכה. הפרשי מחירים בין סניפים של אותה רשת אינם מופיעים במדד. מדד שלא עבר בדיקה לפני פרסום לא מתפרסם.

### C8. The public matching-quality metric

File: `apps/web/src/features/seo/QualityMetric.tsx`

The page writes, from `apps/web/public/seo/quality.json`, a headline such as "⟨N⟩% מההחלפות נכונות בסט
ההערכה". The committed snapshot says: any-brand precision 1.0 on a sample of 546 at that level, **synthetic: true**,
measured 2026-10-07 on 857 gold items (**verified**: `apps/web/public/seo/quality.json`). So the page
currently shows 100% with the qualifier below.

> איכות ההתאמה טרם נמדדה.
>
> ⟨percentDown(headline)⟩ מההחלפות נכונות בסט ההערכה
>
> (סינתטי עד שיהיו נתונים אמיתיים)
>
> **הגדרה.** מתוך ההחלפות שהמערכת מציגה למשתמש לפי רמת גמישות, אחוז ההחלפות שסט ההערכה מסמן כנכונות לאותה רמה. החלפות שנשלחות לבדיקה אנושית אינן נספרות כמוצגות. אחוזים מעוגלים כלפי מטה.
>
> הסט נוצר מתבניות ולא מפריטים אמיתיים מהרשתות, ולכן המספר מראה שמנגנון הבדיקה פועל ושהכללים הקשיחים נשמרים, ואינו הערכה של הדיוק על מוצרים אמיתיים.
>
> זה יעד ולא תוצאה: הוא יימדד על נתונים אמיתיים ועל דחיות של משתמשים בבטא.

### C9. The monthly basket index

File: `apps/web/src/app/(seo)/basket-index/page.tsx`

Shown at `/basket-index`: a fixed basket priced at every chain each month, published only if it passes
checks. It compares chains, not the user's own saving.

> **מדד הסל החודשי**
>
> כל חודש אנחנו מתמחרים סל קבוע של ⟨index.basket.item_count⟩ מוצרי יסוד בכל רשת. הסל לא משתנה בתוך גרסה, כדי שאפשר יהיה להשוות בין חודשים. המדד מראה כמה הסל עולה בכל רשת ומה ההפרש מהזולה, ואינו חיסכון: החיסכון שלך נמדד מול החנות שלך, ברשימה שלך.
>
> **הסל הקבוע**
>
> רשימת המוצרים והכמויות (גרסה ⟨index.basket.version⟩)
>
> הרכב הסל והכמויות נבחרו בשיקול דעת ואינם סל צריכה שנמדד הערכה.
>
> **איך המדד מחושב**
>
> המחיר של רשת לכל מוצר הוא החציוני בין סניפיה, חנויות פיזיות בלבד, ליחידת מידה.
>
> מבצעים כלולים, חוץ ממבצעי מועדון. מחירי מוצרים במשקל הם הערכה.
>
> רשת שחסר לה מחיר למוצר בסל לא מדורגת, והחסרים מפורטים.
>
> לפני פרסום נבדקים פריטים חסרים, שינויים חריגים מהחודש הקודם ועדכניות המחירים. מדד שנכשל בבדיקה לא מתפרסם.
>
> הפרשי מחירים בין סניפים של אותה רשת אינם מופיעים במדד.
>
> המתודולוגיה המלאה

### C10. A product page (SEO)

File: `apps/web/src/app/(seo)/p/[slug]/page.tsx`

> מחיר ⟨unit⟩ של ⟨product.name_he⟩ בכל רשת, לפי קבצי השקיפות של הרשתות.
>
> מחיר חציוני: החציון בין סניפי הרשת. מבצעים כלולים, חוץ ממבצעי מועדון.
>
> ברמת "כל מותג" אנחנו משווים רק מוצרים שהמאפיינים הבאים בהם זהים. מותג וגודל אריזה יכולים להשתנות, והמחיר מושווה ליחידת מידה.

File: `apps/web/src/features/seo/components.tsx`

> עדיין לא נטענו מחירים למוצר הזה. כשקבצי השקיפות של הרשתות ייטענו, המחירים יופיעו כאן עם תאריך העדכון.
>
> רק המוצר עצמו, לפי ברקוד.
>
> אותו מוצר מכל מותג: המאפיינים החשובים נשארים זהים.
>
> תחליף קרוב: מאפיינים משניים, כמו גודל אריזה, יכולים להשתנות.

### C11. Where chain names and data appear

The app shows the chains' own names (for example in "לעומת ⟨homeName⟩, הסופר שלך" and in price tables)
and, on the methodology page, says the data comes only from the transparency files. There is no
statement of non-affiliation with the chains anywhere in the app (**verified** by search of
`apps/web/src`). **To confirm** whether one is needed (O4).

### C12. Neutrality statements

These are repeated in P1, P2 and C7: no sale of user data, no sponsored ranking, no third-party ad or
tracking tools. `docs/decisions.md` D12 leaves room for later "clearly labeled referral partnerships
with online stores", "labeled brand offers separate from ranking" and "anonymized aggregate market
reports (not to chains)"; the methodology page already says future affiliate links "יסומנו בבירור".

## 5. Texts that do not exist on this branch

| Text | Status | Where it would come from |
|---|---|---|
| Image or receipt consent (photo of a list or a receipt) | **Not present.** The API has the contract only: `POST /parse-image` answers 501, and its docstring states the intended rule, "the image is processed in memory and never stored; the raw OCR text is not stored either (D11)". No screen asks for the image yet. | The finish-round photo workstream (issues #61 and #68). When it lands, add its consent text here before it ships. |
| A beta join page or invitation text | **Not present.** The only beta text is the consent sheet in P4. Recruitment (screening form, invite codes, thank-you) is described in `docs/beta-plan.md` section 2 and happens outside the app. | The maintainer, at recruitment time. |
| Terms of use | **Not present** (no page, no link). | To confirm whether needed (Q37). |
| Cookie or local-storage notice | **Not present.** The app sets no cookie today (see the note at the start of section 2); it uses `localStorage` for lists, preferences and the beta-consent answer. | To confirm whether needed (Q18). |
| Data-subject request channel (a contact for access, correction, deletion requests) | **Not present.** Deletion and export are self-service in the profile; the accessibility contact is also unset. | To confirm (Q6, Q7). |

## 6. Inconsistencies found while collecting

Facts about the texts, not legal views. Each is something the owner may want fixed before the lawyer
reads, or may want the lawyer to rule on.

1. **The policy says account deletion is "coming soon", the profile does it.** P1 ends with "מחיקה מלאה
   של החשבון עצמו (כתובת האימייל) תתווסף בקרוב." while P2 and `DELETE /me`
   (`services/api/smartcart_api/routes/me_delete.py`, issue #90) delete the account and the e-mail
   address now. On hosted Supabase the delete needs the Admin API settings; without them the account row
   can remain and the profile says so (the "החשבון המאוחסן" message in P2).
2. **The policy lists what is stored but not everything the app stores or sends.** Not in P1: the
   closed-beta usage events (P4 and P13 mention them), price alerts and their push subscription
   (P10), the monthly budget entries (date, store, total, item count; P12), shared lists and their
   members (P6), the spoken list sent through the browser's speech service (P7), a recipe link sent to
   our server (P9), the savings history (P2 exports it) and the voice or camera permissions. It does
   disclose the OpenStreetMap tile requests.
3. **"No third-party tools" and the sub-processors.** P1, P2 and C7 say there are no third-party
   advertising or tracking tools. The app does use third-party services that see data: Supabase (hosting
   and sign-in), the browser vendor's speech and push services, and OpenStreetMap tiles (disclosed). It
   names Supabase and OpenStreetMap, not the speech and push services (the voice sheet, P7, does name
   the browser's speech service).
4. **The anonymous remainder after deletion.** After "delete my data", `events` and `gap_reports` rows
   keep existing with the user id removed (**verified** in `me_delete.py`); events from a signed-out
   browser carry only a random session id. P2 says "מחקי את הנתונים שלי" and P4 says "ויימחק או יהפוך
   לסטטיסטיקה אנונימית" for events, but P1 does not describe either.
5. **Two retention statements, one of them a proposal.** P1 gives retention for the shopping list (12
   hours) and says other preferences stay until deleted. P4 gives "עד שישה חודשים אחרי סוף הבטא" for
   events; `docs/beta-plan.md` calls it a proposal and the sheet's source comment says it is unreviewed.
6. **The consent wording changed shape.** `docs/beta-plan.md` proposes a text with an unchecked box;
   the app shows a sheet with "אני מסכימה" and "לא, תודה" (P4). The wording is close but not identical
   (first person singular in the proposal, second person in the sheet).
7. **Precision of the location.** P1, P2 and P3 say "רמת שכונה" and "כ-100 מטר". The code rounds to 3
   decimals, which is about 110 m in latitude and less in longitude (**estimate**). Whether that is a
   neighborhood is Q4.
8. **Public accuracy number from synthetic data.** C8 shows "100%" for the any-brand level, qualified as
   synthetic. The precision target of 98% is labeled a target. Whether the qualifier is enough is Q30.

## 7. Questions for the lawyer

Each question is meant to be answerable with a yes, a no or a named change. Where the research does not
cover the point, the question says **to confirm**.

### Privacy (O1; texts P1 to P14)

1. **Applicability.** Which provisions of the Privacy Protection Law and amendment 13 apply to a
   consumer web app of this kind (accounts by e-mail, a stored home location, shopping lists,
   preferences, a monthly spend record, closed-beta usage events)? Is any registration or notification
   to the Privacy Protection Authority required, and does it depend on the number of users?
   **To confirm.**
2. **Sensitive data.** Are kosher level, dietary needs and allergens (stored as preferences, P1) "special
   category" data? Is a stored home location with an account id "sensitive" as the research says
   (**verified** as a research statement), and does the 3-decimal rounding change that?
3. **Role holders.** Is a privacy officer or any named role required for us? **To confirm.**
4. **Location precision.** Is a coordinate rounded to 3 decimals (about 100 m), stored with an account
   id, "neighborhood level" in the legal sense, or should we store city or a coarser grid only? If
   coarser, what rounding is acceptable?
5. **Consent form.** Does P3 (explanation, then a separate tap on "אישור שימוש במיקום המכשיר", with a
   manual alternative) satisfy "explicit consent"? Do we need to keep a record of the consent (time,
   text version)? Is the beta sheet in P4, with two buttons and a stored yes or no, enough, or is an
   unchecked checkbox, as `docs/beta-plan.md` proposed, required?
6. **Notice.** Does P1 contain what a notice at collection must (who we are, a contact, purposes,
   whether providing data is mandatory, recipients and processors, rights, retention per category)?
   List what is missing. Is it a problem that inconsistencies 1 to 3 in section 6 exist?
7. **Data subject rights.** Are self-service export (a JSON of the profile and savings history) and
   self-service deletion enough for access, correction and deletion rights, or must there also be a
   channel and a response time (an e-mail address and a promise to answer within N days)?
8. **Deletion semantics.** After deletion, event and gap-report rows remain without a user id. Is that
   anonymization acceptable, and is "מחקי את הנתונים שלי" an accurate label for it? Must rows
   keyed to a random browser session id be deletable on request, and by whom?
9. **Retention.** Are the stated retention periods (store-mode list 12 hours; preferences until the
   user deletes; beta events "up to six months after the end of the beta") acceptable, and should
   the policy give a period for each category, including saved lists, alerts and spend entries?
10. **Hosting and transfers.** The database is hosted by Supabase in a European region (Frankfurt is
    the working choice, an **estimate**), voice dictation goes to the browser vendor's speech service,
    push goes through the browser vendor's push service, map tiles come from OpenStreetMap. Do any of
    these need disclosure or a transfer mechanism beyond what P1 and P7 say? **To confirm.**
11. **Security duties.** Do we need a written security policy or a database definition document? The
    code uses row-level security and does not store exact coordinates; is anything else required?
    **To confirm.**
12. **Third-party statement.** Is "אין בשירות כלי פרסום או מעקב של צד שלישי" accurate, given Supabase,
    the speech and push services and OpenStreetMap? Should it be reworded?
13. **E-mail statement.** P5 says the address is not shared "עם אף גורם חיצוני". The code sends the
    one-time code through Supabase Auth and whatever mail provider it is configured with. Is the
    statement accurate and should it name the processor?
14. **Sale and aggregates.** P1 says "לא מוכרים ולא מעבירים מידע על משתמשים לצד שלישי". D12 allows
    later "anonymized aggregate market reports (not to chains)". Does the current wording rule that
    out, and should it be narrowed to personal data?
15. **Beta consent content.** Is the list of what is and is not stored in P4 precise enough ("מזהה
    אקראי של הדפדפן" is a persistent identifier), and is "יימחק או יהפוך לסטטיסטיקה אנונימית" a
    sufficient description of what happens at the end of the beta?
16. **Withdrawal.** The profile switch (P4) stops sending at once. Must previously collected events
    be deleted on withdrawal, or is deletion on request enough?
17. **Minors.** The beta is for adults only (`docs/beta-plan.md`); the app asks for no age. Is an age
    gate or a statement needed? **To confirm.**
18. **Browser storage notice.** We use `localStorage`, and a first-party language cookie once a language
    switch exists. Is a notice or consent required for that? **To confirm.**
19. **Notifications.** Are price-alert push notifications and any future e-mail alerts "service
    messages", or do they raise direct-marketing rules (consent, opt-out)? Not in the research.
    **To confirm.**
20. **Shared lists.** A person who opens an invitation link signs in with an e-mail and sees the list
    owner's list. Are there duties toward the invited person or the owner beyond P6?
21. **Receipts and photos (future).** Before the photo feature ships: what consent text, retention
    ("processed in memory and never stored") and notice does it need? Is on-device processing, which
    the research prefers, required?

### Accessibility (O2; texts A1 to A3)

22. **Applicability.** Does standard 5568 and the accessibility regulations apply to this app and to a
    company of our size, from when, and are there phased or exempt categories? The research says only
    that the standard "applies to apps and sites" (**verified** as a research statement).
23. **Statement content.** What must the statement contain (date, level of conformance, known
    limitations, a named coordinator and contact, a way to request an accessible alternative, a
    response time)? A1 aims at 5568, says what was and was not checked, and tells the user how to report;
    the contact is unset. What must change before launch?
24. **Conformance claim.** A1 and A3 deliberately do not claim conformance. Is it acceptable to launch
    with that wording, and does a conformance claim need an external audit or a certified auditor?
    A1 says a legal check "על ידי גורם מוסמך" has not been done.
25. **Scope and version.** The research ties 5568 to WCAG 2.0 AA; we also test some WCAG 2.1 items
    (reflow). Is the installed PWA treated like a website? **To confirm.**
26. **Languages.** The statement is in Hebrew only. An Arabic interface is planned (phase 3, not built
    for launch). Must the statement, or the app, be available in Arabic? **To confirm.**
27. **Known gaps at launch.** Open items are listed in `docs/a11y-report.md` (the screen reader pass,
    text-only scaling, reduced motion, forced colors). Is launch with these listed in the statement
    acceptable?

### Price presentation and trust (O3, O4; texts C1 to C12)

28. **Staleness.** C1 and C2 show the update time and "המחיר הקובע הוא בקופה" but do not warn when a
    price is old. Is that enough to avoid a misleading presentation? Should there be a warning above
    a threshold (for example 24 or 48 hours), or should old prices not be shown?
29. **Savings claims.** C3 shows "חוסך ⟨₪⟩" net of an estimated travel cost, against the user's own
    store. Does a saving claim of this kind need a statement of the assumptions next to it? Is it a
    comparative claim about named chains, and does that carry extra requirements? **To confirm.**
30. **Public accuracy figure.** C8 publishes "100% מההחלפות נכונות בסט ההערכה (סינתטי עד שיהיו נתונים
    אמיתיים)" from a synthetic set. Is a number from synthetic data acceptable on a public page with
    this qualifier, or should it be hidden until it is measured on real labeled pairs? The 98% target
    is labeled a target.
31. **Substitution labeling.** Are the label "תחליף", the reason line, the "לא מאומת" tags and the undo
    in C4 sufficient to avoid misleading about a substituted product, particularly at the default
    "any brand" level? Is a brand swap, as opposed to a product swap, a substitution that must be
    labeled?
32. **Allergens and dietary claims.** The app lets the user set allergens and kosher level, marks
    matching on them "לא מאומת", and does not use them as matching rules. Does that need an explicit
    disclaimer next to a substitute (for example "בדקי את האריזה"), and what is the exposure if a
    substitute contains an allergen the chain's file did not show?
33. **Promo confidence.** Is showing "ביטחון ⟨96⟩%" for a parsed promo (C5) understandable and not
    itself misleading? What if the parsing is wrong?
34. **Structured data.** C6 publishes, for search engines, price "Offer" objects with the chain as
    seller, from medians across branches. Is that a misleading representation, given that we do not
    sell and the shelf price at a given branch may differ? Should it be removed or reworded?
35. **Use of chain names and data.** Is nominative use of the chains' names (C11) allowed without a
    non-affiliation statement? Do the portals' terms or the law require attribution or restrict
    republishing prices? The research says use of the files is permitted and scraping the chains'
    online stores is not (**verified** as a research statement).
36. **Neutrality wording.** C12 says there is no sponsored ranking and that future affiliate links will
    be labeled. Is the current wording safe, and what must the labeling of a future partnership look
    like?
37. **Terms of use.** There are no terms of use (section 5). Are they required before the closed beta
    or before launch, with what limitation-of-liability and dispute clauses? Not in the research.
    **To confirm.**
38. **Beta mechanics.** Participants are recruited by invitation code and receive a small thank-you not
    tied to usage (`docs/beta-plan.md` section 2). Does that raise any rule on inducements or on
    recruiting? **To confirm.**

## 8. What to send and what to ask back

Send: this file; the live pages (`/privacy`, `/accessibility`, `/methodology`, `/basket-index`, one
product page) from the deployed or demo build (`docs/fullstack.md`), because the lawyer will want to
see them rendered; `docs/beta-plan.md` sections 2 and 3; `docs/a11y-report.md`; the research section 2.4
(Hebrew) and `docs/product-and-market.md` "Legal rules we follow".

Ask back, so the owner can act on it without another round:

- An answer per numbered question, with "change X to Y" wording where a text must change.
- A list of texts the app must have and does not (section 5), with the wording or a model.
- For each of P1, P4 and A1, either approved as is, or the exact approved wording, and the date, so
  the pages can drop their "not legally reviewed" sentences (the last line of the privacy page, the
  `ConsentSheet` comment and the statement's "מה עדיין לא נבדק" list).
- What the lawyer needs before launch versus before the closed beta.

Engineering follow-ups that do not need the lawyer, found while collecting (section 6, items 1 to 3):
bring the privacy page in line with account deletion and with the features it does not list. They are
page edits, in files this packet does not own.

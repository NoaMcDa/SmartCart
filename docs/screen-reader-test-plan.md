# Screen-reader test plan (issue #26)

The one accessibility item that only a person can do: a pass over the core flows with VoiceOver and
TalkBack, in Hebrew, right to left, on real phones. `docs/a11y-report.md` lists it as "not done".
This plan makes it a checklist a person can finish in **about two hours** (**estimate**: setup 20
minutes, 45 minutes per phone for the eight flows, 10 minutes to write up; nobody has timed it).
NVDA with Firefox is an optional third pass, about 30 minutes more.

What is already covered, so it is not repeated here: axe on every route in both themes, contrast,
200% zoom at 195 px, a keyboard-only run of the core flow (`docs/a11y-report.md`). What this pass adds
is what no tool can say: what is actually spoken, in which order, in Hebrew, with prices and numbers
inside Hebrew text.

Labels follow `docs/README.md`: **derived** means worked out from the code and the mock data (the
tester confirms it on the screen), **estimate** is a judgement.

## 1. What you need

### 1.1 Devices and readers

| ID | Device | Browser | Reader | Required | Notes |
|---|---|---|---|---|---|
| VO | iPhone, a recent iOS | Safari (also the installed app, if time allows) | VoiceOver | **Yes** | Add the Hebrew voice before starting (Settings, Accessibility, VoiceOver, Speech, Voice). Note the iOS and Safari versions. |
| TB | Android phone, a recent Android | Chrome (also the installed app, if time allows) | TalkBack | **Yes** | Hebrew language and the Google speech voice in Hebrew installed. Note the Android, Chrome and TalkBack versions. |
| NV | Windows laptop | Firefox | NVDA | Optional | Hebrew speech synthesizer installed. Use browse mode; switch to focus mode only where the step says so. |

Settings to write down in the results: reader language (Hebrew), speech rate, verbosity, whether
"Speak hints" / "usage hints" are on. Defaults first; repeat a failing step with hints off before
filing it.

### 1.2 The app to test

Use the mock data, so the names and numbers below match. On a computer on the same network as the phone:

```bash
cd apps/web
npm ci
NEXT_PUBLIC_API_MOCK=1 npm run build
npm run start -- -H 0.0.0.0        # then open http://<the computer's address>:3000 on the phone
```

(`npm run dev:mock -- -H 0.0.0.0` also works but is slower and prints development overlays that a
screen reader will read.) The mock list is `docs/web.md` "API layer and mocks". Against the full-stack
demo (`docs/fullstack.md`) or a deployed build the names and amounts differ; compare the pattern, not the
numbers.

Every name, price and count below is **derived** from the mock fixtures (`apps/web/src/mocks/fixtures.ts`) and
the code that renders them; confirm each on the screen, and report a difference as a note, not a fail,
unless the text itself is wrong or missing.

The time of every price in the mock is 06:40 on 2026-10-07 (Israel time). The app shows it relative to
today, so on 2026-10-08 it says `אתמול 06:40`, later `לפני ⟨N⟩ ימים`, after a week a date.

### 1.3 The list to use

Type or paste this into the list field (flow 2):

```
חלב, קוטג, משקה סויה, רסק עגבניות, שמן זית, פסטה, עגבניות, סלמון, ביצים
```

With the mock this gives nine rows: milk, cottage cheese, soy drink, tomato paste, olive oil (asks for
confirmation), pasta, tomatoes and salmon (weighed), eggs. The home store is the mock's default,
`שופרסל דיל · מודיעין`. **Do not choose a chain in onboarding before flow 4** (or reset the site data,
see flow 1): choosing one replaces that default.

### 1.4 Reading the tables

- **Do** gives the gesture for VoiceOver and for TalkBack. "Next" and "previous" mean the reader's
  move to the next or previous element in reading order. On a right-to-left page, note which swipe
  direction moved forward on your device; that is worth a line in the results (it differs between
  readers and versions; **to confirm on device**).
- **The app should say** is the text the app provides: the accessible name, the visible text, and the
  state words it sets (selected, expanded, checked). It is quoted in Hebrew from the code. The reader
  adds its own words for the role ("לחצן", "כותרת", "תיבת סימון", "מתג", "קישור"...) in its own
  language and order; you do not have to match those, only to notice if the role is missing or wrong.
  A `⟨...⟩` stands for a value that varies (a name, a number); the number must be spoken as a number.
- **P / F / N** columns: P pass, F fail, N not applicable or not reachable. Add a note number to a
  fail and file it as in section 6. "Record" in a step means write down what was heard; it is not a
  pass or fail on its own (these are the open questions of `docs/a11y-report.md`).
- A step passes if the text is spoken, correct, in a sensible order, without needing to look at the
  screen. Prices and numbers are Hebrew-readable (for example `389` as a number, not as digits one
  by one), and an English fragment such as `SmartCart` may be spoken in English.

### 1.5 Gestures you will use

| | VoiceOver (iPhone) | TalkBack (Android) |
|---|---|---|
| Next / previous element | swipe in the reading direction / the other way | the same |
| Activate | double-tap | double-tap |
| Jump by headings, links, form controls | rotor (turn two fingers like a dial), then swipe up or down | reading controls: swipe up or down with one finger (three-finger tap on some versions) |
| Read from the top | two-finger swipe up | swipe up then right, or the "read from top" shortcut |
| Scroll | three-finger swipe | two-finger swipe |
| Close a dialog | the close button in the dialog; also try the two-finger scrub (Z) | the close button; also try the back gesture |
| Touch exploration | drag one finger over the screen | the same |

## 2. Flow 0, before the flows: the shell (5 minutes)

Open `/`. Every flow starts from these elements.

| # | Do | The app should say | VO | TB | NV |
|---|---|---|---|---|---|
| 0.1 | Load the page. Read the page title (VoiceOver: in the status bar or rotor; TalkBack: when the page loads) | `הקנייה השבועית · SmartCart`. The language is Hebrew (`lang="he"`): the Hebrew voice is used, not an English voice reading Hebrew | | | |
| 0.2 | Go to the first element | `דילוג לתוכן` (skip link). Activate it: focus moves to the main content | | | |
| 0.3 | Next | The home link: `SmartCart, לדף הבית` | | | |
| 0.4 | Next (on a phone the top bar's section links and profile link are hidden, so they must not be spoken) | The theme switch: `מצב כהה`, with its state (off or on, `aria-checked`). Activate: the state changes and the page changes theme | | | |
| 0.5 | Find the bottom bar | Landmark `ניווט ראשי`. Five links in this reading order: `רשימות` (the current page), `השוואה`, `סריקת ברקוד` (the raised centre button; its visible word `סריקה` is hidden from the reader), `התראות`, `פרופיל`. The current page is marked as the current page | | | |
| 0.6 | Next after the bar | Record: is the order of the tabs the same as on the screen, right to left? | | | |
| 0.7 | Headings (rotor) | One level-one heading: `הקנייה השבועית` | | | |

If the beta consent sheet (title `עוזרות לנו לבדוק את ההחלפות?`, buttons `אני מסכימה` and `לא, תודה`)
appears, it is a dialog: check that its title is spoken on opening and that both buttons are
reachable, then answer `לא, תודה` and continue. It appears only in a build with beta events on.

## 3. Flow 1: onboarding (10 minutes)

Open `/onboarding` (or the first-run link). Three steps, each skippable.

| # | Do | The app should say | VO | TB | NV |
|---|---|---|---|---|---|
| 1.1 | Open the page | Title `ברוכים הבאים · SmartCart`; heading level one `ברוכים הבאים`; the lead `שלוש שאלות קצרות כדי שההשוואה הראשונה תהיה שלך. אפשר לדלג על כל שלב ולחזור אליו בפרופיל.` | | | |
| 1.2 | Find the progress | Landmark `התקדמות`; a list of three items; the current one is marked as the current step and is spoken as `שלב 1 מתוך 3: איפה את קונה?` (hidden text). Then the visible `שלב 1 מתוך 3`: the numbers are spoken as numbers, in the right order | | | |
| 1.3 | Next | Heading level two `איפה את קונה?` | | | |
| 1.4 | Next | A complementary region named `למה אנחנו שואלים` containing `למה אנחנו שואלים: כדי להציג סניפים קרובים אליך ולחשב כמה עולה להגיע אליהם.` and the rest of the sentence (rounding to a neighborhood, after you approve, delete any time), then the link `מדיניות הפרטיות` | | | |
| 1.5 | Next | `המיקום שלי`, then `עוד לא הגדרת מיקום.` | | | |
| 1.6 | Next | Button `אישור שימוש במיקום המכשיר`; button `להזין עיר ושכונה במקום`. **Do not** activate the first yet | | | |
| 1.7 | Activate `להזין עיר ושכונה במקום` | The manual form appears. Record whether the appearance is announced (expected: it is not announced; focus stays on the button). Next: field `עיר` (a suggestion list is attached), field `שכונה (לא חובה)`, button `שמירת העיר` | | | |
| 1.8 | Type `חיפה` in `עיר`; open suggestions | The suggestions are read (browser behavior). Record how | | | |
| 1.9 | Clear the field, type `עיר לא קיימת`, activate `שמירת העיר` | An error is announced immediately: `לא מצאנו את העיר ברשימה. בחרי עיר מההצעות.` (alert), and the field is marked invalid | | | |
| 1.10 | Type `מודיעין`, choose `מודיעין-מכבים-רעות` from the list, activate `שמירת העיר` | Record what is spoken. The saved place appears as `מודיעין-מכבים-רעות` (a tag) with the button `הסרת המיקום` | | | |
| 1.11 | Radius slider | Name `רדיוס חיפוש`; value spoken as `5 קילומטרים` (not "5"); the value changes by swipe up or down and is spoken each time | | | |
| 1.12 | Activate `אישור שימוש במיקום המכשיר`; refuse the browser permission | The button changes to `מבקשת מיקום…` while waiting; after refusing, a status is announced: `לא קיבלנו הרשאת מיקום, וזה בסדר. אפשר להזין עיר ושכונה ולהמשיך.` The manual fields stay available | | | |
| 1.13 | Activate `המשך` | Step 2: record whether the change of step is announced. Heading level two `הסופר שלי והמועדונים`; the progress now says `שלב 2 מתוך 3` | | | |
| 1.14 | The chain buttons | `הסופר שלי: שופרסל` and nine more chains, each a toggle button with its pressed state; activate one: state becomes pressed. A second group: `מועדון שופרסל`... as toggles. After a selection the text `בלי חנות בסיס לא נוכל להראות חיסכון נטו...` disappears and `ניקוי הבחירה` appears | | | |
| 1.15 | `המשך` | Step 3, heading `איך את עושה קניות?`. Group `אמצעי הגעה` with three options `רכב`, `הליכה או תחבורה`, `משלוח` as radio buttons (one selected); the slider `כמה שווה לך עצירה נוספת?` spoken as `⟨N⟩ שקלים` | | | |
| 1.16 | `סיום` | You arrive at the list page. Record what is spoken on arrival (new page title, focus) | | | |
| 1.17 | `דילוג על השלב` / `חזרה` | Each is reachable and named as written; the skip does not trap you | | | |

**Reset before flow 2.** Choosing a chain changed the home store the mock results rely on. Clear the
site's data (iPhone: Settings, Safari, Advanced, Website Data, remove the site; Android: Chrome, site
settings, clear and reset), reload, and do not choose a chain again until flow 4 is finished.

## 4. Flow 2: paste a list (10 minutes)

Open `/`.

| # | Do | The app should say | VO | TB | NV |
|---|---|---|---|---|---|
| 2.1 | Move to the list area | Region `הרשימה` | | | |
| 2.2 | Next | The field, named `הוסיפי פריטים לרשימה` (the placeholder is not its name). Record whether the placeholder `חלב, 2 רסק עגבניות, סלמון…` is read as a hint | | | |
| 2.3 | Next | `הכתבה קולית` (offered only where the browser supports it; it opens a dialog), `הדבקת רשימה`, `הוסיפי` (disabled until there is text: spoken as unavailable/dimmed). If dictation is not supported, a line is read instead: `הכתבה קולית לא זמינה בדפדפן הזה. אפשר להקליד או להדביק את הרשימה.` | | | |
| 2.4 | Paste the list from section 1.3 into the field (long-press, Paste) and activate `הוסיפי` | While parsing, a polite status: `מזהה פריטים…`. Then the rows appear. **Record** whether anything announces that nine rows were added (expected: nothing, except the estimate region below; this is the open question in `a11y-report.md`) | | | |
| 2.5 | Headings (rotor) | Level two headings, one per department, each followed by a count: for example `מוצרי חלב` `4 פריטים`, `מזווה` `3 פריטים`, `ירקות ופירות` `1 פריט`, `דגים ובשר` `1 פריט`. The numbers are spoken as numbers. Each department is also a region with the same name | | | |
| 2.6 | Read one row, milk | Name `חלב טרי 3%, 1 ליטר`; button `רמת גמישות: כל מותג`; the quantity group `כמות: חלב טרי 3%, 1 ליטר` with `הפחיתי כמות של חלב טרי 3%, 1 ליטר` (unavailable at 1), `כמות 1`, `הוסיפי כמות של חלב טרי 3%, 1 ליטר`; and `הסרת חלב טרי 3%, 1 ליטר` | | | |
| 2.7 | Activate `הוסיפי כמות של ...` | The new value is announced by itself: `כמות 2` (the value is a polite live region). Record if it is missed | | | |
| 2.8 | Read the tomatoes row | A tag with the words `מחיר משוער · שקיל`, so a weighed product is marked as an estimate in words; the quantity is `כמות 1` | | | |
| 2.9 | Read the olive-oil row | A group `אישור הפריט שמן זית` with `כתבת "שמן זית". התכוונת לשמן זית כתית מעולה, 750 מ"ל?`, the buttons `כן, שמן זית כתית מעולה, 750 מ"ל` and `בחרי אחר` | | | |
| 2.10 | Activate `בחרי אחר` | The button now says it is expanded; a list `אפשרויות אחרות` with three choices. Choose one: the group disappears. Record where focus goes | | | |
| 2.11 | Type `ספרינגרול` and `הוסיפי` | A section `לא זוהו` with `לא ייכללו בהשוואה`; the row `לא מצאנו את "ספרינגרול"`, `נסי לכתוב אחרת או לדווח לנו על פער`, buttons `עריכת ספרינגרול` and `הסרת ספרינגרול` | | | |
| 2.12 | Find the estimate bar | Region `הערכת סל` (a polite live region): `הערכת סל ב-⟨N⟩ סניפים עד ⟨R⟩ ק"מ` and a price range such as `₪ 402–₪ 446`: the range is spoken as two prices with a dash, in the right order, not as a negative number. Record how | | | |
| 2.13 | Next | The link `השווי` | | | |

## 5. Flow 3: the flexibility sheet (10 minutes)

On the milk row, activate `רמת גמישות: כל מותג`.

| # | Do | The app should say | VO | TB | NV |
|---|---|---|---|---|---|
| 3.1 | Open it | A dialog named `חלב טרי 3%, 1 ליטר`; focus moves into it (first to the close button `סגירה`). Record what is spoken on opening: the title, the eyebrow `רמת גמישות לפריט`, the role "dialog" | | | |
| 3.2 | Try to leave the dialog by swiping forward and back through everything | You must **not** reach the page behind (the dialog is modal). Count the elements; note if any element of the list page is spoken | | | |
| 3.3 | Reach the options | A group `רמת גמישות` with three radio buttons. Each one's name is its label and explanation: `מוצר מדויק` `רק הברקוד שבחרת.` `לדוגמה: תנובה, 3%, קרטון 1 ליטר.`; `כל מותג` `אותו מוצר מכל יצרן.` `תנובה, טרה, יטבתה, מותג פרטי. נשמר: 3% שומן, טרי, 1 ליטר.`; `תחליף קרוב` `גם אחוז שומן, אריזה או גודל אחרים. תמיד מסומן כתחליף.` `לדוגמה: 1% או 2%, שקית במקום קרטון.` `כל מותג` is selected. **Record** whether the explanation is read twice (once in the name and once as a description) | | | |
| 3.4 | Select `תחליף קרוב` | The selection is spoken. A group `אפשר לוותר על:` appears. Record whether the appearance is announced | | | |
| 3.5 | Reach the group | Three checkboxes: `גודל אריזה אחר`, `קרטון או שקית`, `אחוז שומן אחר`, each with its checked state. Check one: the state changes | | | |
| 3.6 | Select `מוצר מדויק` | The group `אפשר לוותר על:` disappears. Record | | | |
| 3.7 | Reach the switch | `זכרי בחירה זו לכל סוגי החלב`, a switch with its state, and the description `חל על פריטים חדשים ועל הפריטים מהסוג הזה ברשימה. אפשר לשנות בפרופיל.` Activate: the state changes | | | |
| 3.8 | Buttons | `שמרי` and `ביטול`, in this order. Select `תחליף קרוב` again and activate `שמרי` | | | |
| 3.9 | After closing | Focus returns to the row's flexibility button, which now says `רמת גמישות: תחליף קרוב`. If focus is lost (the screen reader starts from the top), that is a fail | | | |
| 3.10 | Reopen and press `ביטול`, then reopen and press `סגירה` | Both close the dialog and return focus to the opener. Try the dialog's own dismiss gesture (VoiceOver two-finger scrub, TalkBack back) and record whether it closes | | | |

## 6. Flow 4: results (15 minutes)

On `/`, activate `השווי` (set the milk row back to `כל מותג` first for a clean state, or leave it).

| # | Do | The app should say | VO | TB | NV |
|---|---|---|---|---|---|
| 4.1 | Arrive | Title `איפה הכי זול השבוע? · SmartCart`; link `חזרה לרשימה`; heading level one `איפה הכי זול השבוע?`. **Record** what is spoken when the page opens and whether the arrival of the results is announced (the loading cards have the label `טוען תוצאות`; there is no live region for the arrival of the results, so silence is expected and is the open finding) | | | |
| 4.2 | Subline | `⟨N⟩ פריטים · עד ⟨R⟩ ק"מ ... · עודכן אתמול 06:40`: numbers as numbers; the time inside a time element | | | |
| 4.3 | The view toggle | A radio group `תצוגה` with `רשימה` (selected) and `מפה`. Do not activate `מפה` | | | |
| 4.4 | First plan card | Heading level two `רמי לוי · מודיעין`; the badge `מומלץ`; the distance `4.2 ק"מ`; `סך הסל` and the total `₪ 389`; `חוסך ₪ 57` and `לעומת שופרסל דיל · מודיעין, הסופר שלך`; the link `3 פריטים הוחלפו`; the button `1 פריט חסר` (collapsed); `2 מבצעים כלולים, 1 למועדון`; `מחירים עודכנו אתמול 06:40`. **Record** how `₪ 389` and `₪ 57` are spoken (currency word, number, order) | | | |
| 4.5 | Activate `1 פריט חסר` | It becomes expanded, and a list `פריטים חסרים` follows: `קוטג' 5%, 250 ג'` `לא נמכר בסניף, לא נספר בסך`. Record whether the expansion is announced | | | |
| 4.6 | Second card | Heading level two `רמי לוי + אושר עד`; the badges `פיצול ל-2 סופרים` and `+12 דק'`; `6 פריטים ברמי לוי · 3 פריטים באושר עד`; `₪ 371`; `חוסך ₪ 41 נטו`; the link `פירוט הפיצול בין הסופרים`; the breakdown `חיסכון בסל ₪ 75, פחות ₪ 9 נסיעה ו-₪ 25 שווי העצירה הנוספת.` | | | |
| 4.7 | Third card | The badge `מינימום מאמץ · הסופר שלך`; heading `שופרסל דיל · מודיעין`; `הבסיס שאליו משווים`; `₪ 446`. It must not say `חוסך` | | | |
| 4.8 | The smart cart (if shown) | A region labelled by its heading, starting `עגלה חכמה · רמי לוי`; buttons `החליפי ל⟨name⟩` and `לא עכשיו`. Activating a swap announces, politely, `הוחלף: ⟨name⟩ (חיסכון ₪ ⟨N⟩).` with the button `ביטול ההחלפה` | | | |
| 4.9 | The substitutions section | Heading level two `החלפות ברמי לוי`, `כל החלפה ניתנת לביטול`; each row: `ברשימה שלך`, the original name, a tag `תחליף`, the substitute name, buttons `למה חלב טרי 3% יטבתה, 1 ליטר?` (visible `למה?`) and `ביטול ההחלפה של חלב טרי 3% יטבתה, 1 ליטר` (visible `בטלי`). The meaning of "substitute" is carried by the word, not by colour | | | |
| 4.10 | The details | `פירוט הסל ברמי לוי`, collapsed. Expand: per store a level-three heading, then lines with the name as a link, the tag `תחליף · למה?` (a link named `תחליף: ⟨name⟩, למה?`), `× ⟨N⟩`, the price with its update time | | | |
| 4.11 | The footer | `המחיר הקובע הוא בקופה.` then `המחירים לפי קבצי שקיפות המחירים של הרשתות...`, a link `איך אנחנו משווים מחירים`, `מחירים עודכנו אתמול 06:40`, the button `דיווח על פער במחיר`. Activate it: a dialog opens; close it; focus returns to the button | | | |
| 4.12 | Headings (rotor) | A sensible outline: the level-one heading, then one level-two heading per card and section. Record anything missing or out of order | | | |

## 7. Flow 5: a substitution card, keep the original (10 minutes)

On the first card, activate `3 פריטים הוחלפו`.

| # | Do | The app should say | VO | TB | NV |
|---|---|---|---|---|---|
| 5.1 | Arrive | Title `פרטי החלפה · SmartCart`; heading level one `פרטי החלפה`; an article named by its heading: `החלפנו את חלב טרי 3% תנובה, 1 ליטר ב-חלב טרי 3% יטבתה, 1 ליטר`; before it `החלפה 1 מתוך 3 · רמי לוי` | | | |
| 5.2 | The original side | `ברשימה שלך`, the name, the price `₪ 6.90` with `עודכן אתמול 06:40`, the unit price `₪ 0.69 ל-100 מ"ל`, `בסופר שלך, שופרסל דיל · מודיעין` | | | |
| 5.3 | The substitute side | The tag `התחליף`, the name, `₪ 5.90`, `₪ 0.59 ל-100 מ"ל`, `רמי לוי · מודיעין` | | | |
| 5.4 | The saving | `חיסכון ₪ 1.00 × 2 יחידות` and `₪ 2.00` | | | |
| 5.5 | The reasons | Heading level three `למה זה תחליף מתאים`; a list `השוואת תכונות`: `אותו סוג מוצר`, `אותו גודל, 1 ליטר`, `אחוז שומן, 3%`, `יטבתה במקום תנובה`. Whether a tag is a match or a difference is carried by its words; record if it is not clear without sight. An unverified tag ends with `· לא מאומת` (see step 5.9) | | | |
| 5.6 | The source line and the disclaimer | `לפי שם המוצר בקובץ השקיפות · ביטחון 98% · מחיר עודכן אתמול 06:40`; `המחיר הקובע הוא בקופה.`; the link `איך אנחנו מחליטים מה תחליף מתאים` | | | |
| 5.7 | The actions | Three buttons: `בסדר, להחלפה הבאה`, `השאירי את המקורי`, `לא תחליף טוב` | | | |
| 5.8 | Activate `השאירי את המקורי` | You return to the results. A polite status is spoken: `השארנו את המוצר המקורי: חלב טרי 3% תנובה, 1 ליטר. הסל חושב מחדש לפי מוצר מדויק.` **If it is not spoken, that is a fail.** The cards now show new totals: record them. Focus: record where it is | | | |
| 5.9 | Go back to the results, open the second substitution (the soy drink: the card says `החלפה 2 מתוך 3`) | An unverified attribute is said as such in words: `חלבון 3.3 ג' ל-100 מ"ל · לא מאומת` | | | |
| 5.10 | `לא תחליף טוב` on another one | After a moment, a polite status: `תודה, הדיווח נשמר ונבדק. חזרנו למוצר המקורי: ⟨name⟩.` | | | |

## 8. Flow 6: the split, move an item by button (10 minutes)

Open the split card's link `פירוט הפיצול בין הסופרים` (a card is present only if the split is recommended or shown). If `/split` says there is no comparison to split, go back to `/compare` first.

| # | Do | The app should say | VO | TB | NV |
|---|---|---|---|---|---|
| 6.1 | Arrive | Title `פיצול סל · SmartCart`; heading level one `פיצול סל`; `רמי לוי ואושר עד` | | | |
| 6.2 | The summary (a polite live region) | `חיסכון נטו מול שופרסל` (the chain of the home store) and `₪ 41`; `סה״כ לקנייה` `₪ 371`; `זמן נוסף` `+12 דק'`; `מחירים` `עודכנו 06:40` | | | |
| 6.3 | The waterfall | A heading (`aria-labelledby`), then the steps as labelled amounts in a readable order: `מחיר בסיס בשופרסל`, then savings (`מעבר רשת`, `החלפת מותג`, `מבצעים`), then costs (`עלות נסיעה`, `שווי עצירה נוספת`). The drawn bars are hidden. Record whether you can tell the savings from the costs without sight | | | |
| 6.4 | The hint and the reset | `גררי פריט אל החנות השנייה, או השתמשי בכפתור "העברה" בכל שורה.`; the button `איפוס לפיצול המומלץ` (unavailable until something moved) | | | |
| 6.5 | The tabs | A tab list `חנויות בפיצול` with `רמי לוי · ₪ 334.40` (selected) and `אושר עד · ₪ 36.60`. Activate the second: its panel shows. Record whether the arrow keys or swipes move between tabs | | | |
| 6.6 | Back on the first store, read an item | `חלב טרי 3% יטבתה, 1 ליטר`, `2 ×`, `עודכן 06:40`, the tag `תחליף`, the price `₪ 11.80`, the button **`העברת חלב טרי 3% יטבתה, 1 ליטר לאושר עד`** (visible `העברה לאושר עד`) and `דיווח: חלב טרי 3% יטבתה, 1 ליטר`. The drag handle `⋮⋮` is **not** spoken | | | |
| 6.7 | Activate the move button | A polite announcement without looking: `חלב טרי 3% יטבתה, 1 ליטר הועבר לאושר עד. חיסכון נטו ₪41.40.` The item leaves the list and the subtotals change. **Record where focus is** after the item disappears (the button that was focused is gone). If the reader falls back to the top of the page, that is a finding | | | |
| 6.8 | A blocked move | On the salmon item, the move button is announced as unavailable with the description `לא נמצא באושר עד, לכן אי אפשר להעביר`. Activate it anyway: `לא ניתן להעביר את פילה סלמון נורבגי טרי: לא נמצא באושר עד` | | | |
| 6.9 | The reset | `איפוס לפיצול המומלץ`: the announcement `הפיצול המומלץ שוחזר.` and the totals return | | | |
| 6.10 | Start shopping | The button `התחילי קנייה ברמי לוי` | | | |

## 9. Flow 7: store mode (10 minutes)

Activate `התחילי קנייה ברמי לוי` (or open a store from the results).

| # | Do | The app should say | VO | TB | NV |
|---|---|---|---|---|---|
| 7.1 | Arrive | Title `מצב חנות · SmartCart`; heading level one `מצב חנות`; the store name `רמי לוי · מודיעין` | | | |
| 7.2 | The progress | `נאספו 0 מתוך 6`; `בעגלה ₪ 0 מתוך ₪ 334.40`; a progress bar named `התקדמות הקנייה` with the value `נאספו 0 מתוך 6` | | | |
| 7.3 | The checklist | Department headings (level two; unknown ones fall in `אחר`), then items as checkboxes. Each item's name is its whole text, for example `חלב טרי 3% יטבתה, 1 ליטר 2 × תחליף עודכן 06:40 ₪ 11.80`, and its checked state. Record whether the long name is bearable | | | |
| 7.4 | Check an item | The state becomes checked; a polite status `סומן: חלב טרי 3% יטבתה, 1 ליטר` with the button `ביטול`; the progress value becomes `נאספו 1 מתוך 6`. The item moves to the bottom of its group: record whether focus stays on it | | | |
| 7.5 | `ביטול` | The item is unchecked | | | |
| 7.6 | A report button beside an item | `דיווח: ⟨name⟩`. Activate, close, focus returns | | | |
| 7.7 | Turn the network off (airplane mode), keep the page open | A status: `אין חיבור. הרשימה נשמרה במכשיר והסימונים נשמרים.` Check one item: it still works. Turn the network on | | | |
| 7.8 | The footer text | `המחיר הקובע הוא בקופה. מחירים עודכנו 06:40.` | | | |
| 7.9 | `סיימתי לקנות` | A dialog named `סיכום הקנייה`; the store name before the title; a list of `נאספו` `1 מתוך 6`, `סכום הפריטים שנאספו`, `חיסכון נטו שנרשם`; `לא נאספו (5)` and the unchecked names; a switch `לרשום בתקציב החודשי` with its description (`יירשמו ₪ ... לפי המחירים שהוצגו ולא לפי קבלה. רק תאריך, חנות, סכום ומספר פריטים.`); the line `בסיום, הרשימה נמחקת מהמכשיר והחיסכון נרשם בפרופיל. המחיר הקובע הוא בקופה.`; buttons `חזרה לקנייה`, `סיום וניקוי` | | | |
| 7.10 | `חזרה לקנייה` | Focus returns to the finish button. Open it again | | | |
| 7.11 | `סיום וניקוי` | You return to the list. Record what is spoken | | | |

## 10. Flow 8: delete my data (10 minutes)

Open `פרופיל` from the bottom bar.

| # | Do | The app should say | VO | TB | NV |
|---|---|---|---|---|---|
| 8.1 | Arrive | Title `פרופיל · SmartCart`; heading level one `פרופיל`; the lead `כל מה שהאפליקציה יודעת עלייך, במקום אחד. שינוי כאן משפיע על ההשוואה הבאה.` | | | |
| 8.2 | Headings (rotor) | Level two headings in this order: `חשבון`, `החיסכון שלי`, the budget heading, `מיקום ורדיוס`, `רשתות ומועדונים`, `איך אני קונה`, `כשרות ותזונה`, `ברירות מחדל לגמישות`, `ערכת צבעים`, `פרטיות ונתונים` | | | |
| 8.3 | Go to `פרטיות ונתונים` | The statement `אנחנו לא מוכרים מידע על משתמשים, לא משתפים אותו עם מפרסמים ולא מציגים תוצאות ממומנות. המיקום נשמר רק ברמת שכונה ורק באישורך. אין בשירות כלי מעקב או פרסום של צד שלישי.` and the link `למדיניות הפרטיות המלאה` | | | |
| 8.4 | Next | The switch `שימוש במיקום` with its state and the description `המיקום נשמר מעוגל לשכונה (כ-100 מטר). כיבוי מוחק את המיקום השמור.` Turn it off and on | | | |
| 8.5 | Next | Buttons `ייצוא הנתונים שלי` and `מחקי את הנתונים שלי` (and, in a beta build, the switch `אירועי שימוש לבדיקת הבטא`) | | | |
| 8.6 | Activate `מחקי את הנתונים שלי` | A dialog named `למחוק את כל הנתונים שלי?` (with `אי אפשר לבטל` before it); the text `יימחקו מהמכשיר: המיקום, הרשת והמועדונים, העדפות הכשרות והתזונה, ברירות המחדל, תוצאת ההשוואה האחרונה, הקנייה הפעילה והחיסכון שנצבר.`; buttons `ביטול` and `כן, למחוק`. The destructive button must be named as such, not only coloured | | | |
| 8.7 | Activate `ביטול` | The dialog closes, focus returns to `מחקי את הנתונים שלי`, nothing is deleted | | | |
| 8.8 | Open it again, activate `כן, למחוק` | The sheet closes and a status is announced: `הנתונים נמחקו מהמכשיר.` If it is silent, that is a fail (the paragraph is a live status). Record where focus is | | | |
| 8.9 | Return to `/` | The list is empty: the heading `הרשימה ריקה` and the text `הדביקי רשימה או כתבי פריטים מופרדים בפסיק...` | | | |
| 8.10 | Signed in (only if the build has sign-in configured) | In the dialog an extra paragraph: `וגם מהחשבון: כל הרשימות השמורות, פרטי הפרופיל והחשבון עצמו, כולל כתובת האימייל. בסיום תתנתקי.` | | | |

## 11. If time remains

Short checks of the other places the audit lists. They are not part of the two-hour estimate.

| # | Where | What to check |
|---|---|---|
| X.1 | An SEO product page, `/p/⟨slug⟩`, and `/basket-index` | Tables are read with their captions and column and row headers; the price in a table cell is a number with its currency; the `details` blocks announce collapsed or expanded; the trust block (`אמינות ועדכון`) is a landmark |
| X.2 | `/accessibility` | The statement reads as headings and lists; the line `פרטי הקשר יפורסמו כאן לפני ההשקה.` is present (the contact is not set yet) |
| X.3 | Voice dictation sheet | On opening, the title and the privacy sentence are read; the status `מקשיבה… אמרי את הפריטים.` is a polite status; the live transcript is not read on every change (by design) |
| X.4 | The budget chart in the profile | A table with a caption carries every number; the drawn chart is hidden |
| X.5 | The map | Record how the map page is read; the list view is the accessible path |

## 12. Results

Fill one copy per device. A step that failed gets a number from the defect list in section 13.

| Field | Value |
|---|---|
| Tester | |
| Date | |
| Device, OS version | |
| Browser, version | |
| Reader, version | |
| Reader language, speech rate, hints on or off | |
| App build (commit and mock or demo) | |
| Time taken | |

| Flow | Steps | P | F | N | Defect numbers |
|---|---|---|---|---|---|
| 0 Shell | 7 | | | | |
| 1 Onboarding | 17 | | | | |
| 2 Paste a list | 13 | | | | |
| 3 Flexibility sheet | 10 | | | | |
| 4 Results | 12 | | | | |
| 5 Substitution card | 10 | | | | |
| 6 Split, move by button | 10 | | | | |
| 7 Store mode | 11 | | | | |
| 8 Delete my data | 10 | | | | |

Overall: pass when no step is a fail in flows 1 to 8 on both required devices. A fail that blocks the
flow (the action cannot be done, or its result cannot be known) is a blocker for launch; the rest are
fixes to schedule. This is the criterion text for issue #26: "a screen reader pass in Hebrew RTL is
documented with findings and fixes".

## 13. Filing a defect

One issue per problem, on `NoaMcDa/SmartCart`, linked to #26, with the label `accessibility`. Title:
`[a11y][VO or TB or NV] ⟨flow and step⟩: ⟨what went wrong⟩`. Body:

```
Flow and step:        e.g. 6.7 Split, move by button
Device / OS / browser / reader (versions):
Reader settings:      language, rate, hints on or off
App build:            commit or URL, mock or demo
Steps:                what you did, gesture by gesture
Expected (from the plan): the text in "The app should say"
Heard:                what was spoken, word for word (or a screen recording with sound)
Seen:                 what the screen showed at that moment
Effect:               blocks the task / wrong or missing information / annoying
WCAG 2.0 criterion, if you know it: e.g. 4.1.2 name, role, value; 1.3.2 meaningful sequence;
                      2.4.3 focus order; 3.3.1 error identification; 4.1.3 is a 2.1 criterion
Workaround:           yes or no
```

Severity: **blocker** (the task cannot be completed, or its result cannot be understood), **major**
(completed with help or with wrong information), **minor** (extra noise, double reading, missing
convenience). Record screen: iPhone, Control Center, screen recording with the microphone on speaks
the reader's output into the recording; Android, the built-in screen recorder with sound.

After the pass, an engineer pastes the filled tables and the defect list into `docs/a11y-report.md`
under "Screen reader pass" (the report asks for that), updates `/accessibility` ("מה עדיין לא נבדק"),
and ticks the screen-reader item of #26. The things this plan already expects to find, from the
audit's own open list: no announcement when the results arrive (4.1), when rows are added to the
list (2.4) or when a step of onboarding changes (1.13); possible double reading in the
flexibility sheet (3.3); focus after an item leaves the split (6.7) or the store checklist (7.4).

# Flutter לאפליקציית השוואת המחירים: מה אפשר, מה לא, ואיזו ארכיטקטורה לבחור (אוקטובר 2026)

**כן, ומומלץ, אבל רק לצד הלקוח ובלי "הכל":** Flutter מתאים מאוד לאפליקציית המובייל (iOS + Android מקוד אחד) ואפשר להשתמש בו גם לאפליקציית Web אינטראקטיבית. מצד שני, הוא לא מתאים לדפי מוצר שצריכים להיות מאונדקסים בגוגל, ושכבות ה-ingestion, ה-ML והאופטימיזציה צריכות להישאר בפייתון. ההמלצה: Flutter במובייל, Supabase כ-backend מנוהל, שירות FastAPI רזה ו-workers בפייתון, ודפי SEO סטטיים נפרדים.

## TL;DR
- **צד לקוח:** Flutter 3.47 (אוגוסט 2026, עם Dart 3.13) הוא בחירה בוגרת ל-iOS/Android, עם תמיכה טובה ב-RTL ובנגישות. מחליפים את React Native/Expo ב-Flutter, ולא משתמשים ב-Flutter Web לדפים שנשענים על SEO. גם התיעוד הרשמי של Flutter מפנה לתוכן כזה ל-Jaspr או לאתר HTML רגיל.
- **Backend:** "full-stack Dart" (Serverpod 4, Dart Frog) אפשרי טכנית, אבל לא כדאי כאן. ל-OR-Tools אין bindings רשמיים ל-Dart, והאקוסיסטם של embeddings, cross-encoders ו-LLM נמצא בפייתון. ML Kit גם לא מזהה טקסט בכתב עברי, כך ש-OCR של קבלות עבריות לא יכול להתבסס עליו.
- **הארכיטקטורה המומלצת:** Flutter, Supabase (Postgres + pgvector + PostGIS, Auth, Realtime לרשימות משותפות), שירות FastAPI רזה לחיפוש סמנטי ולאופטימיזציית עגלה, ו-workers בפייתון ל-ingestion ול-ML. דפי ה-SEO נבנים בפייתון/Jinja בשלב ה-MVP, ו-Jaspr היא אפשרות להמשך. ההערכה: כ-40–100$ לחודש בשלב MVP, ותוספת של 2–4 שבועות ללמידת Dart/Flutter.

## Key Findings

| נושא | ממצא מאומת | המשמעות לפרויקט |
|---|---|---|
| גרסה ובשלות | Flutter 3.47 יצא ב-12.8.2026 עם Dart 3.13. Material ו-Cupertino הפכו לחבילות עצמאיות (`material_ui`, `cupertino_ui` 1.0), והוצאה משימוש רשמית של הספריות המובנות ב-SDK מתוכננת ל-stable של נובמבר 2026. לוח השחרורים ל-2026: 3.41 בפברואר, 3.44 במאי, 3.47 באוגוסט, 3.50 בנובמבר | כדאי להתחיל פרויקט חדש ישר על `material_ui`, וכך לא תצטרכי מיגרציה בעוד חודשיים |
| Impeller | ב-3.38 בוטלה (deprecated) האפשרות לכבות את Impeller ב-Android, וב-3.47 הוא הפך לברירת המחדל גם בדסקטופ | ביצועים עקביים במובייל, בלי "jank" של קומפילציית shaders |
| Flutter Web | ב-build רגיל משתמשים ב-CanvasKit. ב-build עם `--wasm` משתמשים ב-skwasm, ואם הדפדפן לא תומך חוזרים ל-CanvasKit. ה-HTML renderer הוסר ב-3.29 | הדף מצויר על canvas ולא כ-DOM סמנטי, ולכן הוא לא מתאים ל-SEO |
| עמדת צוות Flutter על SEO | לפי התיעוד, תוכן עשיר בטקסט, זורם וסטטי "benefit from the document-centric model". הוא מפנה ל-Jaspr, שבו "makes SEO work in the same way a traditional website would". לפי צוות Flutter, כל שלושת האתרים (dart.dev, ‏flutter.dev ו-docs.flutter.dev) הועברו ל-Jaspr, ולפי Google Open Source Blog ‏jaspr_content מפעיל את תיעוד flutter.dev ו-dart.dev, שכולל יותר מ-3,900 דפים | זו המלצה רשמית להפריד בין האפליקציה לבין דפי התוכן |
| נגישות ב-Web | עץ ה-Semantics מתורגם ל-DOM נגיש עם תפקידי ARIA. בברירת המחדל משתמש עם קורא מסך צריך ללחוץ על כפתור נסתר, "Enable accessibility", אלא אם האפליקציה מפעילה את הנגישות בקוד | אם משתמשים ב-Flutter Web, חובה להפעיל semantics בקוד |
| OCR בעברית | ML Kit Text Recognition v2 תומך רק בכתב לטיני, סיני, דוונאגרי, יפני וקוריאני. אין בו עברית | אם רוצים OCR לקבלות, עושים אותו בצד השרת או עם Tesseract (`heb`) |
| OR-Tools ב-Dart | יש רק בקשת פיצ'ר פתוחה (issue #2830) ל-bindings רשמיים | שכבת האופטימיזציה נשארת בפייתון |
| Serverpod 4 | גרסה 4.0.3 יצאה ב-25.9.2026. היא כוללת Postgres מוטמע עם pgvector ו-PostGIS, טיפוסי geography, ומסד SQLite בצד הלקוח עם סנכרון offline (ניסיוני) | זה ה-backend הבשל ביותר ב-Dart, אבל הוא מוסיף שכבה שלישית לתחזוקה |

## Details

### 1. Flutter לצד הלקוח

**בשלות ויציבות.** ב-2026 יוצאות ארבע גרסאות stable בלוח זמנים ידוע מראש, ו-3.47 מתוארת כצעד לקראת מסגרת מודולרית יותר. מה שהכי רלוונטי לך כאן: Widget Previews הפכו ליציבים, ו-hot reload ב-Web הוא ברירת המחדל מאז 3.35. במובייל אין כיום סיכון טכנולוגי משמעותי. הסיכונים נמצאים ב-Web ובחבילות צד שלישי.

**Web, ‏WebAssembly וגודל ה-bundle.** לפי התיעוד הרשמי, ל-skwasm יש זמן עלייה וביצועי פריימים טובים יותר משל CanvasKit. הוא דורש תמיכה ב-WasmGC בדפדפן, וכשאין תמיכה Flutter חוזר אוטומטית ל-CanvasKit. לפי דף "Web renderers" בתיעוד הרשמי, CanvasKit "adds about 1.5MB in download size" ו-skwasm, גרסה קומפקטית יותר של Skia, מוסיף "about 1.1MB", וזה עוד לפני קוד האפליקציה. בעקבות זה, זמן הטעינה הראשונה של Flutter Web ארוך מזה של אתר HTML רגיל. ‏3.47 ממשיכה להתקדם לעבר Wasm כברירת מחדל ומציגה טעינה דחויה (deferred loading) ב-Wasm, כרגע כפיצ'ר ניסיוני. **הערכה:** בשביל משתמש שמגיע מגוגל לדף מחיר, זמן הטעינה הזה הוא חיסרון ממשי. בשביל משתמש חוזר שעובד מהמחשב על רשימת הקניות שלו, הוא סביר.

**RTL ועברית.** התמיכה בנויה בתוך המסגרת:
- **כיוון:** `Directionality` נגזר מה-locale. ב-`MaterialApp` מגדירים `supportedLocales: [Locale('he')]` ומעבירים את ה-delegates של הלוקליזציה. שימי לב: ב-3.47 `flutter_localizations` הופרד מה-SDK, והחבילה `material_ui` חושפת אוסף מאוחד, `GlobalMaterialLocalizations.delegates`.
- **פריסה:** משתמשים רק ב-`EdgeInsetsDirectional`, ב-`AlignmentDirectional` וב-`TextAlign.start`/`end`, ולא ב-left/right.
- **מחירים ומספרים בתוך טקסט עברי:** לפי תיעוד `Text.textDirection`, הכיוון של המשפט כולו קובע את הסדר של קטעים מעורבים. **פרקטיקה מומלצת:** ליצור widget ייעודי `PriceText` שעוטף את המחיר ב-`Directionality(textDirection: TextDirection.ltr)`, או שמבודד אותו בתווי Unicode ‏LRI/PDI. את המחיר עצמו מעצבים עם `intl` (`NumberFormat.currency(locale: 'he_IL', symbol: '₪')`).
- **באגים ידועים:** קיים issue פתוח (#123563) על מיקום שגוי של סימני פיסוק בעברית ב-RTL. קחי את זה בחשבון כשאת מתכננת טקסטים ובדיקות.
- **גופנים:** Heebo ו-Assistant זמינים דרך `google_fonts`. מומלץ לארוז אותם כ-assets כדי שלא יהיו תלויים בהורדה בזמן ריצה, וכדי שיעבדו גם offline.

**נגישות (WCAG / ת"י 5568).** במובייל, Semantics עובד מול TalkBack ו-VoiceOver, ובגרסאות האחרונות נוספו כלים:
- ‏3.35: ‏`SemanticsLabelBuilder` ו-`SliverEnsureSemantics`.
- ‏3.38: אפשר להפעיל נגישות כברירת מחדל ב-iOS דרך `ensureSemantics`.
- ‏3.41: האפליקציה מכבדת התאמות ריווח טקסט של המשתמש ב-Web, ונוספו matchers לבדיקות (`isSemantics`, `accessibilityAnnouncement`).

ב-Web, `SemanticsRole` ממופה לתפקידי ARIA, ו-`headingLevel` עובד רק שם. **מה צריך לעשות:** להפעיל semantics בקוד ב-Web, להוסיף `tooltip`/`Semantics(label:)` לכל כפתור אייקון (למשל "הוסף לרשימה"), ולוודא יחסי ניגודיות של 4.5:1 לפחות. **הערה:** התקן הישראלי מבוסס על WCAG, ולכן Flutter Web דורש עבודה ידנית מכוונת כדי לעמוד בו. דף HTML רגיל עומד בו כמעט "מובנה".

**חבילות מרכזיות.** הגרסאות בטבלה אומתו ב-pub.dev בספטמבר–אוקטובר 2026. לגבי חבילות שמסומנות "לאמת", מומלץ להוסיף אותן עם `flutter pub add` כדי לקבל את הגרסה העדכנית.

| צורך | חבילה מומלצת | גרסה / הערה |
|---|---|---|
| ברקוד | `mobile_scanner` | 7.4.2. משתמשת ב-ML Kit ב-Android, ב-Apple Vision ב-iOS וב-ZXing ב-Web. הגרסה הארוזה (bundled) מוסיפה 3–10MB ב-Android |
| state management | `flutter_riverpod` (+ `riverpod_generator`) | 3.4.3 (4.9.2026). Riverpod 3 יציב מספטמבר 2025 |
| backend client | `supabase_flutter` | 2.18.0 (יש prerelease 3.0.0-dev). כולל Auth, PostgREST, Realtime ו-Storage |
| קלט קולי | `speech_to_text` | 7.5.0. משתמשת במנוע הזיהוי של המכשיר. he-IL זמין ב-iOS לפי מקורות משניים, וב-Android לא אומת. את הזמינות בודקים בזמן ריצה עם `locales()`, והחבילה מיועדת ל"פקודות וביטויים קצרים" |
| OCR קבלות | בצד השרת (Google Cloud Vision, שתומך בעברית עם הקוד `iw`) או `flutter_tesseract_ocr` 0.4.31 עם `heb.traineddata` | `google_mlkit_text_recognition` 0.17.1 לא תומך בעברית |
| ניווט | `go_router` | לאמת גרסה. נדרש בשביל URLs ו-deep links |
| אחסון מקומי | `drift` (SQLite, עם תמיכה ב-Web) | לאמת גרסה. עדיף על Isar ו-Hive כשמדובר במבנה רלציוני של רשימות ומוצרים |
| מפות ומיקום | `flutter_map` (OSM, בלי עלות API) או `google_maps_flutter`, יחד עם `geolocator` | לאמת גרסה |
| התראות | `firebase_messaging` + `flutter_local_notifications` | לאמת גרסה. FCM נשאר גם בלי Firebase כ-backend |
| גרפים | `fl_chart` (קוד פתוח) | לאמת גרסה. Syncfusion דורש רישיון (קיים רישיון קהילתי) |
| מודלים ו-API | `freezed` + `json_serializable`, ‏`dio` + `retrofit` | לאמת גרסה |

**SEO: הבעיה המרכזית.** Flutter Web מצייר על canvas. חבילות כמו `seo` מייצרות "צל" HTML לסורקים, אבל זה פתרון עוקף ולא מה שהתיעוד הרשמי ממליץ עליו. אם עושק והזול נשענים על דפי מוצר שמאונדקסים בגוגל, Flutter Web לא יכול להתחרות בהם על תנועה אורגנית. החלופות:

- **(א) Flutter Web לאפליקציה, ואתר דפי SEO נפרד. זו ההמלצה.** הדפים יושבים בדומיין הראשי, והאפליקציה ב-`app.` ‏(או שאין אפליקציית Web בכלל בשלב הראשון). בשלב ה-MVP הדפים הסטטיים נוצרים ב-**פייתון/Jinja**, מאותו קטלוג קנוני, כחלק מה-batch היומי, ונפרסים ל-CDN. זה מתאים לחוזקות שלך ולא מוסיף טכנולוגיה חדשה.
- **(ב) Jaspr: להישאר ב-Dart.** הגרסה הנוכחית היא 0.23.5 (25.9.2026), והיא תומכת בשלושה מצבים: static (SSG), server (SSR) ו-client. לפי Google Open Source Blog (אפריל 2026), גוגל בחרה ב-Jaspr לאתרי dart.dev, ‏flutter.dev ו-docs.flutter.dev, שמשמשים "over a million monthly active users". **מגבלה:** במצב static "path parameters are not supported", ולכן כדי לייצר עשרות אלפי דפי מוצר צריך `jaspr_router` שימנה את כל הנתיבים, או מצב server עם CDN. היא מתאימה לשלב שני, אם תרצי לשתף מודלים וקוד Dart בין האפליקציה לאתר.
- **(ג) לוותר על SEO ב-MVP.** זה לגיטימי אם ערוץ ההפצה הראשוני הוא חנויות האפליקציות או קהילות. **הערכה:** כדאי בכל זאת לבנות עשרות דפי קטגוריה סטטיים כבר מההתחלה, כי האינדוקס לוקח חודשים.

**Flutter מול React Native/Expo, למקרה הזה.**

| קריטריון | Flutter | React Native / Expo |
|---|---|---|
| עקומת למידה ממי שבאה מפייתון ו-C# | Dart מוקלדת, מבוססת מחלקות, עם async/await, ולכן קרובה ל-C#. **הערכה:** זו מעבר נוח יותר מ-TS + React למי שאין לה רקע ב-Web | צריך ללמוד JS/TS, React ו-hooks |
| ביצועים ו-UI | מנוע ציור עצמאי (Impeller) ו-UI זהה בכל הפלטפורמות | רכיבים נייטיב (New Architecture) |
| Web ו-SEO | חלש לדפי תוכן, ונדרש אתר נפרד | ‏Next.js חולק את השפה ואת חלק מהקוד |
| עדכוני OTA | Shorebird: עדכון קוד Dart בלבד, בלי נייטיב ובלי שינוי גרסת Flutter. המסלול החינמי כולל 5,000 התקנות patch בחודש, ו-Pro עולה 20$ עם 50,000 התקנות | ‏EAS Update בשל ומשולב |
| גיוס | **מקורות משניים (מאמרים, לא סקרים רשמיים):** בארה"ב יש פי 2 עד 6 יותר משרות ל-React Native. **לגבי ישראל אין נתון מאומת**. ההערכה היא שהיחס דומה, בגלל היתרון של מאגר מפתחי ה-JS | יתרון |

**שורה תחתונה:** אם החשש העיקרי שלך הוא ה-Web, React Native עדיף. אם החשש הוא חוויית מובייל ונוחות שפה, Flutter עדיף. מאחר ש-SEO נפתר ממילא באתר נפרד (Jinja או Jaspr), היתרון של React Native מצטמצם בעיקר לגיוס עובדים.

### 2. Flutter/Dart גם ל-backend?

**האפשרויות ובשלותן:**
- **Serverpod 4:** הבחירה הבשלה ביותר. יש לו ORM עם טיפוס Vector ואינדקסי HNSW ו-IVFFLAT (מאז 2.8), טיפוסי PostGIS geography עם אינדקסי GiST, קוד לקוח שנוצר אוטומטית, ו-`serverpod start` שמריץ את כל ה-stack. הוא דורש Dart 3.12.2 ו-Flutter 3.44.4 לפחות. שימי לב שגרסה 4 כללה הרבה שינויים שוברים, וזה סימן לקצב שינוי מהיר.
- **Dart Frog:** בשל וקל משקל, ומאז שעבר לארגון קהילתי (dart-frog-dev) הוא מתוחזק על ידי הקהילה. **Shelf** הוא שכבה נמוכה עוד יותר.
- **BaaS:** ‏Supabase מספק לך Postgres אמיתי עם pgvector ו-PostGIS ועם client רשמי ל-Flutter. ‏Firebase (Firestore) לא מתאים לשאילתות רלציוניות וגיאוגרפיות על מחירים. Data Connect הוא מבוסס Postgres, אבל מוסיף עוד שכבה. Appwrite ו-PocketBase לא מספקים pgvector או PostGIS ברמה הנדרשת.

**מה נשאר בפייתון, ולמה:**

| שכבה | למה לא Dart |
|---|---|
| Ingestion (‏`israeli-supermarket-scarpers`, `il-supermarket-parser`) | הלוגיקה כבר קיימת ומתוחזקת בפייתון. לפי PyPI, ‏`il-supermarket-parser` (מארגון OpenIsraeliSupermarkets) הוא "a parser for ALL the supermarket chains listed in the GOV.IL site". כתיבה מחדש היא עבודה של חודשים בלי שום תועלת |
| חילוץ מאפיינים ב-LLM, embeddings ‏(BGE-M3 / e5), cross-encoder, fine-tuning | ‏sentence-transformers, PyTorch ו-HF הם אקוסיסטם פייתוני. ב-Dart אין שכבה מקבילה |
| ‏ILP ‏(OR-Tools / HiGHS) | אין bindings רשמיים ל-Dart (יש רק issue #2830). אפשר לכתוב FFI עם `ffigen`, אבל זה פרויקט בפני עצמו |
| embedding של שאילתת חיפוש בזמן אמת | חיפוש סמנטי צריך לקודד את השאילתה עם אותו מודל, ולכן נדרש שירות פייתון **מקוון**, ולא רק batch |

**ארכיטקטורות היברידיות.** העלויות הן הערכות שלי. מחיר הבסיס של Supabase מאומת:

| אפשרות | מבנה | יתרונות | חסרונות | עלות חודשית (הערכה) |
|---|---|---|---|---|
| **(א) Flutter + Supabase + שירות פייתון רזה. ההמלצה** | Flutter קורא קטלוג ומחירים דרך PostgREST/RPC, ‏Realtime משמש לרשימות משותפות, ו-Auth של Supabase. שירות FastAPI קטן מטפל ב-`/search` (embedding + pgvector + rerank) וב-`/optimize` (ILP). workers ל-ingestion ול-ML כותבים ישירות ל-Postgres | הכי מעט קוד backend לכתוב, Auth ו-Realtime מוכנים, ו-RLS לאבטחה | צריך לנהל שני מקורות API ולהגדיר RLS בקפידה. Edge Functions של Supabase כתובות ב-TS/Deno ולא בפייתון | לפי דף התמחור של Supabase, ‏Pro עולה 25$ לחודש וכולל "$10/mo in compute credits, enough to cover one Micro instance", וגם 100,000 MAU ו-250GB egress (מעבר לזה: ‏0.00325$ ל-MAU ו-0.09$ ל-GB). אליו מתווספים VPS או container לפייתון (כ-10–40$) ועלויות LLM/API. **סה"כ כ-40–100$** |
| **(ב) Flutter + FastAPI מלא** (כמו בתכנון המקורי) | כל הקריאות עוברות דרך FastAPI, שמחובר ל-Postgres ול-Redis | שליטה מלאה, API אחד, ולקוח Dart טיפוסי שנוצר מ-OpenAPI | צריך לכתוב בעצמך Auth, Realtime ו-pagination | כ-60–150$ (כמו בדוח הקודם) |
| **(ג) Flutter + Serverpod + מיקרו-שירות פייתון** | Serverpod אחראי על CRUD, Auth ו-streaming, ופייתון על ML ו-ILP | שפה אחת בין הלקוח לשרת, ומודלים משותפים | שלוש שכבות (Dart server, פייתון, DB), קהילה קטנה יותר ושינויים שוברים תכופים | כ-60–150$. **לא מומלץ לצוות קטן** |

**לקוח API טיפוסי מ-FastAPI.** FastAPI מייצר OpenAPI 3.1. ‏`swagger_parser` תומך ב-OpenAPI 2, ‏3.0 ו-3.1, ומייצר לקוחות retrofit (על dio) ומודלים עם freezed, ‏json_serializable או dart_mappable. התהליך: משיגים את `openapi.json`, מריצים `dart run swagger_parser`, ואחר כך `dart run build_runner build`. קיים גם `openapi_retrofit_generator`, שהוא שכתוב של swagger_parser. **פרקטיקה:** שמים את הלקוח שנוצר בחבילה נפרדת (`packages/api_client`) ומייצרים אותו מחדש ב-CI בכל שינוי של הסכמה.

**מודלים על המכשיר.** ברוב המקרים זה לא רלוונטי ל-MVP:
- **סריקת ברקוד:** כבר רצה על המכשיר דרך `mobile_scanner`.
- **OCR קבלות:** ML Kit לא תומך בעברית. Tesseract על המכשיר אפשרי, אבל לפי ה-README הוא "slower than ml_kit" ודורש לארוז את קובץ ה-traineddata. **מומלץ** לבצע OCR בצד השרת (Cloud Vision), כפיצ'ר של שלב 2.
- **חיפוש סמנטי offline:** הרצת BGE-M3 על הטלפון כבדה מדי. חלופה סבירה היא מטמון מקומי ב-`drift` של רשימות ומחירים אחרונים, עם חיפוש טקסטואלי, ובלי embeddings על המכשיר.

### 3. המלצה סופית

**ללכת על Flutter לאפליקציית המובייל, בארכיטקטורה (א).**

**לפני ואחרי:**

| רכיב | תכנון מקורי | תכנון מעודכן |
|---|---|---|
| מובייל | React Native / Expo | **Flutter 3.47 + Riverpod 3 + go_router + drift** |
| Web אפליקטיבי | Next.js | Flutter Web (אופציונלי, שלב 2, עם semantics מופעל) |
| Web ל-SEO | Next.js (SSR) | **דפים סטטיים בפייתון/Jinja על CDN**, ואחר כך אולי Jaspr |
| API | ‏FastAPI לכל הקריאות | ‏Supabase (PostgREST/RPC, Auth, Realtime) **ו**-FastAPI רזה (`/search`, `/optimize`) |
| Auth | ‏(בתוך FastAPI) | Supabase Auth |
| רשימות משותפות | WebSocket או Redis | Supabase Realtime |
| Redis | נדרש | אופציונלי (מטמון לתוצאות אופטימיזציה) |
| DB, ingestion, ML, ILP | ללא שינוי | ללא שינוי (פייתון + Postgres/pgvector/PostGIS) |
| OTA | ‏EAS Update | Shorebird (חינמי עד 5,000 התקנות patch בחודש) |
| OCR קבלות | לא הוגדר | בצד השרת (Cloud Vision, עברית), בשלב 2 |

**שינויים ב-roadmap (הערכה):**
- **שבועות 0–3:** למידת Dart ו-Flutter. מומלץ ה-Learn pathway הרשמי ו-codelab על Riverpod. זו תוספת של כ-2–4 שבועות לעומת React Native, ובערך מתקזזת מול החיסכון בכתיבת Auth ו-Realtime בזכות Supabase.
- **במקביל:** ה-ingestion וקטלוג ה-ML בפייתון ממשיכים בלי שינוי.
- **שלב MVP:** חיפוש, עגלה ואופטימיזציה, רשימות משותפות, ברקוד ומפת סניפים במובייל, וכ-50–200 דפי קטגוריה ו"מוצר מוביל" סטטיים לגוגל.
- **שלב 2:** OCR קבלות, Flutter Web, Jaspr (אם תרצי), וקלט קולי.

**מבנה פרויקט מוצע (monorepo):**
```
/apps/mobile            # Flutter
  lib/
    app/                # router (go_router), theme, l10n (he), DI
    core/               # PriceText (LTR isolation), formatting, errors
    data/
      services/         # supabase_client, api_client (generated), local_db (drift)
      repositories/     # ProductsRepo, PricesRepo, ListsRepo, OptimizeRepo
    features/
      search/  cart/  lists/  scanner/  stores_map/  price_history/
        ui/ (widgets)   view_models/ (Riverpod Notifiers)
/packages/api_client    # swagger_parser output (retrofit+freezed)
/services/ingest        # Python: scrapers/parsers → Postgres
/services/catalog_ml    # Python: LLM attributes, BGE-M3, cross-encoder (batch)
/services/api           # FastAPI: /search, /optimize (OR-Tools/HiGHS)
/web/seo                # Jinja templates → static HTML → CDN
/supabase               # migrations, RLS policies, RPC functions (SQL)
```
החלוקה בין שכבת UI לשכבת data (repositories ו-services) תואמת את מדריך הארכיטקטורה הרשמי של Flutter. Riverpod Notifiers משמשים כ-view models. הקוד מאורגן לפי פיצ'ר כדי שיהיה קל להוסיף מסכים.

**סיכונים ייחודיים ל-Flutter ודרכי התמודדות:**
- **המעבר ל-`material_ui`/`cupertino_ui` ופיצול הלוקליזציה:** להתחיל ישר על החבילות החדשות. אם חבילה תלויה עדיין צריכה את Material הישן, להשתמש ב-`MaterialUiCompatibilityBridge`.
- **באגי BiDi בעברית:** לרכז את כל הטיפול ב-`PriceText` אחד, ולהוסיף golden tests ל-RTL.
- **תלות בחבילות קהילתיות** (למשל שינויים שוברים בעבר ב-`mobile_scanner`): לנעול גרסאות, ולבצע שדרוגים יזומים פעם ברבעון, בהתאם ללוח השחרורים.
- **מגבלות Shorebird:** הוא לא מעדכן קוד נייטיב, assets או את גרסת Flutter. לכן שינויים בפלאגינים עדיין דורשים שחרור לחנות.
- **גיוס:** המאגר מצומצם יותר משל React Native. כדי לפצות, להשקיע בקוד ברור, בבדיקות ובתיעוד, ולגייס מפתחי C# או Kotlin שמסתגלים מהר ל-Dart (הערכה).

## Caveats
- נתוני הגיוס והשוק (פי 2 עד 6 יותר משרות ל-React Native) מגיעים ממאמרים משניים בארה"ב ולא מסקרים רשמיים. **אין נתון מאומת לישראל.**
- ש-he-IL זמין ב-`speech_to_text` ב-iOS ידוע רק ממקורות משניים, וב-Android זה לא אומת. צריך לבדוק בזמן ריצה.
- העלויות החודשיות של חלופות (א)–(ג) הן הערכות. רק מחיר הבסיס של Supabase Pro (25$ עם קרדיט compute של 10$) ומחירי Shorebird אומתו. צמיחה ב-MAU, ב-egress או ב-compute תייקר את החשבון. לדוגמה, לפי דף התמחור של Supabase מופע Large ‏(2 vCPU, ‏8GB) עולה 110$ לחודש, כלומר כ-100$ נטו אחרי הקרדיט.
- הגרסאות בטבלאות נכונות לסוף ספטמבר ותחילת אוקטובר 2026. גרסה 3.50 של Flutter צפויה בנובמבר 2026, ואיתה ההוצאה משימוש הרשמית של הספריות המובנות.
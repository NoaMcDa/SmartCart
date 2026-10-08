import { defineMessages } from "../messages";

/**
 * Shared lists: share sheet, invite page, members, live checklist (features/share). Arabic
 * machine-drafted, needs native-speaker review (#73).
 */
export const shareMessages = defineMessages({
  he: {
    roleEditor: "עריכה",
    roleViewer: "צפייה בלבד",
    roleOwner: "בעלים",

    // Errors of the share and accept calls
    errShareSignIn: "צריך להתחבר כדי לשתף רשימה.",
    errShareForbidden: "שיתוף משפחתי הוא חלק מהמנוי, או שהרשימה הזו לא שלך.",
    errShareNotFound: "הרשימה לא נמצאה.",
    errServer: "השרת החזיר שגיאה. נסי שוב בעוד רגע.",
    errOffline: "נראה שאין חיבור לשרת. בדקי את החיבור ונסי שוב.",
    errAcceptSignIn: "צריך להתחבר כדי להצטרף לרשימה.",
    errAcceptInvalid: "הקישור לא תקף: ייתכן שפג תוקפו או שהבעלים ביטלה אותו. בקשי קישור חדש.",

    // Share sheet
    sheetEyebrow: "שיתוף הרשימה",
    inviteFamily: "הזמנת בני משפחה",
    sheetHint:
      "מי שתקבל את הקישור תתחבר, תצטרף ותראה את הרשימה ואת השינויים בה בזמן אמת. היא לא רואה את המיקום או ההעדפות שלך.",
    shareSignInNote: "כדי לשתף צריך להתחבר, כך שרק מי שהוזמנה תגיע לרשימה.",
    signIn: "התחברות",
    permissionLabel: "הרשאה למוזמנת",
    inviteLinkLabel: "קישור הזמנה ({role})",
    copyLink: "העתקת הקישור",
    nativeShareTitle: "רשימת קניות ב-SmartCart",
    shareOnPhone: "שיתוף בטלפון",
    revokeLink: "ביטול הקישור",
    creatingLink: "יוצרת קישור…",
    createLink: "יצירת קישור הזמנה",
    linkRevoked: "הקישור בוטל. מי שקיבלה אותו לא תוכל להצטרף, ומי שכבר הצטרפה איבדה גישה.",
    linkCopied: "הקישור הועתק.",
    copyFailed: "לא הצלחנו להעתיק אוטומטית. סימנו את הקישור, אפשר להעתיק אותו ידנית.",

    // Members
    memberOwner: "הבעלים של הרשימה",
    memberPending: "הזמנה ממתינה",
    memberMember: "חברה ברשימה",
    membersHeading: "מי ברשימה",
    roleNotJoined: "{role} · עדיין לא הצטרפה",
    removeMemberAria: "הסרת חברה מהרשימה ({role})",
    removeMember: "הסרה מהרשימה",
    revokeInviteAria: "ביטול הזמנה ממתינה ({role})",
    revokeInvite: "ביטול ההזמנה",
    membersHint: "חברים רואים רק את הרשימה. המיקום וההעדפות של כל אחת נשארים אצלה.",

    // Add item
    addItemLabel: "הוספת פריט לרשימה המשותפת",
    addItemPlaceholder: "למשל: חלב",
    search: "חיפוש",
    noHits: "לא מצאנו מוצר כזה. נסי ניסוח אחר.",
    hitsLabel: "תוצאות חיפוש",
    addHit: "הוספי: {name}",

    // Items
    checkAria: "סימון {name} כנאסף",
    removeItemAria: "הסרת {name} מהרשימה המשותפת",
    removeItem: "הסרה",
    itemsHeading: "פריטים ברשימה (<ltr>{count}</ltr>)",
    emptyList: "הרשימה ריקה. הוסיפי פריט וכולם יראו אותו.",

    // Shared list screen
    loadingList: "טוענת את הרשימה",
    listNotFound: "הרשימה לא נמצאה, או שאין לך גישה אליה.",
    listForbidden: "צריך להתחבר עם החשבון שהוזמן כדי לראות את הרשימה.",
    listLoadError: "לא הצלחנו לטעון את הרשימה. בדקי את החיבור ונסי שוב.",
    retry: "נסי שוב",
    syncRealtime: "מתעדכן בזמן אמת",
    syncConnecting: "מתחברת לעדכונים בזמן אמת…",
    syncPolling: "מתעדכן כל כמה שניות",
    pendingSync: "ממתין לסנכרון (<ltr>{count}</ltr>)",
    sharedWithMe: "רשימות ששיתפו איתך",
    mineHeading: "שיתוף הרשימה שלך",
    mineEmpty: "הרשימה ריקה, ואין מה לשתף עדיין. הוסיפי פריטים ואז חזרי לכאן.",
    buildList: "לבניית הרשימה",
    mineBody:
      'ניצור עותק משותף של "{name}" (<ltr>{count}</ltr> פריטים). מי שתזמיני תוכל לראות ולערוך אותו, ושינויים יופיעו אצל כולן. הרשימה שלך במכשיר נשארת כמו שהיא.',
    creatingList: "יוצרת…",
    createShared: "יצירת רשימה משותפת",
    backToMine: "חזרה לרשימה שלי",

    // Invite page
    acceptHeading: "הוזמנת לרשימת קניות משותפת",
    acceptBody:
      "אחרי ההצטרפות תראי את הרשימה ואת השינויים בה בזמן אמת. מי שהזמינה אותך תראה שהצטרפת, אבל לא תראה את המיקום או ההעדפות שלך.",
    acceptSignInNote: "כדי להצטרף צריך להתחבר, כך שהרשימה נשמרת בחשבון שלך.",
    joining: "מצטרפת…",
    join: "הצטרפות לרשימה",

    // Messages the sync hook raises (shown by the screen)
    msgRefused: "השינוי לא נשמר, אז החזרנו את הרשימה למה שהיה. נסי שוב.",
    msgPartial: "חלק מהשינויים לא נשמרו, אז טענו את הרשימה מחדש.",
    msgAddFailed: "הפריט לא נוסף. נסי שוב.",
    msgRevokeFailed: "ההזמנה לא בוטלה, אז החזרנו אותה לרשימה. נסי שוב.",
    msgRemoveFailed: "החברה לא הוסרה, אז החזרנו אותה לרשימה. נסי שוב.",
  },
  // Arabic machine-drafted, needs native-speaker review (#73).
  ar: {
    roleEditor: "تعديل",
    roleViewer: "مشاهدة فقط",
    roleOwner: "المالك",

    errShareSignIn: "يلزم تسجيل الدخول لمشاركة قائمة.",
    errShareForbidden: "المشاركة العائلية جزء من الاشتراك، أو أن هذه القائمة ليست قائمتك.",
    errShareNotFound: "لم يتم العثور على القائمة.",
    errServer: "أعاد الخادم خطأً. حاول مرة أخرى بعد قليل.",
    errOffline: "يبدو أنه لا يوجد اتصال بالخادم. تحقق من الاتصال وحاول مرة أخرى.",
    errAcceptSignIn: "يلزم تسجيل الدخول للانضمام إلى القائمة.",
    errAcceptInvalid: "الرابط غير صالح: ربما انتهت صلاحيته أو ألغاه المالك. اطلب رابطًا جديدًا.",

    sheetEyebrow: "مشاركة القائمة",
    inviteFamily: "دعوة أفراد العائلة",
    sheetHint:
      "من يستلم الرابط يسجّل الدخول وينضم ويرى القائمة والتغييرات عليها لحظة بلحظة. لا يرى موقعك ولا تفضيلاتك.",
    shareSignInNote: "للمشاركة يلزم تسجيل الدخول، حتى لا يصل إلى القائمة إلا من تمت دعوته.",
    signIn: "تسجيل الدخول",
    permissionLabel: "صلاحية المدعو",
    inviteLinkLabel: "رابط الدعوة ({role})",
    copyLink: "نسخ الرابط",
    nativeShareTitle: "قائمة تسوّق في SmartCart",
    shareOnPhone: "مشاركة عبر الهاتف",
    revokeLink: "إلغاء الرابط",
    creatingLink: "جارٍ إنشاء الرابط…",
    createLink: "إنشاء رابط دعوة",
    linkRevoked: "تم إلغاء الرابط. من استلمه لن يتمكن من الانضمام، ومن انضم من قبل فقد الوصول.",
    linkCopied: "تم نسخ الرابط.",
    copyFailed: "تعذّر النسخ تلقائيًا. حدّدنا الرابط، ويمكنك نسخه يدويًا.",

    memberOwner: "مالك القائمة",
    memberPending: "دعوة قيد الانتظار",
    memberMember: "عضو في القائمة",
    membersHeading: "من في القائمة",
    roleNotJoined: "{role} · لم ينضم بعد",
    removeMemberAria: "إزالة عضو من القائمة ({role})",
    removeMember: "إزالة من القائمة",
    revokeInviteAria: "إلغاء دعوة قيد الانتظار ({role})",
    revokeInvite: "إلغاء الدعوة",
    membersHint: "يرى الأعضاء القائمة فقط. يبقى موقع كل عضو وتفضيلاته عنده.",

    addItemLabel: "إضافة صنف إلى القائمة المشتركة",
    addItemPlaceholder: "مثلًا: حليب",
    search: "بحث",
    noHits: "لم نجد منتجًا كهذا. جرّب صياغة أخرى.",
    hitsLabel: "نتائج البحث",
    addHit: "إضافة: {name}",

    checkAria: "تحديد {name} كمجموع",
    removeItemAria: "إزالة {name} من القائمة المشتركة",
    removeItem: "إزالة",
    itemsHeading: "الأصناف في القائمة (<ltr>{count}</ltr>)",
    emptyList: "القائمة فارغة. أضف صنفًا وسيراه الجميع.",

    loadingList: "جارٍ تحميل القائمة",
    listNotFound: "لم يتم العثور على القائمة، أو لا تملك صلاحية الوصول إليها.",
    listForbidden: "يلزم تسجيل الدخول بالحساب الذي تمت دعوته لرؤية القائمة.",
    listLoadError: "تعذّر تحميل القائمة. تحقق من الاتصال وحاول مرة أخرى.",
    retry: "حاول مرة أخرى",
    syncRealtime: "يتحدّث لحظة بلحظة",
    syncConnecting: "جارٍ الاتصال بالتحديثات الفورية…",
    syncPolling: "يتحدّث كل بضع ثوانٍ",
    pendingSync: "بانتظار المزامنة (<ltr>{count}</ltr>)",
    sharedWithMe: "قوائم شاركها الآخرون معك",
    mineHeading: "مشاركة قائمتك",
    mineEmpty: "القائمة فارغة ولا يوجد ما يُشارَك بعد. أضف أصنافًا ثم عد إلى هنا.",
    buildList: "إلى بناء القائمة",
    mineBody:
      'سننشئ نسخة مشتركة من "{name}" (<ltr>{count}</ltr> أصناف). من تدعوهم يمكنهم رؤيتها وتعديلها، وستظهر التغييرات عند الجميع. قائمتك على الجهاز تبقى كما هي.',
    creatingList: "جارٍ الإنشاء…",
    createShared: "إنشاء قائمة مشتركة",
    backToMine: "العودة إلى قائمتي",

    acceptHeading: "تمت دعوتك إلى قائمة تسوّق مشتركة",
    acceptBody:
      "بعد الانضمام سترى القائمة والتغييرات عليها لحظة بلحظة. من دعاك سيرى أنك انضممت، لكنه لن يرى موقعك ولا تفضيلاتك.",
    acceptSignInNote: "للانضمام يلزم تسجيل الدخول، حتى تُحفظ القائمة في حسابك.",
    joining: "جارٍ الانضمام…",
    join: "الانضمام إلى القائمة",

    msgRefused: "لم يتم حفظ التغيير، لذلك أعدنا القائمة إلى ما كانت عليه. حاول مرة أخرى.",
    msgPartial: "لم يتم حفظ بعض التغييرات، لذلك أعدنا تحميل القائمة.",
    msgAddFailed: "لم تتم إضافة الصنف. حاول مرة أخرى.",
    msgRevokeFailed: "لم يتم إلغاء الدعوة، لذلك أعدناها إلى القائمة. حاول مرة أخرى.",
    msgRemoveFailed: "لم تتم إزالة العضو، لذلك أعدناه إلى القائمة. حاول مرة أخرى.",
  },
});

export type ShareMessageKey = keyof (typeof shareMessages)["he"];

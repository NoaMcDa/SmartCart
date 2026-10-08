import { defineMessages } from "../messages";

/**
 * Labels for what the API sends as codes (`src/lib/attributes.ts`): attribute names, values and
 * units, plus the pieces of a tag's text.
 * Arabic machine-drafted, needs native-speaker review (#73).
 */
export const attributeMessages = defineMessages({
  he: {
    key_product_type: "סוג מוצר",
    key_pack_size: "גודל אריזה",
    key_unit: "יחידה",
    key_brand: "מותג",
    key_fat_pct: "אחוז שומן",
    key_base: "בסיס",
    key_kosher: "כשרות",
    key_state: "מצב",
    key_flavor: "טעם",

    base_soy: "סויה",
    base_almond: "שקדים",
    base_oat: "שיבולת שועל",
    base_rice: "אורז",
    base_coconut: "קוקוס",

    state_fresh: "טרי",
    state_frozen: "קפוא",
    state_dried: "מיובש",
    state_canned: "משומר",

    unit_g: "ג׳",
    unit_ml: "מ״ל",
    unit_unit: "יח׳",
    unit_kg: "ק״ג",
    unit_l: "ל׳",

    perUnitNumeric: "ל-{text}",
    perUnitWord: "ל{text}",

    tagUnverified: "{text} · לא מאומת",
    tagDiffers: "{label}: {value}",
    tagMatched: "{label}, {value}",
  },
  ar: {
    key_product_type: "نوع المنتج",
    key_pack_size: "حجم العبوة",
    key_unit: "الوحدة",
    key_brand: "الماركة",
    key_fat_pct: "نسبة الدسم",
    key_base: "المكوّن الأساسي",
    key_kosher: "الكاشير",
    key_state: "الحالة",
    key_flavor: "النكهة",

    base_soy: "الصويا",
    base_almond: "اللوز",
    base_oat: "الشوفان",
    base_rice: "الأرز",
    base_coconut: "جوز الهند",

    state_fresh: "طازج",
    state_frozen: "مجمّد",
    state_dried: "مجفّف",
    state_canned: "معلّب",

    unit_g: "غ",
    unit_ml: "مل",
    unit_unit: "وحدة",
    unit_kg: "كغ",
    unit_l: "ل",

    perUnitNumeric: "لكل {text}",
    perUnitWord: "لكل {text}",

    tagUnverified: "{text} · غير موثّق",
    tagDiffers: "{label}: {value}",
    tagMatched: "{label}، {value}",
  },
});

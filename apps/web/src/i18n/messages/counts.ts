import { defineMessages } from "../messages";

/**
 * Counted nouns shared by the list, compare, split, store and budget screens. Each noun has four
 * forms (`_one`, `_two`, `_few`, `_many`, see `plural.ts`); Hebrew uses two and repeats the plural.
 * `item` is "פריט" for exactly one; `items` keeps the plural for every number, as the Hebrew
 * screens always wrote "N פריטים".
 * Arabic machine-drafted, needs native-speaker review (#73).
 */
export const countMessages = defineMessages({
  he: {
    item_one: "פריט",
    item_two: "פריטים",
    item_few: "פריטים",
    item_many: "פריטים",
    items_one: "פריטים",
    items_two: "פריטים",
    items_few: "פריטים",
    items_many: "פריטים",
    replaced_one: "פריט הוחלף",
    replaced_two: "פריטים הוחלפו",
    replaced_few: "פריטים הוחלפו",
    replaced_many: "פריטים הוחלפו",
    missing_one: "פריט חסר",
    missing_two: "פריטים חסרים",
    missing_few: "פריטים חסרים",
    missing_many: "פריטים חסרים",
    promo_one: "מבצע כלול",
    promo_two: "מבצעים כלולים",
    promo_few: "מבצעים כלולים",
    promo_many: "מבצעים כלולים",
    unit_one: "יחידה",
    unit_two: "יחידות",
    unit_few: "יחידות",
    unit_many: "יחידות",
  },
  // Machine-drafted; needs native-speaker review (#73).
  ar: {
    item_one: "صنف",
    item_two: "صنفان",
    item_few: "أصناف",
    item_many: "صنفًا",
    items_one: "صنف",
    items_two: "صنفان",
    items_few: "أصناف",
    items_many: "صنفًا",
    replaced_one: "صنف مستبدل",
    replaced_two: "صنفان مستبدلان",
    replaced_few: "أصناف مستبدلة",
    replaced_many: "صنفًا مستبدلًا",
    missing_one: "صنف مفقود",
    missing_two: "صنفان مفقودان",
    missing_few: "أصناف مفقودة",
    missing_many: "صنفًا مفقودًا",
    promo_one: "عرض مشمول",
    promo_two: "عرضان مشمولان",
    promo_few: "عروض مشمولة",
    promo_many: "عرضًا مشمولًا",
    unit_one: "وحدة",
    unit_two: "وحدتان",
    unit_few: "وحدات",
    unit_many: "وحدة",
  },
});

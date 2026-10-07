import type { FlexLevel } from "@/api/client";
import { SMART_DEFAULTS, lookupDefault } from "@/state/flex";
import type { KosherLevel } from "./profileState";

export const KOSHER_OPTIONS: ReadonlyArray<{ value: KosherLevel | "none"; label: string }> = [
  { value: "none", label: "ללא העדפה" },
  { value: "regular", label: "כשר" },
  { value: "mehadrin", label: "מהדרין" },
  { value: "badatz", label: 'בד"צ' },
];

export const ALLERGENS: ReadonlyArray<{ key: string; label: string }> = [
  { key: "peanuts", label: "בוטנים" },
  { key: "tree_nuts", label: "אגוזים" },
  { key: "sesame", label: "שומשום" },
  { key: "milk", label: "חלב" },
  { key: "eggs", label: "ביצים" },
  { key: "soy", label: "סויה" },
  { key: "wheat", label: "חיטה" },
  { key: "fish", label: "דגים" },
];

/** The 19 taxonomy departments (data/taxonomy.yaml) with their Hebrew names. */
export const DEPARTMENTS: ReadonlyArray<{ id: string; label: string }> = [
  { id: "dairy", label: "מוצרי חלב וביצים" },
  { id: "meat", label: "בשר ועוף" },
  { id: "fish", label: "דגים" },
  { id: "deli", label: "מעדנייה וסלטים" },
  { id: "produce", label: "פירות וירקות" },
  { id: "bakery", label: "לחם ומאפים" },
  { id: "pantry", label: "מזון יבש ובישול" },
  { id: "canned", label: "שימורים" },
  { id: "frozen", label: "קפואים" },
  { id: "beverages", label: "משקאות" },
  { id: "snacks", label: "חטיפים ומתוקים" },
  { id: "baby", label: "תינוקות" },
  { id: "cleaning", label: "ניקיון ומוצרים לבית" },
  { id: "paper", label: "נייר וחד-פעמי" },
  { id: "toiletries", label: "טיפוח והיגיינה" },
  { id: "health", label: "בריאות ופארם" },
  { id: "pets", label: "חיות מחמד" },
  { id: "holiday", label: "כשר לפסח ומוצרי חג" },
  { id: "alcohol", label: "יין ואלכוהול" },
];

/** Smart default (D4) for a category: the shared table in `@/state/flex`, else "any brand". */
export function smartDefault(taxonomyId: string): FlexLevel {
  return lookupDefault(taxonomyId, SMART_DEFAULTS) ?? "any_brand";
}

/** Hebrew label for a taxonomy node id, falling back to the department or the raw id. */
export function categoryLabel(taxonomyId: string): string {
  const dept = DEPARTMENTS.find((d) => d.id === taxonomyId);
  if (dept) return dept.label;
  const KNOWN: Record<string, string> = {
    "dairy.milk": "חלב ומשקאות חלב",
    "dairy.cheese": "גבינות",
    "dairy.yogurt": "יוגורט ומעדנים",
    "dairy.cream": "שמנת וחמאה",
    "dairy.eggs": "ביצים",
  };
  return KNOWN[taxonomyId] ?? taxonomyId;
}

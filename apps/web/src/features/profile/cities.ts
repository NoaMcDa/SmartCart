/**
 * Manual location fallback: a city centre is a neighborhood-level point by construction. The
 * coordinates are approximate city centres (estimates for centring a search radius, not survey
 * data), already at 3 decimals. The neighborhood the user types is kept as text only.
 */
export type City = { name: string; lat: number; lon: number };

export const CITIES: ReadonlyArray<City> = [
  { name: "תל אביב-יפו", lat: 32.085, lon: 34.782 },
  { name: "ירושלים", lat: 31.768, lon: 35.214 },
  { name: "חיפה", lat: 32.794, lon: 34.99 },
  { name: "ראשון לציון", lat: 31.973, lon: 34.793 },
  { name: "פתח תקווה", lat: 32.084, lon: 34.888 },
  { name: "נתניה", lat: 32.322, lon: 34.853 },
  { name: "באר שבע", lat: 31.253, lon: 34.792 },
  { name: "אשדוד", lat: 31.804, lon: 34.655 },
  { name: "מודיעין-מכבים-רעות", lat: 31.897, lon: 35.01 },
  { name: "רחובות", lat: 31.893, lon: 34.811 },
  { name: "בני ברק", lat: 32.081, lon: 34.834 },
  { name: "חולון", lat: 32.016, lon: 34.787 },
  { name: "רמת גן", lat: 32.068, lon: 34.825 },
  { name: "הרצליה", lat: 32.166, lon: 34.844 },
  { name: "כפר סבא", lat: 32.175, lon: 34.907 },
  { name: "רעננה", lat: 32.185, lon: 34.871 },
  { name: "הוד השרון", lat: 32.15, lon: 34.889 },
  { name: "רמת השרון", lat: 32.146, lon: 34.839 },
  { name: "חדרה", lat: 32.434, lon: 34.92 },
  { name: "אשקלון", lat: 31.669, lon: 34.574 },
  { name: "בית שמש", lat: 31.747, lon: 34.988 },
  { name: "לוד", lat: 31.952, lon: 34.896 },
  { name: "רמלה", lat: 31.929, lon: 34.867 },
  { name: "נס ציונה", lat: 31.929, lon: 34.799 },
  { name: "כרמיאל", lat: 32.919, lon: 35.29 },
  { name: "עכו", lat: 32.928, lon: 35.082 },
  { name: "נהריה", lat: 33.005, lon: 35.098 },
  { name: "טבריה", lat: 32.794, lon: 35.53 },
  { name: "אילת", lat: 29.558, lon: 34.952 },
];

const normalize = (s: string) => s.replace(/[\s"'׳״-]+/g, "").toLowerCase();

/** Exact or prefix match on the typed city; "מודיעין" finds "מודיעין-מכבים-רעות". */
export function findCity(input: string): City | undefined {
  const needle = normalize(input);
  if (needle.length < 2) return undefined;
  return (
    CITIES.find((c) => normalize(c.name) === needle) ??
    CITIES.find((c) => normalize(c.name).startsWith(needle))
  );
}

import { DEFAULT_LOCALE, type Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { profileMessages, type ProfileMessageKey } from "@/i18n/messages/profile";

/**
 * Manual location fallback: a city centre is a neighborhood-level point by construction. The
 * coordinates are approximate city centres (estimates for centring a search radius, not survey
 * data), already at 3 decimals. The neighborhood the user types is kept as text only.
 */
export type City = {
  /** Slug; the display names are the `city_<id>` messages. */
  id: string;
  /** Hebrew name: what is stored in the profile, whatever the UI language. */
  name: string;
  lat: number;
  lon: number;
};

export const CITIES: ReadonlyArray<City> = [
  { id: "tel_aviv", name: "תל אביב-יפו", lat: 32.085, lon: 34.782 },
  { id: "jerusalem", name: "ירושלים", lat: 31.768, lon: 35.214 },
  { id: "haifa", name: "חיפה", lat: 32.794, lon: 34.99 },
  { id: "rishon", name: "ראשון לציון", lat: 31.973, lon: 34.793 },
  { id: "petah_tikva", name: "פתח תקווה", lat: 32.084, lon: 34.888 },
  { id: "netanya", name: "נתניה", lat: 32.322, lon: 34.853 },
  { id: "beer_sheva", name: "באר שבע", lat: 31.253, lon: 34.792 },
  { id: "ashdod", name: "אשדוד", lat: 31.804, lon: 34.655 },
  { id: "modiin", name: "מודיעין-מכבים-רעות", lat: 31.897, lon: 35.01 },
  { id: "rehovot", name: "רחובות", lat: 31.893, lon: 34.811 },
  { id: "bnei_brak", name: "בני ברק", lat: 32.081, lon: 34.834 },
  { id: "holon", name: "חולון", lat: 32.016, lon: 34.787 },
  { id: "ramat_gan", name: "רמת גן", lat: 32.068, lon: 34.825 },
  { id: "herzliya", name: "הרצליה", lat: 32.166, lon: 34.844 },
  { id: "kfar_saba", name: "כפר סבא", lat: 32.175, lon: 34.907 },
  { id: "raanana", name: "רעננה", lat: 32.185, lon: 34.871 },
  { id: "hod_hasharon", name: "הוד השרון", lat: 32.15, lon: 34.889 },
  { id: "ramat_hasharon", name: "רמת השרון", lat: 32.146, lon: 34.839 },
  { id: "hadera", name: "חדרה", lat: 32.434, lon: 34.92 },
  { id: "ashkelon", name: "אשקלון", lat: 31.669, lon: 34.574 },
  { id: "beit_shemesh", name: "בית שמש", lat: 31.747, lon: 34.988 },
  { id: "lod", name: "לוד", lat: 31.952, lon: 34.896 },
  { id: "ramla", name: "רמלה", lat: 31.929, lon: 34.867 },
  { id: "ness_ziona", name: "נס ציונה", lat: 31.929, lon: 34.799 },
  { id: "karmiel", name: "כרמיאל", lat: 32.919, lon: 35.29 },
  { id: "acre", name: "עכו", lat: 32.928, lon: 35.082 },
  { id: "nahariya", name: "נהריה", lat: 33.005, lon: 35.098 },
  { id: "tiberias", name: "טבריה", lat: 32.794, lon: 35.53 },
  { id: "eilat", name: "אילת", lat: 29.558, lon: 34.952 },
];

/** The city name to show: Hebrew from the table, Arabic with `locale: "ar"`. */
export function cityName(city: City, locale: Locale = DEFAULT_LOCALE): string {
  if (locale === DEFAULT_LOCALE) return city.name;
  return translate(profileMessages, locale, `city_${city.id}` as ProfileMessageKey);
}

/** A stored city (Hebrew) in the UI language; a name that is not in the table is returned as is. */
export function cityLabelFor(label: string, locale: Locale = DEFAULT_LOCALE): string {
  const city = CITIES.find((c) => c.name === label);
  return city ? cityName(city, locale) : label;
}

/** Spaces, quotes, geresh and hyphens drop out; so do Arabic diacritics and tatweel. */
const normalize = (s: string) =>
  s
    .replace(/[\s"'׳״-]+/g, "")
    .replace(/[ً-ٟـ]/g, "")
    .toLowerCase();

/**
 * Exact or prefix match on the typed city, in Hebrew or in Arabic: "מודיעין" finds
 * "מודיעין-מכבים-רעות" and "موديعين" finds "موديعين-مكابيم-رعوت". Returns the table entry, whose
 * Hebrew `name` is what the profile stores.
 */
export function findCity(input: string): City | undefined {
  const needle = normalize(input);
  if (needle.length < 2) return undefined;
  const names = (c: City) => [normalize(c.name), normalize(cityName(c, "ar"))];
  return (
    CITIES.find((c) => names(c).includes(needle)) ??
    CITIES.find((c) => names(c).some((n) => n.startsWith(needle)))
  );
}

"use client";

import { useId, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Tag } from "@/components/ui/Tag";
import { IconPin } from "@/components/ui/icons";
import { CITIES, findCity } from "../cities";
import {
  RADIUS_MAX_KM,
  RADIUS_MIN_KM,
  clearLocation,
  setLocation,
  updateProfile,
  useProfile,
} from "../profileState";
import { RangeField } from "./RangeField";
import styles from "./controls.module.css";

type GeoState = "idle" | "asking" | "denied" | "unavailable";

/**
 * Location and radius, shared by onboarding step 1 and Profile ("same controls as onboarding").
 * The device location is requested only on an explicit click, after the explanation the caller
 * shows above. Declining or failing falls back to a city and neighborhood. Whatever is stored is
 * rounded to 3 decimals by `setLocation` (D11).
 */
export function LocationControls() {
  const profile = useProfile();
  const [geo, setGeo] = useState<GeoState>("idle");
  const [manualOpen, setManualOpen] = useState(false);
  const [city, setCity] = useState(profile.location?.city ?? "");
  const [neighborhood, setNeighborhood] = useState(profile.location?.neighborhood ?? "");
  const [cityError, setCityError] = useState(false);
  const listId = useId();
  const cityId = useId();
  const hoodId = useId();

  function askDevice() {
    if (typeof navigator === "undefined" || !("geolocation" in navigator)) {
      setGeo("unavailable");
      setManualOpen(true);
      return;
    }
    setGeo("asking");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          source: "device",
        });
        setGeo("idle");
      },
      () => {
        setGeo("denied");
        setManualOpen(true);
      },
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 600_000 },
    );
  }

  function saveManual() {
    const match = findCity(city);
    if (!match) {
      setCityError(true);
      return;
    }
    setCityError(false);
    setLocation({
      lat: match.lat,
      lon: match.lon,
      city: match.name,
      neighborhood: neighborhood.trim() || null,
      source: "manual",
    });
    setCity(match.name);
  }

  const loc = profile.location;
  const showManual = manualOpen || geo === "denied" || geo === "unavailable";

  return (
    <div className={styles.stack}>
      <div className={styles.group}>
        <p className={styles.legend}>המיקום שלי</p>
        {loc ? (
          <div className={styles.statusRow} data-testid="location-summary">
            <Tag variant="matched">
              {loc.city
                ? [loc.city, loc.neighborhood].filter(Boolean).join(", ")
                : loc.source === "device"
                  ? "מיקום המכשיר, מעוגל לשכונה"
                  : "מיקום שמור, מעוגל לשכונה"}
            </Tag>
            <Button size="sm" variant="ghost" onClick={() => clearLocation()}>
              הסרת המיקום
            </Button>
          </div>
        ) : (
          <p className={styles.status}>עוד לא הגדרת מיקום.</p>
        )}
        <div className={styles.row}>
          <Button
            variant="outline"
            iconStart={<IconPin size={18} />}
            onClick={askDevice}
            disabled={geo === "asking"}
          >
            {geo === "asking" ? "מבקשת מיקום…" : "אישור שימוש במיקום המכשיר"}
          </Button>
          {!showManual ? (
            <Button variant="ghost" onClick={() => setManualOpen(true)}>
              להזין עיר ושכונה במקום
            </Button>
          ) : null}
        </div>
        {geo === "denied" ? (
          <p className={styles.error} role="status">
            לא קיבלנו הרשאת מיקום, וזה בסדר. אפשר להזין עיר ושכונה ולהמשיך.
          </p>
        ) : null}
        {geo === "unavailable" ? (
          <p className={styles.error} role="status">
            המכשיר לא מספק מיקום. אפשר להזין עיר ושכונה ולהמשיך.
          </p>
        ) : null}
      </div>

      {showManual ? (
        <div className={styles.group} data-testid="manual-location">
          <div className={styles.row}>
            <div className={styles.field}>
              <label htmlFor={cityId} className={styles.label}>
                עיר
              </label>
              <input
                id={cityId}
                className={styles.input}
                list={listId}
                value={city}
                autoComplete="off"
                aria-invalid={cityError || undefined}
                aria-describedby={cityError ? `${cityId}-err` : undefined}
                onChange={(e) => {
                  setCity(e.target.value);
                  setCityError(false);
                }}
              />
              <datalist id={listId}>
                {CITIES.map((c) => (
                  <option key={c.name} value={c.name} />
                ))}
              </datalist>
            </div>
            <div className={styles.field}>
              <label htmlFor={hoodId} className={styles.label}>
                שכונה (לא חובה)
              </label>
              <input
                id={hoodId}
                className={styles.input}
                value={neighborhood}
                autoComplete="off"
                onChange={(e) => setNeighborhood(e.target.value)}
              />
            </div>
          </div>
          {cityError ? (
            <p id={`${cityId}-err`} className={styles.error} role="alert">
              לא מצאנו את העיר ברשימה. בחרי עיר מההצעות.
            </p>
          ) : null}
          <div>
            <Button size="sm" variant="secondary" onClick={saveManual}>
              שמירת העיר
            </Button>
          </div>
        </div>
      ) : null}

      <RangeField
        label="רדיוס חיפוש"
        min={RADIUS_MIN_KM}
        max={RADIUS_MAX_KM}
        value={profile.radiusKm}
        onChange={(radiusKm) => updateProfile({ radiusKm })}
        display={
          <>
            <span dir="ltr">{profile.radiusKm}</span> ק&quot;מ
          </>
        }
        valueText={`${profile.radiusKm} קילומטרים`}
        minLabel={
          <>
            <span dir="ltr">{RADIUS_MIN_KM}</span> ק&quot;מ
          </>
        }
        maxLabel={
          <>
            <span dir="ltr">{RADIUS_MAX_KM}</span> ק&quot;מ
          </>
        }
      />
    </div>
  );
}

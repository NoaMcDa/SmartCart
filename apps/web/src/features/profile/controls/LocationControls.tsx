"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Tag } from "@/components/ui/Tag";
import { IconPin } from "@/components/ui/icons";
import { formatRich } from "@/i18n/format";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { profileMessages } from "@/i18n/messages/profile";
import { CITIES, cityLabelFor, cityName, findCity } from "../cities";
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
  const t = useT(profileMessages);
  const { locale } = useLocale();
  const profile = useProfile();
  const [geo, setGeo] = useState<GeoState>("idle");
  const [manualOpen, setManualOpen] = useState(false);
  const [city, setCity] = useState(cityLabelFor(profile.location?.city ?? "", locale));
  const [neighborhood, setNeighborhood] = useState(profile.location?.neighborhood ?? "");
  const [cityError, setCityError] = useState(false);
  const listId = useId();
  const cityId = useId();
  const hoodId = useId();
  // The device-location request that may still store a location. Leaving the step (skip, back,
  // navigation) or removing the location starts a new number: a position that arrives after that
  // is dropped, so it never saves a location (and the consent that goes with it) the person has
  // moved on from.
  const askRun = useRef(0);
  useEffect(
    () => () => {
      askRun.current += 1;
    },
    [],
  );

  function askDevice() {
    if (typeof navigator === "undefined" || !("geolocation" in navigator)) {
      setGeo("unavailable");
      setManualOpen(true);
      return;
    }
    setGeo("asking");
    const mine = (askRun.current += 1);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        if (mine !== askRun.current) return;
        setLocation({
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          source: "device",
        });
        setGeo("idle");
      },
      () => {
        if (mine !== askRun.current) return;
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
    setCity(cityName(match, locale));
  }

  const loc = profile.location;
  const showManual = manualOpen || geo === "denied" || geo === "unavailable";

  return (
    <div className={styles.stack}>
      <div className={styles.group}>
        <p className={styles.legend}>{t("myLocation")}</p>
        {loc ? (
          <div className={styles.statusRow} data-testid="location-summary">
            <Tag variant="matched">
              {loc.city
                ? [cityLabelFor(loc.city, locale), loc.neighborhood].filter(Boolean).join(", ")
                : loc.source === "device"
                  ? t("locationDevice")
                  : t("locationSaved")}
            </Tag>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                askRun.current += 1;
                setGeo("idle");
                clearLocation();
              }}
            >
              {t("removeLocation")}
            </Button>
          </div>
        ) : (
          <p className={styles.status}>{t("noLocation")}</p>
        )}
        <div className={styles.row}>
          <Button
            variant="outline"
            iconStart={<IconPin size={18} />}
            onClick={askDevice}
            disabled={geo === "asking"}
          >
            {geo === "asking" ? t("asking") : t("askDevice")}
          </Button>
          {!showManual ? (
            <Button variant="ghost" onClick={() => setManualOpen(true)}>
              {t("enterManual")}
            </Button>
          ) : null}
        </div>
        {geo === "denied" ? (
          <p className={styles.error} role="status">
            {t("geoDenied")}
          </p>
        ) : null}
        {geo === "unavailable" ? (
          <p className={styles.error} role="status">
            {t("geoUnavailable")}
          </p>
        ) : null}
      </div>

      {showManual ? (
        <div className={styles.group} data-testid="manual-location">
          <div className={styles.row}>
            <div className={styles.field}>
              <label htmlFor={cityId} className={styles.label}>
                {t("city")}
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
                  <option key={c.id} value={cityName(c, locale)} />
                ))}
              </datalist>
            </div>
            <div className={styles.field}>
              <label htmlFor={hoodId} className={styles.label}>
                {t("neighborhood")}
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
              {t("cityNotFound")}
            </p>
          ) : null}
          <div>
            <Button size="sm" variant="secondary" onClick={saveManual}>
              {t("saveCity")}
            </Button>
          </div>
        </div>
      ) : null}

      <RangeField
        label={t("radius")}
        min={RADIUS_MIN_KM}
        max={RADIUS_MAX_KM}
        value={profile.radiusKm}
        onChange={(radiusKm) => updateProfile({ radiusKm })}
        display={<>{formatRich(t("radiusKm"), { n: <span dir="ltr">{profile.radiusKm}</span> })}</>}
        valueText={t("radiusSpoken", { n: profile.radiusKm })}
        minLabel={<>{formatRich(t("radiusKm"), { n: <span dir="ltr">{RADIUS_MIN_KM}</span> })}</>}
        maxLabel={<>{formatRich(t("radiusKm"), { n: <span dir="ltr">{RADIUS_MAX_KM}</span> })}</>}
      />
    </div>
  );
}

"use client";

import type { CSSProperties } from "react";
import { useT } from "@/i18n/LocaleProvider";
import { mapMessages } from "@/i18n/messages/map";
import { PinButton, type Pin } from "./PinButton";
import type { LatLon } from "./geo";
import styles from "./Map.module.css";

type Props = {
  center: LatLon;
  radiusM: number;
  pins: ReadonlyArray<Pin & { position: LatLon }>;
  selectedId: number | null;
  onSelect: (storeId: number) => void;
};

/**
 * Shown when WebGL is unavailable: a schematic plan on the map background token, the user's
 * location at the centre and each store's basket pill at its distance and bearing. East is to the
 * physical right (the container is laid out with container-query units, not left/right).
 */
export function FallbackMap({ center, radiusM, pins, selectedId, onSelect }: Props) {
  const t = useT(mapMessages);
  const metersEast = (p: LatLon) =>
    (p.lon - center.lon) * Math.cos((center.lat * Math.PI) / 180) * 111_320;
  const metersNorth = (p: LatLon) => (p.lat - center.lat) * 110_540;
  const extent =
    Math.max(
      radiusM,
      ...pins.map((p) => Math.hypot(metersEast(p.position), metersNorth(p.position))),
    ) * 1.1;
  return (
    <div
      className={styles.fallback}
      data-testid="map-fallback"
      role="group"
      aria-label={t("fallbackLabel")}
    >
      <span
        className={styles.fbRing}
        style={{ "--rr": `${(radiusM / extent) * 42}` } as CSSProperties}
        aria-hidden="true"
      />
      <span className={styles.fbUser} role="img" aria-label={t("myLocation")} />
      {pins.map((pin) => (
        <span
          key={pin.storeId}
          className={styles.fbPin}
          style={
            {
              "--dx": `${(metersEast(pin.position) / extent) * 42}`,
              "--dy": `${(-metersNorth(pin.position) / extent) * 30}`,
            } as CSSProperties
          }
        >
          <PinButton pin={pin} selected={selectedId === pin.storeId} onSelect={onSelect} />
        </span>
      ))}
    </div>
  );
}

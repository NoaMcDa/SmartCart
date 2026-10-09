"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import {
  AttributionControl,
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  type StyleSpecification,
} from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useT } from "@/i18n/LocaleProvider";
import { mapMessages } from "@/i18n/messages/map";
import { APPROX_AREA_M, circleRing, type LatLon } from "./geo";
import { PinButton, type Pin } from "./PinButton";
import styles from "./Map.module.css";

export type MapCanvasProps = {
  center: LatLon;
  radiusM: number;
  pins: ReadonlyArray<Pin & { position: LatLon }>;
  selectedId: number | null;
  onSelect: (storeId: number) => void;
  /** Called once when the map cannot start (no WebGL), so the screen can show its fallback. */
  onUnsupported: () => void;
};

/**
 * OpenStreetMap raster tiles through MapLibre GL, no API key. The style is inline, so nothing but
 * the tile requests leaves the page. Pins are real DOM markers (buttons) rendered from React
 * through portals, so they are keyboard and screen-reader reachable and carry the basket price.
 * Loaded only through next/dynamic (see MapScreen), never during SSR and not in other bundles.
 * Attribution is the MapLibre control (bottom, visible), as OSM's tile policy requires.
 */
const STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution:
        '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

function webglAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

const token = (name: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#1f5f8b";

/** Adds the radius circle, or moves it when it already exists. Safe to call before and after load. */
function setRadius(map: MapLibreMap, center: LatLon, radiusM: number) {
  const data = {
    type: "Feature" as const,
    properties: {},
    geometry: { type: "Polygon" as const, coordinates: [circleRing(center, radiusM)] },
  };
  const existing = map.getSource("radius");
  if (existing && "setData" in existing) {
    (existing as unknown as { setData: (d: typeof data) => void }).setData(data);
    return;
  }
  map.addSource("radius", { type: "geojson", data });
  map.addLayer({
    id: "radius-fill",
    type: "fill",
    source: "radius",
    paint: { "fill-color": token("--sc-accent-fg"), "fill-opacity": 0.08 },
  });
  map.addLayer({
    id: "radius-line",
    type: "line",
    source: "radius",
    paint: { "line-color": token("--sc-accent-fg"), "line-width": 2, "line-dasharray": [2, 2] },
  });
}

/**
 * Draws (or updates) the dashed areas around the stores that are only placed at their town
 * centre. Safe to call before and after load; an empty list clears them.
 */
function setApproxAreas(map: MapLibreMap, areas: ReadonlyArray<LatLon>) {
  const data = {
    type: "FeatureCollection" as const,
    features: areas.map((c) => ({
      type: "Feature" as const,
      properties: {},
      geometry: { type: "Polygon" as const, coordinates: [circleRing(c, APPROX_AREA_M)] },
    })),
  };
  const existing = map.getSource("approx-areas");
  if (existing && "setData" in existing) {
    (existing as unknown as { setData: (d: typeof data) => void }).setData(data);
    return;
  }
  map.addSource("approx-areas", { type: "geojson", data });
  map.addLayer({
    id: "approx-areas-fill",
    type: "fill",
    source: "approx-areas",
    paint: { "fill-color": token("--sc-muted"), "fill-opacity": 0.12 },
  });
  map.addLayer({
    id: "approx-areas-line",
    type: "line",
    source: "approx-areas",
    paint: { "line-color": token("--sc-muted"), "line-width": 2, "line-dasharray": [1, 2] },
  });
}

export default function MapCanvas({
  center,
  radiusM,
  pins,
  selectedId,
  onSelect,
  onUnsupported,
}: MapCanvasProps) {
  const myLocation = useT(mapMessages)("myLocation");
  const container = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<MapLibreMap | null>(null);

  // One host element per pin: plain DOM nodes that MapLibre positions as markers and React fills
  // with the pin button through a portal. Created in render because the component only ever runs
  // in the browser (it is loaded with ssr: false).
  const hosts = useMemo(
    () => new Map(pins.map((p) => [p.storeId, document.createElement("div")])),
    [pins],
  );

  // Create the map once; it becomes visible to the other effects on the next frame.
  useEffect(() => {
    const el = container.current;
    if (!el) return;
    if (!webglAvailable()) {
      onUnsupported();
      return;
    }
    let created: MapLibreMap;
    try {
      created = new MapLibreMap({
        container: el,
        style: STYLE,
        center: [center.lon, center.lat],
        zoom: 12,
        attributionControl: false,
        dragRotate: false,
      });
    } catch {
      onUnsupported();
      return;
    }
    created.touchZoomRotate.disableRotation();
    // The page is RTL: controls sit at the inline-start (right) side, attribution at the end.
    created.addControl(new NavigationControl({ showCompass: false }), "top-right");
    created.addControl(new AttributionControl({ compact: false }), "bottom-left");
    const frame = requestAnimationFrame(() => setMap(created));
    return () => {
      cancelAnimationFrame(frame);
      created.remove();
    };
    // The map is created once; props are synced by the effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The user's location marker and the radius circle.
  useEffect(() => {
    if (!map) return;
    const dot = document.createElement("div");
    dot.className = styles.userDot ?? "";
    dot.setAttribute("role", "img");
    dot.setAttribute("aria-label", myLocation);
    const marker = new Marker({ element: dot }).setLngLat([center.lon, center.lat]).addTo(map);
    const apply = () => setRadius(map, center, radiusM);
    try {
      apply();
    } catch {
      // The style is still loading: draw the circle as soon as it is ready.
      map.once("style.load", apply);
    }
    return () => {
      marker.remove();
      map.off("style.load", apply);
    };
  }, [map, center, radiusM, myLocation]);

  // The dashed areas of the stores that are only placed at their town centre.
  useEffect(() => {
    if (!map) return;
    const areas = pins.filter((p) => p.approximate).map((p) => p.position);
    const apply = () => setApproxAreas(map, areas);
    try {
      apply();
    } catch {
      map.once("style.load", apply);
    }
    return () => {
      map.off("style.load", apply);
    };
  }, [map, pins]);

  // One marker per pin.
  useEffect(() => {
    if (!map) return;
    const markers = pins.flatMap((pin) => {
      const element = hosts.get(pin.storeId);
      return element
        ? [
            new Marker({ element, anchor: pin.approximate ? "center" : "bottom" })
              .setLngLat([pin.position.lon, pin.position.lat])
              .addTo(map),
          ]
        : [];
    });
    return () => {
      for (const m of markers) m.remove();
    };
  }, [map, pins, hosts]);

  // Fit the view to the radius and the pins whenever they change.
  useEffect(() => {
    if (!map) return;
    const points: [number, number][] = [
      ...circleRing(center, radiusM, 8),
      ...pins.map((p) => [p.position.lon, p.position.lat] as [number, number]),
      ...pins.filter((p) => p.approximate).flatMap((p) => circleRing(p.position, APPROX_AREA_M, 8)),
    ];
    const lons = points.map((p) => p[0]);
    const lats = points.map((p) => p[1]);
    map.fitBounds(
      [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ],
      { padding: 56, maxZoom: 15, animate: false },
    );
  }, [map, center, radiusM, pins]);

  return (
    <div className={styles.canvas}>
      <div ref={container} className={styles.map} data-testid="map-canvas" />
      {pins.map((pin) => {
        const host = hosts.get(pin.storeId);
        return host
          ? createPortal(
              <PinButton pin={pin} selected={selectedId === pin.storeId} onSelect={onSelect} />,
              host,
              String(pin.storeId),
            )
          : null;
      })}
    </div>
  );
}

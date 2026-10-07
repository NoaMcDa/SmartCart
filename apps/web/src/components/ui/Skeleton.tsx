import type { CSSProperties } from "react";
import styles from "./Skeleton.module.css";

export type SkeletonProps = {
  width?: CSSProperties["width"];
  height?: CSSProperties["height"];
  radius?: CSSProperties["borderRadius"];
  className?: string;
};

/** Loading placeholder. Decorative: pair it with an aria-busy container or a status message. */
export function Skeleton({ width = "100%", height = 16, radius = 8, className }: SkeletonProps) {
  return (
    <span
      aria-hidden="true"
      className={[styles.skeleton, className].filter(Boolean).join(" ")}
      style={{ inlineSize: width, blockSize: height, borderRadius: radius }}
    />
  );
}

/** A stack of text lines; the last one is shorter. */
export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <span className={styles.stack} aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} width={i === lines - 1 ? "60%" : "100%"} height={12} />
      ))}
    </span>
  );
}

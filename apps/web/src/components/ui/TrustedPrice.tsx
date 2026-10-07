import { Price, type PriceProps } from "./Price";
import { UpdatedAt } from "./UpdatedAt";
import styles from "./TrustedPrice.module.css";

export type TrustedPriceProps = PriceProps & {
  /** Required: no price renders without its update time (D10, issue #12). */
  updatedAt: string;
  /** Show the time on its own line under the price (default) or inline after it. */
  layout?: "stacked" | "inline";
};

/**
 * A shelf or line price with its update time. Use it wherever a single price is shown; totals
 * that combine many prices show one UpdatedAt for the card instead.
 */
export function TrustedPrice({ updatedAt, layout = "stacked", ...price }: TrustedPriceProps) {
  return (
    <span className={[styles.wrap, styles[layout]].join(" ")} data-trust-scope="price">
      <Price {...price} />
      <UpdatedAt iso={updatedAt} />
    </span>
  );
}

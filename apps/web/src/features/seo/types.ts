/** Shapes of the generated files in `public/seo` (written by `smartcart-catalog export-seo`). */

export type BaseUnit = "100g" | "100ml" | "unit" | "kg";

export type Category = {
  slug: string;
  id: string;
  level: 1 | 2;
  parent_slug: string | null;
  name_he: string;
  name_en: string | null;
  canonical_count: number;
  has_page: boolean;
  path: { slug: string; name_he: string }[];
};

export type CategoriesFile = {
  generated_at: string;
  count: number;
  page_count: number;
  categories: Category[];
};

export type ChainPrice = {
  chain_id: string;
  chain_name: string;
  min_unit_price: number;
  median_unit_price: number;
  stores: number;
  is_estimated: boolean;
  price_valid_from: string;
};

export type Product = {
  slug: string;
  name_he: string;
  taxonomy_id: string;
  /** Levels 1 to 4; only levels 1 and 2 have a category page (`slug` is null below that). */
  path: { id: string; name_he: string; slug: string | null }[];
  product_type: string;
  base_unit: BaseUnit;
  critical_attrs: Record<string, string | number>;
  rank: number | null;
  has_page: boolean;
  no_prices_yet: boolean;
  prices: ChainPrice[] | null;
  price_valid_from: string | null;
};

export type ProductsFile = {
  generated_at: string;
  count: number;
  page_count: number;
  priced_count: number;
  products: Product[];
};

export type FlexLevelKey = "exact" | "any_brand" | "close";

export type Quality =
  | { generated_at: string; available: false }
  | {
      generated_at: string;
      available: true;
      run_id: number;
      measured_at: string;
      precision: Partial<Record<FlexLevelKey, number>>;
      sample: Partial<Record<FlexLevelKey, number>>;
      gold_items: number;
      gold_pairs: number;
      synthetic: boolean;
      judge: string | null;
      target_any_brand: number;
    };

export type BasketItem = {
  slug: string;
  name_he: string;
  amount: number;
  base_unit: BaseUnit;
  label_he: string;
};

export type BasketChainRow = {
  chain_id: string;
  name: string;
  total: number | null;
  delta_vs_cheapest: number | null;
  delta_pct: number | null;
  items_priced: number;
  estimated_items: number;
  stores: number;
  complete: boolean;
  missing: string[];
};

export type BasketMonth = {
  month: string;
  basket_version: number;
  computed_at: string;
  price_date: string | null;
  cheapest_chain_id: string | null;
  spread_pct: number | null;
  chains: BasketChainRow[];
  status: "draft" | "published";
  reviewed_by: string | null;
};

export type BasketIndexFile = {
  generated_at: string;
  basket: { version: number; item_count: number; items: BasketItem[] };
  months: BasketMonth[];
};

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ProductDetail } from "@/features/product/ProductDetail";

export const metadata: Metadata = { title: "פרטי מוצר" };

/**
 * `/product/<canonical id>?name=<Hebrew canonical name>`. Screens that link here pass the name
 * (the price lines only carry chain item names). Without it the page falls back to the cheapest
 * variant's name, then to the generic title.
 */
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ name?: string | string[] }>;
}) {
  const { id } = await params;
  const { name } = await searchParams;
  const canonicalId = Number(id);
  if (!Number.isInteger(canonicalId) || canonicalId <= 0) notFound();
  const hint = (Array.isArray(name) ? name[0] : name)?.trim().slice(0, 200) || null;
  return <ProductDetail canonicalId={canonicalId} nameHint={hint} />;
}

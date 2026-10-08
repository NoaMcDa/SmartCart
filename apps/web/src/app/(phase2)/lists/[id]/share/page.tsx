import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SharedListScreen } from "@/features/share/SharedListScreen";
import pageStyles from "../../../phase2.module.css";
import { PageTitle } from "../../../PageTitle";

export const metadata: Metadata = { title: "שיתוף הרשימה" };

/**
 * `/lists/<server list id>/share`, or `/lists/mine/share` to share the list on this device (the
 * first visit creates the shared copy and redirects to its id).
 */
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const listId = id === "mine" ? "mine" : Number(id);
  if (listId !== "mine" && (!Number.isInteger(listId) || listId <= 0)) notFound();
  return (
    <div className={pageStyles.page}>
      <PageTitle id="share" />
      <SharedListScreen listId={listId} />
    </div>
  );
}

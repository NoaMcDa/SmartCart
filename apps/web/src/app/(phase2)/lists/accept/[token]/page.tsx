import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { AcceptInvite } from "@/features/share/AcceptInvite";
import pageStyles from "../../../phase2.module.css";

export const metadata: Metadata = {
  title: "הצטרפות לרשימה משותפת",
  // An invite link is private: keep it out of search results and referrers.
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default async function Page({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  if (!/^[A-Za-z0-9._~-]{4,200}$/.test(token)) notFound();
  return (
    <div className={pageStyles.page}>
      <h1 className={pageStyles.title}>הצטרפות לרשימה משותפת</h1>
      <AcceptInvite token={token} />
    </div>
  );
}

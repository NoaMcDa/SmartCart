"use client";

import { useRef, useState } from "react";
import type { PricedItem, StoreRef } from "@/api/client";
import { BottomSheet, Button } from "@/components/ui";
import { IconCart, IconCheck, IconInfo } from "@/components/ui/icons";
import { trackEvent } from "@/features/seo/track";
import { useT } from "@/i18n/LocaleProvider";
import { handoffMessages } from "@/i18n/messages/handoff";
import styles from "./Handoff.module.css";
import {
  enabledChain,
  handoffItems,
  httpsUrl,
  listText,
  searchUrl,
  type HandoffItem,
} from "./links";
import { useChainsOnline } from "./useChainsOnline";

export type HandoffActionProps = {
  /** The store card this sits on; only its chain is used. */
  store: Pick<StoreRef, "store_id" | "chain_id" | "chain_name">;
  /** The items bought at this store in the plan being shown. */
  items: readonly Pick<PricedItem, "display_name_he" | "quantity">[];
};

/**
 * "Continue on the chain's site" (issue #72). Shown on a store card only when that store's chain is
 * switched on (`GET /chains/online`, flag CART_HANDOFF_CHAINS) and has an online address. It opens a
 * sheet to copy or share the list for that store and to open the chain's public site or its public
 * site search for one item. Every address is a link the user's browser opens: the app fetches
 * nothing from the chain and puts nothing in its cart (docs/cart-transfer.md). It reads no price or
 * ranking data and ranking never reads it. A failed `/chains/online` request renders nothing.
 */
export function HandoffAction({ store, items }: HandoffActionProps) {
  const chains = useChainsOnline();
  const t = useT(handoffMessages);
  const [open, setOpen] = useState(false);
  const chain = enabledChain(chains, store.chain_id);
  if (!chain) return null;
  return (
    <>
      <button
        type="button"
        className={styles.action}
        data-testid={`handoff-open-${store.store_id}`}
        aria-haspopup="dialog"
        aria-label={t("actionLabel", { chain: chain.chain_name })}
        onClick={() => setOpen(true)}
      >
        <IconCart size={14} />
        {t("action")}
      </button>
      {open ? (
        <HandoffSheet
          chainName={chain.chain_name}
          onlineUrl={httpsUrl(chain.online_url) ?? ""}
          template={chain.search_url_template ?? null}
          referral={chain.referral}
          items={handoffItems(items)}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </>
  );
}

function HandoffSheet({
  chainName,
  onlineUrl,
  template,
  referral,
  items,
  onClose,
}: {
  chainName: string;
  onlineUrl: string;
  template: string | null;
  referral: boolean;
  items: HandoffItem[];
  onClose: () => void;
}) {
  const t = useT(handoffMessages);
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const text = listText(items, (i) => t("listLine", { name: i.name, quantity: i.quantity }));
  const canNativeShare = typeof navigator !== "undefined" && typeof navigator.share === "function";

  async function copy() {
    trackEvent("cart_handoff", { action: "copy" });
    let ok = false;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch {
      // Clipboard API refused (permissions, insecure context): select the text and let the user copy.
      const el = textRef.current;
      if (el) {
        el.focus();
        el.select();
        try {
          ok = document.execCommand("copy");
        } catch {
          ok = false;
        }
      }
    }
    setCopied(ok);
    setFailed(!ok);
  }

  function share() {
    trackEvent("cart_handoff", { action: "share" });
    void navigator
      .share({ title: t("shareTitle", { chain: chainName }), text })
      .catch(() => undefined);
  }

  const linkProps = { target: "_blank", rel: "noopener noreferrer" } as const;
  const referralTag = referral ? (
    <span className={styles.referral} data-testid="handoff-referral-label">
      {t("referralLabel")}
    </span>
  ) : null;

  return (
    <BottomSheet
      open
      onClose={onClose}
      eyebrow={t("sheetEyebrow")}
      title={t("sheetTitle", { chain: chainName })}
    >
      <div className={styles.stack} data-testid="handoff-sheet">
        <p className={styles.hint}>{t("intro")}</p>
        <p className={styles.disclaimer} data-testid="handoff-disclaimer">
          <IconInfo size={15} />
          <span>{t("disclaimer")}</span>
        </p>
        {referral ? (
          <p className={styles.hint} data-testid="handoff-referral-note">
            {t("referralNote", { chain: chainName })}
          </p>
        ) : null}

        {items.length === 0 ? (
          <p className={styles.hint}>{t("noItems")}</p>
        ) : (
          <>
            <div className={styles.field}>
              <label htmlFor="handoff-text" className={styles.label}>
                {t("textLabel")}
              </label>
              <textarea
                id="handoff-text"
                ref={textRef}
                className={styles.text}
                readOnly
                rows={Math.min(8, Math.max(3, items.length))}
                value={text}
                onFocus={(e) => e.currentTarget.select()}
                data-testid="handoff-text"
              />
            </div>
            <div className={styles.row}>
              <Button onClick={() => void copy()} data-testid="handoff-copy">
                {t("copy")}
              </Button>
              {canNativeShare ? (
                <Button variant="outline" onClick={share} data-testid="handoff-share">
                  {t("share")}
                </Button>
              ) : null}
            </div>
          </>
        )}

        <div role="status" aria-live="polite">
          {copied ? (
            <p className={styles.ok} data-testid="handoff-copied">
              <IconCheck size={15} /> {t("copied")}
            </p>
          ) : null}
          {failed ? (
            <p className={styles.error} data-testid="handoff-copy-failed">
              {t("copyFailed")}
            </p>
          ) : null}
        </div>

        <div className={styles.row}>
          <Button
            href={onlineUrl}
            variant="secondary"
            {...linkProps}
            data-testid="handoff-site"
            onClick={() => trackEvent("cart_handoff", { action: "open_site" })}
          >
            {t("openSite")}
          </Button>
          {referralTag}
        </div>

        {template && items.length > 0 ? (
          <section aria-labelledby="handoff-items-title">
            <h3 id="handoff-items-title" className={styles.itemsTitle}>
              {t("itemsTitle")}
            </h3>
            <ul className={styles.items}>
              {items.map((item, index) => {
                const href = searchUrl(template, item.name);
                return (
                  <li key={`${index}-${item.name}`} className={styles.item}>
                    <span className={styles.itemName}>
                      {item.name} <span dir="ltr">× {item.quantity}</span>
                    </span>
                    {href ? (
                      <span className={styles.itemLink}>
                        <a
                          href={href}
                          {...linkProps}
                          aria-label={t("searchItemLabel", { name: item.name, chain: chainName })}
                          data-testid="handoff-item-link"
                          onClick={() => trackEvent("cart_handoff", { action: "open_item" })}
                        >
                          {t("searchItem")}
                        </a>
                        {referralTag}
                      </span>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </section>
        ) : null}
      </div>
    </BottomSheet>
  );
}

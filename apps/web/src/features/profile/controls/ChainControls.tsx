"use client";

import { Button } from "@/components/ui/Button";
import { IconCheck } from "@/components/ui/icons";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { profileMessages } from "@/i18n/messages/profile";
import { CHAINS, chainLetter, chainName, clubLabel } from "../chains";
import { adoptNearestHomeStore, toggleClub, updateProfile, useProfile } from "../profileState";
import styles from "./controls.module.css";

/**
 * "הסופר שלי" (one chain, the baseline of the net saving, D7) and club memberships (several).
 * Chain cards are text badges, never real logos. A selected card shows a check icon as well as
 * the accent-soft background, so selection never relies on color alone.
 */
export function ChainControls() {
  const t = useT(profileMessages);
  const { locale } = useLocale();
  const profile = useProfile();
  return (
    <div className={styles.stack}>
      <div className={styles.group} role="group" aria-labelledby="home-chain-legend">
        <p id="home-chain-legend" className={styles.legend}>
          {t("homeChain")}
        </p>
        <p className={styles.hint}>{t("homeChainHint")}</p>
        <div className={styles.cards} data-testid="home-chain-cards">
          {CHAINS.map((chain) => {
            const selected = profile.homeChainId === chain.id;
            return (
              <button
                key={chain.id}
                type="button"
                className={styles.card}
                aria-pressed={selected}
                aria-label={t("homeChainAria", { name: chainName(chain, locale) })}
                onClick={() => {
                  updateProfile({ homeChainId: selected ? null : chain.id, homeStoreId: null });
                  // The chain becomes a concrete store: the nearest one to the profile's location.
                  if (!selected) void adoptNearestHomeStore(chain.id);
                }}
              >
                <span className={styles.badge} aria-hidden="true">
                  {chainLetter(chain, locale)}
                </span>
                <span className={styles.cardName}>{chainName(chain, locale)}</span>
                <span className={styles.tick} aria-hidden="true">
                  <IconCheck size={16} />
                </span>
              </button>
            );
          })}
        </div>
        {profile.homeChainId ? (
          <div>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => updateProfile({ homeChainId: null, homeStoreId: null })}
            >
              {t("clearChoice")}
            </Button>
          </div>
        ) : (
          <p className={styles.hint} data-testid="baseline-hint">
            {t("baselineHint")}
          </p>
        )}
      </div>

      <div className={styles.group} role="group" aria-labelledby="clubs-legend">
        <p id="clubs-legend" className={styles.legend}>
          {t("clubsLegend")}
        </p>
        <p className={styles.hint}>{t("clubsHint")}</p>
        <div className={styles.cards} data-testid="club-cards">
          {CHAINS.map((chain) => {
            const selected = profile.clubs.includes(chain.name);
            return (
              <button
                key={chain.id}
                type="button"
                className={styles.card}
                aria-pressed={selected}
                aria-label={clubLabel(chain.name, locale)}
                onClick={() => updateProfile({ clubs: toggleClub(profile, chain.name) })}
              >
                <span className={styles.badge} aria-hidden="true">
                  {chainLetter(chain, locale)}
                </span>
                <span className={styles.cardName}>{clubLabel(chain.name, locale)}</span>
                <span className={styles.tick} aria-hidden="true">
                  <IconCheck size={16} />
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

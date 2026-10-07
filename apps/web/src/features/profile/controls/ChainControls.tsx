"use client";

import { Button } from "@/components/ui/Button";
import { IconCheck } from "@/components/ui/icons";
import { CHAINS, clubLabel, mockStoreIdFor } from "../chains";
import { toggleClub, updateProfile, useProfile } from "../profileState";
import styles from "./controls.module.css";

/**
 * "הסופר שלי" (one chain, the baseline of the net saving, D7) and club memberships (several).
 * Chain cards are text badges, never real logos. A selected card shows a check icon as well as
 * the accent-soft background, so selection never relies on color alone.
 */
export function ChainControls() {
  const profile = useProfile();
  return (
    <div className={styles.stack}>
      <div className={styles.group} role="group" aria-labelledby="home-chain-legend">
        <p id="home-chain-legend" className={styles.legend}>
          הסופר שלי
        </p>
        <p className={styles.hint}>
          החיסכון שנציג הוא תמיד מול החנות שבחרת כאן, אחרי נסיעה. בחירה אחת.
        </p>
        <div className={styles.cards} data-testid="home-chain-cards">
          {CHAINS.map((chain) => {
            const selected = profile.homeChainId === chain.id;
            return (
              <button
                key={chain.id}
                type="button"
                className={styles.card}
                aria-pressed={selected}
                aria-label={`הסופר שלי: ${chain.name}`}
                onClick={() =>
                  updateProfile({
                    homeChainId: selected ? null : chain.id,
                    homeStoreId: selected ? null : mockStoreIdFor(chain.id),
                  })
                }
              >
                <span className={styles.badge} aria-hidden="true">
                  {chain.letter}
                </span>
                <span className={styles.cardName}>{chain.name}</span>
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
              ניקוי הבחירה
            </Button>
          </div>
        ) : (
          <p className={styles.hint} data-testid="baseline-hint">
            בלי חנות בסיס לא נוכל להראות חיסכון נטו. אפשר לבחור אותה בכל שלב בפרופיל.
          </p>
        )}
      </div>

      <div className={styles.group} role="group" aria-labelledby="clubs-legend">
        <p id="clubs-legend" className={styles.legend}>
          מועדונים שאני חברה בהם
        </p>
        <p className={styles.hint}>מבצעי מועדון יוצגו רק לחברי המועדון. אפשר לבחור כמה.</p>
        <div className={styles.cards} data-testid="club-cards">
          {CHAINS.map((chain) => {
            const selected = profile.clubs.includes(chain.name);
            return (
              <button
                key={chain.id}
                type="button"
                className={styles.card}
                aria-pressed={selected}
                aria-label={clubLabel(chain.name)}
                onClick={() => updateProfile({ clubs: toggleClub(profile, chain.name) })}
              >
                <span className={styles.badge} aria-hidden="true">
                  {chain.letter}
                </span>
                <span className={styles.cardName}>{clubLabel(chain.name)}</span>
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

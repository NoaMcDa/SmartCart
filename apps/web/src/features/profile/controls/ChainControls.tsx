"use client";

import { useId } from "react";
import { Button } from "@/components/ui/Button";
import { IconCheck } from "@/components/ui/icons";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { profileMessages } from "@/i18n/messages/profile";
import { CHAINS, chainLetter, chainName } from "../chains";
import {
  chainsWithClubs,
  chainsWithoutClubs,
  toggleClubId,
  useChainClubs,
  type ChainClubs,
  type ClubChoice,
} from "../clubs";
import { adoptNearestHomeStore, updateProfile, useProfile } from "../profileState";
import styles from "./controls.module.css";

/**
 * "הסופר שלי" (one chain, the baseline of the net saving, D7) and club memberships (several).
 * The clubs listed are the API's (`GET /chains/clubs`): per chain, the clubs and cards its real
 * promotion files name. The profile keeps their ids.
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

      <ClubPicker />
    </div>
  );
}

function ClubPicker() {
  const t = useT(profileMessages);
  const profile = useProfile();
  const clubs = useChainClubs();
  return (
    <div className={styles.group} role="group" aria-labelledby="clubs-legend">
      <p id="clubs-legend" className={styles.legend}>
        {t("clubsLegend")}
      </p>
      <p className={styles.hint}>{t("clubsHint")}</p>
      <div className={styles.clubs} data-testid="club-cards">
        {clubs.status === "loading" ? (
          <p className={styles.status} role="status">
            {t("clubsLoading")}
          </p>
        ) : null}
        {clubs.status === "error" ? (
          <div className={styles.statusRow}>
            <p className={styles.error} role="alert">
              {t("clubsError")}
            </p>
            <Button size="sm" variant="ghost" onClick={clubs.reload}>
              {t("clubsRetry")}
            </Button>
          </div>
        ) : null}
        {clubs.status === "success" ? (
          <ClubGroups rows={clubs.chains} selected={profile.clubs} />
        ) : null}
      </div>
    </div>
  );
}

function ClubGroups({ rows, selected }: { rows: ChainClubs[]; selected: string[] }) {
  const t = useT(profileMessages);
  const { locale } = useLocale();
  const groups = chainsWithClubs(rows);
  const without = chainsWithoutClubs(rows);
  return (
    <>
      {groups.map((group) => {
        const name = group.name(locale);
        const chain = CHAINS.find((c) => c.id === group.key);
        return (
          <div
            key={group.key}
            className={styles.clubGroup}
            role="group"
            aria-label={t("clubGroupAria", { chain: name })}
            data-testid={`club-group-${group.key}`}
          >
            <p className={styles.clubGroupTitle}>{name}</p>
            <div className={`${styles.cards} ${styles.clubCards}`}>
              {group.clubs.map((club) => (
                <ClubCard
                  key={club.id}
                  club={club}
                  letter={chain ? chainLetter(chain, locale) : name.slice(0, 1)}
                  selected={selected.includes(club.id)}
                  onToggle={() => updateProfile({ clubs: toggleClubId(selected, club.id) })}
                />
              ))}
            </div>
          </div>
        );
      })}
      {without.length > 0 ? (
        <p className={styles.hint} data-testid="clubs-none">
          {t("clubsNoneFor", { chains: without.map((c) => chainName(c, locale)).join(", ") })}
        </p>
      ) : null}
    </>
  );
}

function ClubCard({
  club,
  letter,
  selected,
  onToggle,
}: {
  club: ClubChoice;
  letter: string;
  selected: boolean;
  onToggle: () => void;
}) {
  const t = useT(profileMessages);
  const id = useId();
  // The name is the club's own name; the kind is its description; the chain is the card's group.
  return (
    <button
      type="button"
      className={styles.card}
      aria-pressed={selected}
      aria-labelledby={`${id}-name`}
      aria-describedby={`${id}-kind`}
      data-club-id={club.id}
      onClick={onToggle}
    >
      <span className={styles.badge} aria-hidden="true">
        {letter}
      </span>
      <span className={styles.cardText}>
        <span id={`${id}-name`} className={styles.cardName} lang="he">
          {club.label}
        </span>
        <span id={`${id}-kind`} className={styles.cardKind}>
          {t(`clubKind_${club.kind}`)}
        </span>
      </span>
      <span className={styles.tick} aria-hidden="true">
        <IconCheck size={16} />
      </span>
    </button>
  );
}

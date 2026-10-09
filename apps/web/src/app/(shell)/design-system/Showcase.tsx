"use client";

import { useState, type ReactNode } from "react";
import { DocumentTitle } from "@/components/shell/PageChrome";
import { formatRich } from "@/i18n/format";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { appMessages } from "@/i18n/messages/app";
import { formatDistance } from "@/lib/format";
import {
  BottomSheet,
  Button,
  Card,
  CardRow,
  CheckChip,
  Chip,
  FlexChip,
  IconCheck,
  IconClose,
  IconClipboard,
  IconMap,
  IconPin,
  Price,
  PriceRange,
  PromoConfidence,
  SegmentedControl,
  Skeleton,
  SkeletonText,
  Stepper,
  Switch,
  Tag,
  TrustedPrice,
  UpdatedAt,
  type FlexLevel,
} from "@/components/ui";
import styles from "./Showcase.module.css";

const TOKENS = [
  "bg",
  "surface",
  "subtle",
  "border",
  "divider",
  "text",
  "muted",
  "faint",
  "accent",
  "accent-fg",
  "accent-soft",
  "brand-bg",
  "brand-fg",
  "exact-bg",
  "exact-fg",
  "warn-bg",
  "warn-fg",
  "good-bg",
  "good-fg",
  "bad-fg",
] as const;

/** Fixed "now" so the relative update times read the same whenever the page is opened. */
const DS_NOW = new Date("2026-10-07T12:00:00Z");

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>{title}</h3>
      {children}
    </section>
  );
}

function Panel({ theme }: { theme: "light" | "dark" }) {
  const t = useT(appMessages);
  const { locale } = useLocale();
  const [qty, setQty] = useState(2);
  const [remember, setRemember] = useState(true);
  const [view, setView] = useState<"list" | "map">("list");
  const [flex, setFlex] = useState<FlexLevel>("any_brand");
  const [allowCarton, setAllowCarton] = useState(true);
  const [allowBrand, setAllowBrand] = useState(true);
  const [allowFlavor, setAllowFlavor] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const next: Record<FlexLevel, FlexLevel> = {
    exact: "any_brand",
    any_brand: "close",
    close: "exact",
  };

  return (
    <div data-theme={theme} className={styles.panel} data-testid={`ds-panel-${theme}`}>
      <h2 className={styles.panelTitle}>
        {theme === "light" ? t("dsPanelLight") : t("dsPanelDark")}
      </h2>

      <Section title={t("dsColors")}>
        <ul className={styles.swatches}>
          {TOKENS.map((token) => (
            <li key={token} className={styles.swatch}>
              <span className={styles.swatchColor} style={{ background: `var(--sc-${token})` }} />
              <code dir="ltr">--sc-{token}</code>
            </li>
          ))}
        </ul>
      </Section>

      <Section title={t("dsButtons")}>
        <div className={styles.row}>
          <Button>{t("dsCompare")}</Button>
          <Button variant="secondary">{t("dsCancel")}</Button>
          <Button variant="outline" size="sm">
            {t("dsKeepOriginal")}
          </Button>
          <Button variant="outline" size="sm" tone="bad" iconStart={<IconClose size={14} />}>
            {t("dsNotGoodSub")}
          </Button>
          <Button variant="ghost" size="sm" iconStart={<IconClipboard size={16} />}>
            {t("dsPasteList")}
          </Button>
          <Button disabled>{t("dsUnavailable")}</Button>
        </div>
      </Section>

      <Section title={t("dsFlexChips")}>
        <div className={styles.row}>
          <FlexChip level="exact" />
          <FlexChip level="any_brand" />
          <FlexChip level="close" />
          <FlexChip level={flex} onClick={() => setFlex(next[flex])} />
        </div>
        <div className={styles.row}>
          <Chip tone="neutral" selected={allowCarton} onClick={() => setAllowCarton((v) => !v)}>
            {t("dsCartonOrBag")}
          </Chip>
          <Chip tone="neutral" selected={false} onClick={() => {}}>
            {t("dsOtherPackSize")}
          </Chip>
          <Chip tone="accent" size="sm" icon={<IconCheck size={12} />}>
            {t("dsRecommended")}
          </Chip>
          <Chip tone="exact" size="sm">
            {t("dsSplitTwo")}
          </Chip>
        </div>
      </Section>

      <Section title={t("dsTrust")}>
        <div className={styles.row} data-testid={`ds-updated-${theme}`}>
          <UpdatedAt
            iso="2026-10-07T03:40:00Z"
            now={DS_NOW}
            prefix={t("dsPricesUpdated")}
            withIcon
          />
          <UpdatedAt iso="2026-10-06T15:20:00Z" now={DS_NOW} />
          <UpdatedAt iso="2026-10-04T08:00:00Z" now={DS_NOW} />
          <UpdatedAt iso={null} />
        </div>
        <div className={styles.row} data-testid={`ds-trusted-${theme}`}>
          <TrustedPrice amount="12.90" updatedAt="2026-10-07T03:40:00Z" size="lg" />
          <TrustedPrice
            amount="4.50"
            updatedAt="2026-10-06T15:20:00Z"
            layout="inline"
            fractionDigits={2}
          />
        </div>
        <div className={styles.row} data-testid={`ds-trust-tags-${theme}`}>
          <Tag variant="substitute">{t("dsSubstitute")}</Tag>
          <Tag variant="club">{t("dsClubPromo")}</Tag>
          <PromoConfidence confidence={0.96} />
          <PromoConfidence confidence={0.72} />
          <PromoConfidence confidence={null} />
        </div>
        <div className={styles.row} role="group" aria-label={t("dsMayWaive")}>
          <CheckChip checked={allowBrand} onChange={setAllowBrand}>
            {t("dsOtherBrand")}
          </CheckChip>
          <CheckChip checked={allowFlavor} onChange={setAllowFlavor}>
            {t("dsOtherFlavor")}
          </CheckChip>
          <CheckChip checked={false} onChange={() => {}} disabled>
            {t("dsUnavailable")}
          </CheckChip>
        </div>
      </Section>

      <Section title={t("dsTags")}>
        <div className={styles.row}>
          <Tag variant="matched">{t("dsSameType")}</Tag>
          <Tag variant="unverified">{t("dsSolids")}</Tag>
          <Tag variant="differs">{t("dsPrivateLabel")}</Tag>
          <Tag variant="missing">{t("dsOneMissing")}</Tag>
          <Tag variant="estimated">{t("dsEstimatedWeighed")}</Tag>
        </div>
      </Section>

      <Section title={t("dsPrices")}>
        <p className={styles.sentence} data-testid={`price-sentence-${theme}`}>
          {formatRich(t("dsSentenceTotal"), {
            total: <Price amount="389.00" size="lg" />,
            saving: <Price amount={57} tone="good" />,
          })}
        </p>
        <p className={styles.sentence}>
          {formatRich(t("dsSentenceUnit"), {
            unit: <Price amount="1.73" />,
            shelf: <Price amount="4.5" fractionDigits={2} />,
          })}
        </p>
        <p className={styles.sentence}>
          {formatRich(t("dsSentenceEstimate"), {
            range: <PriceRange from={412} to={468} size="lg" />,
          })}
        </p>
        <div className={styles.row} data-testid={`ds-price-sizes-${theme}`}>
          <Price amount="3.9" size="sm" />
          <Price amount="3.9" size="md" />
          <Price amount="3.9" size="lg" />
          <Price amount="3.9" size="xl" />
          <Price amount="389" size="hero" />
          <Price amount="3.9" tone="muted" />
          <Price amount="57" tone="good" />
        </div>
      </Section>

      <Section title={t("dsCards")}>
        <Card as="article" variant="recommended">
          <div className={styles.spread}>
            <Chip tone="accent" size="sm" icon={<IconCheck size={12} />}>
              {t("dsRecommended")}
            </Chip>
            <span className={styles.meta}>
              <IconPin size={14} /> {formatDistance(4200, locale)}
            </span>
          </div>
          <div className={styles.storeName}>{t("dsStoreName")}</div>
          <div className={styles.spread}>
            <Price amount={389} size="hero" />
            <span className={styles.saving}>
              {formatRich(t("dsSaving"), { price: <Price amount={57} /> })}
            </span>
          </div>
        </Card>
        <Card padding="none">
          <CardRow>
            <div className={styles.itemText}>
              <div className={styles.itemName}>{t("dsMilk")}</div>
              <FlexChip level="any_brand" onClick={() => setSheetOpen(true)} />
            </div>
            <Stepper value={qty} onChange={setQty} label={t("dsMilk")} min={1} />
          </CardRow>
          <CardRow>
            <div className={styles.itemText}>
              <div className={styles.itemName}>{t("dsTomatoes")}</div>
              <Tag variant="estimated">{t("dsEstimatedWeighed")}</Tag>
            </div>
            <Stepper
              value={1}
              onChange={() => {}}
              label={t("dsTomatoes")}
              unit={t("dsKgUnit")}
              step={0.5}
            />
          </CardRow>
        </Card>
      </Section>

      <Section title={t("dsSwitchSegmented")}>
        <Switch checked={remember} onChange={setRemember} label={t("dsRememberMilk")} />
        <SegmentedControl
          label={t("dsView")}
          value={view}
          onChange={setView}
          options={[
            { value: "list", label: t("dsViewList") },
            { value: "map", label: t("dsViewMap"), icon: <IconMap size={16} /> },
          ]}
        />
      </Section>

      <Section title={t("dsSheet")}>
        <Button variant="secondary" onClick={() => setSheetOpen(true)}>
          {t("dsOpenSheet")}
        </Button>
        <BottomSheet
          open={sheetOpen}
          onClose={() => setSheetOpen(false)}
          eyebrow={t("dsSheetEyebrow")}
          title={t("dsMilk")}
          footer={
            <>
              <Button onClick={() => setSheetOpen(false)}>{t("dsSave")}</Button>
              <Button variant="secondary" onClick={() => setSheetOpen(false)}>
                {t("dsCancel")}
              </Button>
            </>
          }
        >
          <p className={styles.meta}>{t("dsSheetBody")}</p>
          <Switch checked={remember} onChange={setRemember} label={t("dsRememberMilk")} />
        </BottomSheet>
      </Section>

      <Section title={t("dsSkeleton")}>
        <Card aria-busy="true">
          <Skeleton width="50%" height={18} />
          <SkeletonText lines={3} />
          <Skeleton height={44} radius={14} />
        </Card>
      </Section>
    </div>
  );
}

export function Showcase() {
  const t = useT(appMessages);
  return (
    <div className={styles.page}>
      <DocumentTitle id="designSystemTitle" />
      <h1 className={styles.title}>{t("designSystemTitle")}</h1>
      <p className={styles.meta}>{t("dsIntro")}</p>
      <div className={styles.grid}>
        <Panel theme="light" />
        <Panel theme="dark" />
      </div>
    </div>
  );
}

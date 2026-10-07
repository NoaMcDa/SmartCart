"use client";

import { useState, type ReactNode } from "react";
import {
  BottomSheet,
  Button,
  Card,
  CardRow,
  Chip,
  FlexChip,
  IconCheck,
  IconClose,
  IconClipboard,
  IconMap,
  IconPin,
  Price,
  PriceRange,
  SegmentedControl,
  Skeleton,
  SkeletonText,
  Stepper,
  Switch,
  Tag,
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

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>{title}</h3>
      {children}
    </section>
  );
}

function Panel({ theme }: { theme: "light" | "dark" }) {
  const [qty, setQty] = useState(2);
  const [remember, setRemember] = useState(true);
  const [view, setView] = useState<"list" | "map">("list");
  const [flex, setFlex] = useState<FlexLevel>("any_brand");
  const [allowCarton, setAllowCarton] = useState(true);
  const [sheetOpen, setSheetOpen] = useState(false);
  const next: Record<FlexLevel, FlexLevel> = {
    exact: "any_brand",
    any_brand: "close",
    close: "exact",
  };

  return (
    <div data-theme={theme} className={styles.panel} data-testid={`ds-panel-${theme}`}>
      <h2 className={styles.panelTitle}>{theme === "light" ? "ערכה בהירה" : "ערכה כהה"}</h2>

      <Section title="צבעים">
        <ul className={styles.swatches}>
          {TOKENS.map((t) => (
            <li key={t} className={styles.swatch}>
              <span className={styles.swatchColor} style={{ background: `var(--sc-${t})` }} />
              <code dir="ltr">--sc-{t}</code>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="כפתורים">
        <div className={styles.row}>
          <Button>השווי</Button>
          <Button variant="secondary">ביטול</Button>
          <Button variant="outline" size="sm">
            השאירי את המקורי
          </Button>
          <Button variant="outline" size="sm" tone="bad" iconStart={<IconClose size={14} />}>
            לא תחליף טוב
          </Button>
          <Button variant="ghost" size="sm" iconStart={<IconClipboard size={16} />}>
            הדבקת רשימה
          </Button>
          <Button disabled>לא זמין</Button>
        </div>
      </Section>

      <Section title="צ'יפים של גמישות">
        <div className={styles.row}>
          <FlexChip level="exact" />
          <FlexChip level="any_brand" />
          <FlexChip level="close" />
          <FlexChip level={flex} onClick={() => setFlex(next[flex])} />
        </div>
        <div className={styles.row}>
          <Chip tone="neutral" selected={allowCarton} onClick={() => setAllowCarton((v) => !v)}>
            קרטון או שקית
          </Chip>
          <Chip tone="neutral" selected={false} onClick={() => {}}>
            גודל אריזה אחר
          </Chip>
          <Chip tone="accent" size="sm" icon={<IconCheck size={12} />}>
            מומלץ
          </Chip>
          <Chip tone="exact" size="sm">
            פיצול ל-2 סופרים
          </Chip>
        </div>
      </Section>

      <Section title="תגיות">
        <div className={styles.row}>
          <Tag variant="matched">אותו סוג מוצר</Tag>
          <Tag variant="unverified">28% מוצקים · לא מאומת</Tag>
          <Tag variant="differs">מותג פרטי במקום אסם</Tag>
          <Tag variant="missing">1 פריט חסר</Tag>
          <Tag variant="estimated">מחיר משוער · שקיל</Tag>
        </div>
      </Section>

      <Section title="מחירים">
        <p className={styles.sentence} data-testid={`price-sentence-${theme}`}>
          סך הסל <Price amount="389.00" size="lg" />, חוסך <Price amount={57} tone="good" /> לעומת
          שופרסל דיל.
        </p>
        <p className={styles.sentence}>
          <Price amount="1.73" /> ל-100 ג&apos;, מחיר מדף <Price amount="4.5" fractionDigits={2} />.
        </p>
        <p className={styles.sentence}>
          הערכת סל: <PriceRange from={412} to={468} size="lg" />
        </p>
      </Section>

      <Section title="כרטיסים">
        <Card as="article" variant="recommended">
          <div className={styles.spread}>
            <Chip tone="accent" size="sm" icon={<IconCheck size={12} />}>
              מומלץ
            </Chip>
            <span className={styles.meta}>
              <IconPin size={14} /> 4.2 ק&quot;מ
            </span>
          </div>
          <div className={styles.storeName}>רמי לוי · מודיעין</div>
          <div className={styles.spread}>
            <Price amount={389} size="hero" />
            <span className={styles.saving}>
              חוסך <Price amount={57} />
            </span>
          </div>
        </Card>
        <Card padding="none">
          <CardRow>
            <div className={styles.itemText}>
              <div className={styles.itemName}>חלב טרי 3%, 1 ליטר</div>
              <FlexChip level="any_brand" onClick={() => setSheetOpen(true)} />
            </div>
            <Stepper value={qty} onChange={setQty} label="חלב טרי 3%, 1 ליטר" min={1} />
          </CardRow>
          <CardRow>
            <div className={styles.itemText}>
              <div className={styles.itemName}>עגבניות, 1 ק&quot;ג</div>
              <Tag variant="estimated">מחיר משוער · שקיל</Tag>
            </div>
            <Stepper value={1} onChange={() => {}} label='עגבניות, 1 ק"ג' unit='ק"ג' step={0.5} />
          </CardRow>
        </Card>
      </Section>

      <Section title="מתג ובקרה מקטעית">
        <Switch checked={remember} onChange={setRemember} label="זכרי בחירה זו לכל סוגי החלב" />
        <SegmentedControl
          label="תצוגה"
          value={view}
          onChange={setView}
          options={[
            { value: "list", label: "רשימה" },
            { value: "map", label: "מפה", icon: <IconMap size={16} /> },
          ]}
        />
      </Section>

      <Section title="גיליון תחתון">
        <Button variant="secondary" onClick={() => setSheetOpen(true)}>
          פתיחת גיליון גמישות
        </Button>
        <BottomSheet
          open={sheetOpen}
          onClose={() => setSheetOpen(false)}
          eyebrow="רמת גמישות לפריט"
          title="חלב טרי 3%, 1 ליטר"
          footer={
            <>
              <Button onClick={() => setSheetOpen(false)}>שמרי</Button>
              <Button variant="secondary" onClick={() => setSheetOpen(false)}>
                ביטול
              </Button>
            </>
          }
        >
          <p className={styles.meta}>
            אותו מוצר מכל יצרן: תנובה, טרה, יטבתה, מותג פרטי. נשמר: 3% שומן, טרי, 1 ליטר.
          </p>
          <Switch checked={remember} onChange={setRemember} label="זכרי בחירה זו לכל סוגי החלב" />
        </BottomSheet>
      </Section>

      <Section title="שלד טעינה">
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
  return (
    <div className={styles.page}>
      <h1 className={styles.title}>ערכת עיצוב</h1>
      <p className={styles.meta}>
        כל רכיבי src/components/ui בשתי הערכות. דף פיתוח, לא מקושר מהאפליקציה.
      </p>
      <div className={styles.grid}>
        <Panel theme="light" />
        <Panel theme="dark" />
      </div>
    </div>
  );
}

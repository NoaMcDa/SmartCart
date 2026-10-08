"use client";

import { useId, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { parseList, type ParsedRow } from "@/api/client";
import {
  Button,
  Card,
  IconBook,
  IconClipboard,
  IconInfo,
  IconMic,
  IconShare,
  Skeleton,
  UpdatedAt,
} from "@/components/ui";
import { reportListPasted } from "@/features/consent/betaEvents";
import { RecipeSheet } from "@/features/recipe/RecipeSheet";
import { VoiceSheet } from "@/features/voice/VoiceSheet";
import { useVoiceSupported } from "@/features/voice/useVoiceInput";
import { buildCompareInput, useCompareEstimate } from "@/state/comparison";
import { basketItems, groupByDepartment, listActions, useList } from "@/state/list";
import { useShopper } from "@/state/shopper";
import { EstimatePanel } from "./EstimatePanel";
import { FlexibilitySheet } from "./FlexibilitySheet";
import { ListRow } from "./ListRow";
import styles from "./ListBuilder.module.css";

const PLACEHOLDER = "חלב, 2 רסק עגבניות, סלמון…";

/**
 * List builder (issue #24): paste or type a Hebrew list, /parse-list turns it into canonical rows
 * grouped by department, each with a quantity and a flexibility chip. Flagged rows get an amber
 * confirmation; Compare stays usable. The list lives in localStorage (src/state/list.ts).
 */
export function ListBuilder() {
  const { state, hydrated } = useList();
  const shopper = useShopper();
  const [text, setText] = useState("");
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [flexItemId, setFlexItemId] = useState<string | null>(null);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [recipeOpen, setRecipeOpen] = useState(false);
  // null before hydration: neither the mic nor the "not supported" hint is rendered then.
  const voiceSupported = useVoiceSupported();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  // Set by a paste into the box or the clipboard button; read by the next successful parse.
  const pastedRef = useRef(false);
  const inputId = useId();

  const basket = useMemo(() => basketItems(state), [state]);
  const compareInput = useMemo(
    () => (shopper ? buildCompareInput(basket, shopper) : null),
    [basket, shopper],
  );
  const estimateRes = useCompareEstimate(compareInput);
  const estimateData = "data" in estimateRes ? estimateRes.data : undefined;
  const newestPrice =
    estimateData?.stores
      .map((s) => s.prices_updated_at)
      .sort()
      .at(-1) ?? null;

  const groups = groupByDepartment(state.items);
  const notFound = state.items.filter((i) => i.notFound);
  const recognized = state.items.length - notFound.length;
  const flexItem = state.items.find((i) => i.id === flexItemId) ?? null;

  /** The one path from text to list rows (typed, pasted, or dictated): `/parse-list`, then add. */
  async function parseInto(value: string): Promise<number | null> {
    try {
      const res = await parseList({ text: value, flex_defaults: state.flexDefaults });
      listActions.add(res.rows);
      return res.rows.length;
    } catch {
      return null;
    }
  }

  async function submit(raw: string) {
    const value = raw.trim();
    if (!value || parsing) return;
    const wasPasted = pastedRef.current;
    pastedRef.current = false;
    setParsing(true);
    setError(null);
    setHint(null);
    const added = await parseInto(value);
    if (added === null) {
      setError("לא הצלחנו לזהות את הרשימה. בדקי את החיבור ונסי שוב.");
    } else {
      if (wasPasted) reportListPasted(added);
      setText("");
    }
    setParsing(false);
  }

  /** Confirmed dictation: same call as a pasted list, and the same amber confirmation afterwards. */
  async function addDictated(value: string): Promise<number | null> {
    const added = await parseInto(value);
    if (added !== null) {
      setError(null);
      setHint(`נוספו ${added} פריטים מההכתבה. בדקי את הפריטים שמסומנים לאישור.`);
    }
    return added;
  }

  function addRecipe(rows: ParsedRow[], info: { title: string; servings: number }) {
    listActions.add(rows);
    setRecipeOpen(false);
    setError(null);
    setHint(
      `נוספו ${rows.length} פריטים מהמתכון "${info.title}" ל-${info.servings} מנות. בדקי את הפריטים שמסומנים לאישור.`,
    );
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void submit(text);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void submit(text);
    }
  }

  async function pasteFromClipboard() {
    setHint(null);
    try {
      const clip = await navigator.clipboard.readText();
      if (!clip.trim()) {
        setHint("הלוח ריק. העתיקי רשימה ונסי שוב.");
        return;
      }
      setText(clip);
      pastedRef.current = true;
      await submit(clip);
    } catch {
      setHint("אין גישה ללוח. הדביקי בתיבה עם Ctrl+V או לחיצה ארוכה.");
      inputRef.current?.focus();
    }
  }

  function editNotFound(id: string, inputText: string) {
    listActions.remove(id);
    setText((prev) => (prev ? `${prev}, ${inputText}` : inputText));
    inputRef.current?.focus();
  }

  return (
    <div className={styles.page}>
      <div className={styles.head}>
        <p className={styles.subline} data-testid="list-subline">
          <span dir="ltr">{recognized}</span> פריטים
          {newestPrice ? (
            <>
              {" · "}
              <UpdatedAt iso={newestPrice} prefix="מחירים עודכנו" />
            </>
          ) : null}
        </p>
        {/* /lists/mine/share opens this device's shared list when there is one, else offers to create it. */}
        <Button
          href="/lists/mine/share"
          variant="outline"
          size="sm"
          iconStart={<IconShare size={16} />}
          data-testid="share-entry"
        >
          שיתוף
        </Button>
      </div>

      <div className={styles.layout}>
        <section className={styles.listColumn} aria-label="הרשימה">
          <form className={styles.inputBox} onSubmit={onSubmit}>
            <label htmlFor={inputId} className="sr-only">
              הוסיפי פריטים לרשימה
            </label>
            <textarea
              ref={inputRef}
              id={inputId}
              className={styles.input}
              rows={1}
              value={text}
              placeholder={PLACEHOLDER}
              onChange={(e) => {
                setText(e.target.value);
                if (!e.target.value) pastedRef.current = false;
              }}
              onKeyDown={onKeyDown}
              onPaste={() => {
                pastedRef.current = true;
              }}
              aria-describedby={error || hint ? `${inputId}-msg` : undefined}
              enterKeyHint="done"
            />
            {voiceSupported ? (
              <button
                type="button"
                className={styles.inputButton}
                aria-label="הכתבה קולית"
                aria-haspopup="dialog"
                onClick={() => setVoiceOpen(true)}
                data-testid="voice-open"
              >
                <IconMic size={22} />
              </button>
            ) : null}
            <button
              type="button"
              className={styles.inputButton}
              aria-label="הדבקת רשימה"
              onClick={pasteFromClipboard}
            >
              <IconClipboard size={22} />
            </button>
            <Button type="submit" size="sm" disabled={parsing || !text.trim()}>
              הוסיפי
            </Button>
          </form>
          <div className={styles.sources}>
            <Button
              variant="ghost"
              size="sm"
              iconStart={<IconBook size={16} />}
              onClick={() => setRecipeOpen(true)}
              aria-haspopup="dialog"
              data-testid="recipe-open"
            >
              ממתכון
            </Button>
          </div>
          {voiceSupported === false ? (
            <p className={styles.hint} data-testid="voice-unsupported">
              הכתבה קולית לא זמינה בדפדפן הזה. אפשר להקליד או להדביק את הרשימה.
            </p>
          ) : null}
          {error || hint ? (
            <p
              id={`${inputId}-msg`}
              className={error ? styles.error : styles.hint}
              role={error ? "alert" : "status"}
            >
              {error ?? hint}
            </p>
          ) : null}

          <div aria-busy={parsing || !hydrated} aria-live="polite">
            {parsing ? (
              <p className={styles.hint} role="status">
                מזהה פריטים…
              </p>
            ) : null}
          </div>

          {!hydrated ? (
            <Card padding="none" aria-hidden="true">
              {[0, 1, 2].map((i) => (
                <div key={i} className={styles.row}>
                  <Skeleton width="60%" height={16} />
                </div>
              ))}
            </Card>
          ) : state.items.length === 0 && !parsing ? (
            <Card className={styles.empty}>
              <h2 className={styles.emptyTitle}>הרשימה ריקה</h2>
              <p className={styles.emptyText}>
                הדביקי רשימה או כתבי פריטים מופרדים בפסיק, למשל &quot;{PLACEHOLDER}&quot;. נזהה כל
                פריט, נציע רמת גמישות ונשווה בין הסניפים הקרובים.
              </p>
            </Card>
          ) : null}

          {groups.map((group) => (
            <section key={group.name} className={styles.group} aria-label={group.name}>
              <h2 className={styles.groupTitle}>
                <span>{group.name}</span>
                <span className={styles.groupCount}>
                  <span dir="ltr">{group.items.length}</span>{" "}
                  {group.items.length === 1 ? "פריט" : "פריטים"}
                </span>
              </h2>
              <Card padding="none" className={styles.groupCard}>
                {group.items.map((item) => (
                  <ListRow key={item.id} item={item} onOpenFlex={setFlexItemId} />
                ))}
              </Card>
            </section>
          ))}

          {notFound.length ? (
            <section className={styles.group} aria-label="לא זוהו">
              <h2 className={styles.groupTitle}>
                <span>לא זוהו</span>
                <span className={styles.groupCount}>לא ייכללו בהשוואה</span>
              </h2>
              <Card padding="none" className={styles.groupCard}>
                {notFound.map((item) => (
                  <div key={item.id} className={styles.row} data-testid="not-found-row">
                    <div className={styles.rowLine}>
                      <IconInfo size={18} className={styles.notFoundIcon} />
                      <div className={styles.rowMain}>
                        <div className={styles.rowName}>
                          לא מצאנו את &quot;{item.inputText}&quot;
                        </div>
                        <div className={styles.rowHint}>נסי לכתוב אחרת או לדווח לנו על פער</div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => editNotFound(item.id, item.inputText)}
                        aria-label={`עריכת ${item.inputText}`}
                      >
                        עריכה
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => listActions.remove(item.id)}
                        aria-label={`הסרת ${item.inputText}`}
                      >
                        הסרה
                      </Button>
                    </div>
                  </div>
                ))}
              </Card>
            </section>
          ) : null}

          {state.items.length ? (
            <div className={styles.listActions}>
              <Button variant="ghost" size="sm" onClick={() => listActions.clear()}>
                ניקוי הרשימה
              </Button>
            </div>
          ) : null}
        </section>

        <EstimatePanel
          items={state.items}
          basket={basket}
          data={estimateData}
          loading={estimateRes.status === "loading"}
          radiusKm={shopper ? Math.round(shopper.radiusM / 100) / 10 : 5}
          newestPrice={newestPrice}
        />
      </div>

      <VoiceSheet open={voiceOpen} onClose={() => setVoiceOpen(false)} onAdd={addDictated} />
      <RecipeSheet open={recipeOpen} onClose={() => setRecipeOpen(false)} onAdd={addRecipe} />

      <FlexibilitySheet
        item={flexItem}
        flexDefaults={state.flexDefaults}
        onClose={() => setFlexItemId(null)}
      />
    </div>
  );
}

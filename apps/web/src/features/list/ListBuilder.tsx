"use client";

import { useId, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { parseList } from "@/api/client";
import {
  Button,
  Card,
  IconClipboard,
  IconInfo,
  IconMic,
  Skeleton,
  UpdatedAt,
} from "@/components/ui";
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
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const inputId = useId();
  const micTipId = useId();

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

  async function submit(raw: string) {
    const value = raw.trim();
    if (!value || parsing) return;
    setParsing(true);
    setError(null);
    setHint(null);
    try {
      const res = await parseList({ text: value, flex_defaults: state.flexDefaults });
      listActions.add(res.rows);
      setText("");
    } catch {
      setError("לא הצלחנו לזהות את הרשימה. בדקי את החיבור ונסי שוב.");
    } finally {
      setParsing(false);
    }
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
      <p className={styles.subline} data-testid="list-subline">
        <span dir="ltr">{recognized}</span> פריטים
        {newestPrice ? (
          <>
            {" · "}
            <UpdatedAt iso={newestPrice} prefix="מחירים עודכנו" />
          </>
        ) : null}
      </p>

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
              onChange={(e) => setText(e.target.value)}
              onKeyDown={onKeyDown}
              aria-describedby={error || hint ? `${inputId}-msg` : undefined}
              enterKeyHint="done"
            />
            <span className={styles.tipWrap}>
              <button
                type="button"
                className={styles.inputButton}
                aria-label="הכתבה קולית"
                aria-disabled="true"
                aria-describedby={micTipId}
                title="בקרוב"
                onClick={(e) => e.preventDefault()}
              >
                <IconMic size={22} />
              </button>
              <span role="tooltip" id={micTipId} className={styles.tooltip}>
                בקרוב
              </span>
            </span>
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

      <FlexibilitySheet
        item={flexItem}
        flexDefaults={state.flexDefaults}
        onClose={() => setFlexItemId(null)}
      />
    </div>
  );
}

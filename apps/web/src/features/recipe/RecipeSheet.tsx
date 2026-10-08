"use client";

import { useId, useMemo, useState, type FormEvent } from "react";
import { ApiError, parseRecipe, type ParsedRow, type ParseRecipeResponse } from "@/api/client";
import {
  BottomSheet,
  Button,
  IconInfo,
  SegmentedControl,
  Stepper,
  Tag,
  type SegmentOption,
} from "@/components/ui";
import { MAX_SERVINGS, MIN_SERVINGS, scaleRows, unresolvedRow } from "./scale";
import styles from "./Recipe.module.css";

type Mode = "text" | "url";

const MODES: SegmentOption<Mode>[] = [
  { value: "text", label: "הדבקת טקסט" },
  { value: "url", label: "קישור למתכון" },
];

export type RecipeSheetProps = {
  open: boolean;
  onClose: () => void;
  /** Adds the scaled rows (and the unmatched lines as "not found" rows) to the list. */
  onAdd: (rows: ParsedRow[], info: { title: string; servings: number | null }) => void;
};

function errorText(err: unknown, mode: Mode): string {
  if (err instanceof ApiError) {
    return mode === "url"
      ? "לא הצלחנו לקרוא את המתכון מהקישור הזה. אפשר להדביק את הטקסט של המתכון במקום."
      : "לא הצלחנו לקרוא את המתכון. נסי להדביק רק את רשימת המצרכים, שורה לכל מצרך.";
  }
  return "לא הצלחנו להתחבר לשרת. בדקי את החיבור ונסי שוב.";
}

/**
 * Recipe to list (issue #71, UI half): paste a recipe or a link, `POST /parse-recipe` reads it into
 * `/parse-list` rows, the person picks the number of servings (quantities scale here, no request),
 * and the rows join the list, where the normal confirmation for uncertain matches takes over.
 */
export function RecipeSheet({ open, onClose, onAdd }: RecipeSheetProps) {
  const fieldId = useId();
  const [mode, setMode] = useState<Mode>("text");
  const [text, setText] = useState("");
  const [link, setLink] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recipe, setRecipe] = useState<ParseRecipeResponse | null>(null);
  const [servings, setServings] = useState(4);

  const scaled = useMemo(
    // A recipe whose yield is unknown (servings null) cannot be scaled: its quantities stay as read.
    () =>
      recipe
        ? recipe.servings
          ? scaleRows(recipe.items, recipe.servings, servings)
          : recipe.items
        : [],
    [recipe, servings],
  );

  function close() {
    setRecipe(null);
    setError(null);
    onClose();
  }

  async function read(e?: FormEvent) {
    e?.preventDefault();
    if (loading) return;
    const value = (mode === "text" ? text : link).trim();
    if (!value) {
      setError(mode === "text" ? "הדביקי את המתכון או את רשימת המצרכים." : "הדביקי קישור למתכון.");
      return;
    }
    if (mode === "url" && !/^https?:\/\/\S+$/iu.test(value)) {
      setError("הקישור צריך להתחיל ב-https://");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await parseRecipe(mode === "text" ? { text: value } : { url: value });
      if (res.items.length === 0 && res.unresolved.length === 0) {
        setError("לא מצאנו מצרכים במתכון הזה. נסי להדביק רק את רשימת המצרכים.");
        return;
      }
      setRecipe(res);
      setServings(Math.min(MAX_SERVINGS, Math.max(MIN_SERVINGS, res.servings ?? 4)));
    } catch (err) {
      setError(errorText(err, mode));
    } finally {
      setLoading(false);
    }
  }

  function add() {
    if (!recipe) return;
    const rows = [...scaled, ...recipe.unresolved.map(unresolvedRow)];
    onAdd(rows, { title: recipe.title ?? "מתכון", servings: recipe.servings ? servings : null });
    setRecipe(null);
    setError(null);
    setText("");
    setLink("");
  }

  const count = recipe ? recipe.items.length + recipe.unresolved.length : 0;

  return (
    <BottomSheet open={open} onClose={close} eyebrow="הוספה ממתכון" title="מתכון לרשימה">
      {recipe ? (
        <div className={styles.body}>
          <h3 className={styles.recipeTitle} data-testid="recipe-title">
            {recipe.title ?? "מתכון"}
          </h3>
          {recipe.servings ? (
            <div className={styles.servingsRow}>
              <span className={styles.label}>למי מכינים?</span>
              <Stepper
                label="מנות"
                unit="מנות"
                value={servings}
                min={MIN_SERVINGS}
                max={MAX_SERVINGS}
                onChange={setServings}
              />
            </div>
          ) : (
            <p className={styles.hint} data-testid="recipe-no-servings">
              לא כתוב במתכון לכמה מנות הוא מיועד, ולכן הכמויות הן כפי שנקראו ואי אפשר לשנות מנות.
            </p>
          )}
          <ul className={styles.items} aria-label="מצרכים" data-testid="recipe-items">
            {scaled.map((row, i) => (
              <li key={`${row.input_text}-${i}`} className={styles.item} data-testid="recipe-item">
                <span className={styles.qty}>
                  <span dir="ltr">{row.quantity}</span>
                  {row.is_weighed || row.unit === "kg" ? " ק״ג" : ""}
                </span>
                <span className={styles.itemName}>
                  {row.canonical?.display_name_he ?? row.input_text}
                </span>
                {row.needs_confirmation ? <Tag variant="unverified">לאישור</Tag> : null}
              </li>
            ))}
          </ul>
          {recipe.unresolved.length > 0 ? (
            <div data-testid="recipe-unresolved">
              <p className={styles.legend}>לא זיהינו ({recipe.unresolved.length})</p>
              <ul className={styles.unresolved}>
                {recipe.unresolved.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              <p className={styles.hint}>
                השורות האלה יתווספו לקבוצה &quot;לא זוהו&quot; ברשימה, ושם אפשר לערוך אותן או להסיר.
              </p>
            </div>
          ) : null}
          <p className={styles.hint}>
            הכמויות מתעדכנות לפי מספר המנות. פריטים שלא בטוחים בהם יופיעו ברשימה לאישור שלך.
          </p>
          <div className={styles.footer}>
            <Button variant="outline" onClick={() => setRecipe(null)}>
              חזרה
            </Button>
            <Button onClick={add} disabled={count === 0} data-testid="recipe-add">
              הוסיפי {count} פריטים לרשימה
            </Button>
          </div>
        </div>
      ) : (
        <form className={styles.body} onSubmit={(e) => void read(e)} noValidate>
          <SegmentedControl
            label="מקור המתכון"
            value={mode}
            onChange={(v) => {
              setMode(v);
              setError(null);
            }}
            options={MODES}
          />
          <div className={styles.field}>
            <label htmlFor={fieldId} className={styles.label}>
              {mode === "text" ? "המתכון או רשימת המצרכים" : "קישור למתכון"}
            </label>
            {mode === "text" ? (
              <textarea
                id={fieldId}
                className={styles.input}
                value={text}
                placeholder={"פסטה ברוטב עגבניות\n500 גרם פסטה\n2 רסק עגבניות\nשמן זית"}
                onChange={(e) => setText(e.target.value)}
                aria-describedby={error ? `${fieldId}-error` : undefined}
              />
            ) : (
              <input
                id={fieldId}
                className={styles.input}
                type="url"
                inputMode="url"
                dir="ltr"
                autoComplete="off"
                value={link}
                placeholder="https://"
                onChange={(e) => setLink(e.target.value)}
                aria-describedby={error ? `${fieldId}-error` : undefined}
              />
            )}
          </div>
          {mode === "url" ? (
            <p className={styles.hint}>
              הקישור נשלח לשרת שלנו כדי לקרוא את המתכון, ולא נשמר. אם הקריאה לא מצליחה, אפשר להדביק
              את הטקסט.
            </p>
          ) : null}
          {error ? (
            <p id={`${fieldId}-error`} className={styles.callout} role="alert">
              <IconInfo size={16} />
              {error}
            </p>
          ) : null}
          <div className={styles.footer}>
            <Button variant="outline" onClick={close}>
              ביטול
            </Button>
            <Button type="submit" disabled={loading} data-testid="recipe-read">
              {loading ? "קוראת את המתכון…" : "קראי את המתכון"}
            </Button>
          </div>
        </form>
      )}
    </BottomSheet>
  );
}

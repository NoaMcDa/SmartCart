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
import { useT } from "@/i18n/LocaleProvider";
import { recipeMessages, type RecipeMessageKey } from "@/i18n/messages/recipe";
import { MAX_SERVINGS, MIN_SERVINGS, scaleRows, unresolvedRow } from "./scale";
import styles from "./Recipe.module.css";

type Mode = "text" | "url";

export type RecipeSheetProps = {
  open: boolean;
  onClose: () => void;
  /** Adds the scaled rows (and the unmatched lines as "not found" rows) to the list. */
  onAdd: (rows: ParsedRow[], info: { title: string; servings: number | null }) => void;
};

/** The message key for a failed read; the sheet translates it, so it follows the language. */
function errorKey(err: unknown, mode: Mode): RecipeMessageKey {
  if (err instanceof ApiError) return mode === "url" ? "errUrlRead" : "errTextRead";
  return "errConnect";
}

/**
 * Recipe to list (issue #71, UI half): paste a recipe or a link, `POST /parse-recipe` reads it into
 * `/parse-list` rows, the person picks the number of servings (quantities scale here, no request),
 * and the rows join the list, where the normal confirmation for uncertain matches takes over.
 */
export function RecipeSheet({ open, onClose, onAdd }: RecipeSheetProps) {
  const t = useT(recipeMessages);
  const fieldId = useId();
  const modes: SegmentOption<Mode>[] = [
    { value: "text", label: t("modeText") },
    { value: "url", label: t("modeUrl") },
  ];
  const [mode, setMode] = useState<Mode>("text");
  const [text, setText] = useState("");
  const [link, setLink] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<RecipeMessageKey | null>(null);
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
      setError(mode === "text" ? "errPasteRecipe" : "errPasteLink");
      return;
    }
    if (mode === "url" && !/^https?:\/\/\S+$/iu.test(value)) {
      setError("errLinkHttps");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await parseRecipe(mode === "text" ? { text: value } : { url: value });
      if (res.items.length === 0 && res.unresolved.length === 0) {
        setError("errNoIngredients");
        return;
      }
      setRecipe(res);
      setServings(Math.min(MAX_SERVINGS, Math.max(MIN_SERVINGS, res.servings ?? 4)));
    } catch (err) {
      setError(errorKey(err, mode));
    } finally {
      setLoading(false);
    }
  }

  function add() {
    if (!recipe) return;
    const rows = [...scaled, ...recipe.unresolved.map(unresolvedRow)];
    onAdd(rows, {
      title: recipe.title ?? t("recipe"),
      servings: recipe.servings ? servings : null,
    });
    setRecipe(null);
    setError(null);
    setText("");
    setLink("");
  }

  const count = recipe ? recipe.items.length + recipe.unresolved.length : 0;

  return (
    <BottomSheet open={open} onClose={close} eyebrow={t("eyebrow")} title={t("title")}>
      {recipe ? (
        <div className={styles.body}>
          <h3 className={styles.recipeTitle} data-testid="recipe-title">
            {recipe.title ?? t("recipe")}
          </h3>
          {recipe.servings ? (
            <div className={styles.servingsRow}>
              <span className={styles.label}>{t("servingsWho")}</span>
              <Stepper
                label={t("servingsLabel")}
                unit={t("servingsUnit")}
                value={servings}
                min={MIN_SERVINGS}
                max={MAX_SERVINGS}
                onChange={setServings}
              />
            </div>
          ) : (
            <p className={styles.hint} data-testid="recipe-no-servings">
              {t("noServings")}
            </p>
          )}
          <ul className={styles.items} aria-label={t("ingredients")} data-testid="recipe-items">
            {scaled.map((row, i) => (
              <li key={`${row.input_text}-${i}`} className={styles.item} data-testid="recipe-item">
                <span className={styles.qty}>
                  <span dir="ltr">{row.quantity}</span>
                  {row.is_weighed || row.unit === "kg" ? t("kgSuffix") : ""}
                </span>
                <span className={styles.itemName}>
                  {row.canonical?.display_name_he ?? row.input_text}
                </span>
                {row.needs_confirmation ? <Tag variant="unverified">{t("toConfirm")}</Tag> : null}
              </li>
            ))}
          </ul>
          {recipe.unresolved.length > 0 ? (
            <div data-testid="recipe-unresolved">
              <p className={styles.legend}>
                {t("unresolved", { count: recipe.unresolved.length })}
              </p>
              <ul className={styles.unresolved}>
                {recipe.unresolved.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              <p className={styles.hint}>{t("unresolvedHint")}</p>
            </div>
          ) : null}
          <p className={styles.hint}>{t("scaleHint")}</p>
          <div className={styles.footer}>
            <Button variant="outline" onClick={() => setRecipe(null)}>
              {t("back")}
            </Button>
            <Button onClick={add} disabled={count === 0} data-testid="recipe-add">
              {t("addItems", { count })}
            </Button>
          </div>
        </div>
      ) : (
        <form className={styles.body} onSubmit={(e) => void read(e)} noValidate>
          <SegmentedControl
            label={t("sourceLabel")}
            value={mode}
            onChange={(v) => {
              setMode(v);
              setError(null);
            }}
            options={modes}
          />
          <div className={styles.field}>
            <label htmlFor={fieldId} className={styles.label}>
              {mode === "text" ? t("fieldText") : t("fieldUrl")}
            </label>
            {mode === "text" ? (
              <textarea
                id={fieldId}
                className={styles.input}
                value={text}
                placeholder={t("placeholderText")}
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
          {mode === "url" ? <p className={styles.hint}>{t("urlHint")}</p> : null}
          {error ? (
            <p id={`${fieldId}-error`} className={styles.callout} role="alert">
              <IconInfo size={16} />
              {t(error)}
            </p>
          ) : null}
          <div className={styles.footer}>
            <Button variant="outline" onClick={close}>
              {t("cancel")}
            </Button>
            <Button type="submit" disabled={loading} data-testid="recipe-read">
              {loading ? t("reading") : t("read")}
            </Button>
          </div>
        </form>
      )}
    </BottomSheet>
  );
}

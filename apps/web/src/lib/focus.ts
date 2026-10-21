/**
 * Focus after the control that had it leaves the page. Removing a row, or answering a question that
 * then disappears, destroys the focused button; the browser then puts focus on `<body>` and a
 * keyboard or screen reader user has to start again from the top of the page. Call `rescueFocus`
 * from the click handler, before or just after the state change: one animation frame later, once
 * the page has re-rendered, it moves focus to a neighbor of the removed row (or to `fallback`,
 * or to the page's `[data-focus-fallback]` element) unless focus is already somewhere sensible.
 */

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export type RescueFocusOptions = {
  /** The row the trigger sits in (its closest match). Default: the closest `li`. */
  row?: string;
  /** Try the neighbor rows first. False when the row stays and only part of it goes. */
  neighbors?: boolean;
  /** Where focus goes when there is no neighbor. Default: the page's `[data-focus-fallback]`. */
  fallback?: () => HTMLElement | null;
};

function focusIsLost(): boolean {
  const active = document.activeElement;
  return !active || active === document.body || !document.body.contains(active);
}

export function rescueFocus(from: Element | null, options: RescueFocusOptions = {}): void {
  if (typeof document === "undefined") return;
  const { row = "li", neighbors = true, fallback } = options;
  const rowEl = from?.closest<HTMLElement>(row) ?? null;
  // Read now: after the re-render the removed row has no parent to ask.
  const next = neighbors ? rowEl?.nextElementSibling : null;
  const previous = neighbors ? rowEl?.previousElementSibling : null;
  window.requestAnimationFrame(() => {
    if (!focusIsLost()) return;
    for (const sibling of [next, previous]) {
      if (sibling?.isConnected) {
        const target = sibling.querySelector<HTMLElement>(FOCUSABLE);
        if (target) {
          target.focus();
          return;
        }
      }
    }
    const spot = fallback?.() ?? document.querySelector<HTMLElement>("[data-focus-fallback]");
    spot?.focus();
  });
}

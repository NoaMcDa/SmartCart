export type ThemePreference = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

/** localStorage key for the user's manual choice. Absent or "system" = follow the OS. */
export const THEME_STORAGE_KEY = "sc-theme";

/**
 * Browser UI color (`<meta name="theme-color">`), per theme. Matches --sc-surface, which is the
 * header background, so the status bar blends into the top bar.
 */
export const THEME_COLOR: Record<ResolvedTheme, string> = {
  light: "#FFFFFF",
  dark: "#1F1F1D",
};

export function isThemePreference(v: unknown): v is ThemePreference {
  return v === "system" || v === "light" || v === "dark";
}

/**
 * Inline script for <head>, run before first paint so there is no flash of the wrong theme.
 * Keep it dependency-free and wrapped in try/catch (storage can throw in private mode).
 */
export const THEME_INIT_SCRIPT = `(function(){try{var d=document.documentElement,p=null;try{p=localStorage.getItem(${JSON.stringify(
  THEME_STORAGE_KEY,
)})}catch(e){}var dark=p==="dark"||(p!=="light"&&window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches);var t=dark?"dark":"light";d.setAttribute("data-theme",t);if(p==="light"||p==="dark"){var c=t==="dark"?${JSON.stringify(
  THEME_COLOR.dark,
)}:${JSON.stringify(THEME_COLOR.light)};var m=document.querySelectorAll('meta[name="theme-color"]');for(var i=0;i<m.length;i++){m[i].setAttribute("data-sc-original",m[i].getAttribute("content")||"");m[i].setAttribute("content",c)}}}catch(e){}})();`;

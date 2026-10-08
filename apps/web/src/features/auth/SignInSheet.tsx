"use client";

import { useId, useState, type FormEvent } from "react";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Button } from "@/components/ui/Button";
import controls from "@/features/profile/controls/controls.module.css";
import { formatRich } from "@/i18n/format";
import { useT } from "@/i18n/LocaleProvider";
import { authMessages } from "@/i18n/messages/auth";
import { loadSupabase } from "./supabaseClient";

type Step = "email" | "code";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export type SignInSheetProps = {
  open: boolean;
  /** Whether Supabase is configured. When not, the sheet only explains. */
  configured: boolean;
  onClose: () => void;
  onSignedIn: () => void;
};

/**
 * Email one-time-code sign-in (Supabase Auth). Step 1 asks for the email and sends the code; step
 * 2 takes the code and verifies it. supabase-js stores the session. No passwords, no third-party
 * identity providers.
 */
export function SignInSheet({ open, configured, onClose, onSignedIn }: SignInSheetProps) {
  const t = useT(authMessages);
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const emailId = useId();
  const codeId = useId();

  function close() {
    setStep("email");
    setCode("");
    setError(null);
    onClose();
  }

  async function sendCode(e: FormEvent) {
    e.preventDefault();
    const supabase = await loadSupabase();
    if (!supabase) return;
    if (!EMAIL_RE.test(email.trim())) {
      setError(t("errorEmailInvalid"));
      return;
    }
    setBusy(true);
    setError(null);
    const { error: err } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { shouldCreateUser: true },
    });
    setBusy(false);
    if (err) {
      setError(t("errorSendFailed"));
      return;
    }
    setStep("code");
  }

  async function verify(e: FormEvent) {
    e.preventDefault();
    const supabase = await loadSupabase();
    if (!supabase) return;
    if (!/^\d{6,10}$/.test(code.trim())) {
      setError(t("errorCodeFormat"));
      return;
    }
    setBusy(true);
    setError(null);
    const { error: err } = await supabase.auth.verifyOtp({
      email: email.trim(),
      token: code.trim(),
      type: "email",
    });
    setBusy(false);
    if (err) {
      setError(t("errorCodeWrong"));
      return;
    }
    setStep("email");
    setCode("");
    onSignedIn();
  }

  return (
    <BottomSheet open={open} onClose={close} title={t("title")} eyebrow={t("eyebrow")}>
      {!configured ? (
        <p className={controls.hint} data-testid="auth-unavailable">
          {t("unavailable")}
        </p>
      ) : step === "email" ? (
        <form onSubmit={sendCode} className={controls.stack} noValidate>
          <p className={controls.hint}>{t("emailHint")}</p>
          <div className={controls.field}>
            <label htmlFor={emailId} className={controls.label}>
              {t("emailLabel")}
            </label>
            <input
              id={emailId}
              type="email"
              inputMode="email"
              autoComplete="email"
              dir="ltr"
              className={controls.input}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          {error ? (
            <p className={controls.error} role="alert">
              {error}
            </p>
          ) : null}
          <Button type="submit" block disabled={busy}>
            {busy ? t("sending") : t("sendCode")}
          </Button>
        </form>
      ) : (
        <form onSubmit={verify} className={controls.stack} noValidate>
          <p className={controls.hint}>
            {formatRich(t("codeSentTo"), { email: <span dir="ltr">{email.trim()}</span> })}
          </p>
          <div className={controls.field}>
            <label htmlFor={codeId} className={controls.label}>
              {t("codeLabel")}
            </label>
            <input
              id={codeId}
              inputMode="numeric"
              autoComplete="one-time-code"
              dir="ltr"
              className={controls.input}
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </div>
          {error ? (
            <p className={controls.error} role="alert">
              {error}
            </p>
          ) : null}
          <Button type="submit" block disabled={busy}>
            {busy ? t("verifying") : t("verify")}
          </Button>
          <Button variant="ghost" onClick={() => setStep("email")}>
            {t("changeEmail")}
          </Button>
        </form>
      )}
    </BottomSheet>
  );
}

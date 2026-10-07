import { AppShell } from "@/components/shell/AppShell";
import { Button } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <AppShell>
      <div style={{ display: "flex", flexDirection: "column", gap: 16, alignItems: "flex-start" }}>
        <h1 style={{ fontSize: 24, fontWeight: 700 }}>הדף לא נמצא</h1>
        <p style={{ color: "var(--sc-muted)" }}>אולי הקישור ישן. אפשר לחזור לרשימה ולהמשיך משם.</p>
        <Button href="/">חזרה לרשימה</Button>
      </div>
    </AppShell>
  );
}

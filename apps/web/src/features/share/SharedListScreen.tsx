"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useState, type FormEvent } from "react";
import { createList, search, type CanonicalRef, type ListMember } from "@/api/client";
import { Button, Card, FlexChip, Skeleton, Stepper } from "@/components/ui";
import { IconClose, IconInfo } from "@/components/ui/icons";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { useAuth } from "@/features/auth/AuthProvider";
import controls from "@/features/profile/controls/controls.module.css";
import { useList } from "@/state/list";
import type { SharedItem } from "./listSync";
import { ROLE_LABEL, ShareSheet, shareError } from "./ShareSheet";
import { localListToServer, readRegistry, rememberJoined, setOwnedListId } from "./sharedLists";
import { useSharedList } from "./useSharedList";
import styles from "./Share.module.css";

export function memberLabel(m: ListMember): string {
  if (m.is_owner) return "הבעלים של הרשימה";
  if (!m.user_id) return "הזמנה ממתינה";
  return "חברה ברשימה";
}

function Members({ members }: { members: ListMember[] }) {
  if (members.length === 0) return null;
  return (
    <Card as="section" aria-labelledby="members-heading">
      <h2 id="members-heading" className={styles.sectionTitle}>
        מי ברשימה
      </h2>
      <ul className={styles.members} data-testid="members">
        {members.map((m, i) => (
          <li key={`${m.user_id ?? "invite"}-${i}`} data-testid="member">
            <span className={styles.memberName}>{memberLabel(m)}</span>
            <span className={styles.memberRole}>
              {m.is_owner ? "בעלים" : ROLE_LABEL[m.role]}
              {m.user_id || m.is_owner ? null : " · עדיין לא הצטרפה"}
            </span>
          </li>
        ))}
      </ul>
      <p className={controls.hint}>
        חברים רואים רק את הרשימה. המיקום וההעדפות של כל אחת נשארים אצלה.
      </p>
    </Card>
  );
}

function AddItem({ onAdd }: { onAdd: (c: CanonicalRef) => void }) {
  const [text, setText] = useState("");
  const [hits, setHits] = useState<CanonicalRef[] | null>(null);
  const [busy, setBusy] = useState(false);
  const id = useId();

  async function find(e: FormEvent) {
    e.preventDefault();
    const q = text.trim();
    if (!q) return;
    setBusy(true);
    try {
      const res = await search(q, 5);
      setHits(res.hits.map((h) => h.canonical));
    } catch {
      setHits([]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={find} className={controls.stack} noValidate>
      <div className={controls.field}>
        <label htmlFor={id} className={controls.label}>
          הוספת פריט לרשימה המשותפת
        </label>
        <div className={styles.row}>
          <input
            id={id}
            className={controls.input}
            value={text}
            placeholder="למשל: חלב"
            onChange={(e) => setText(e.target.value)}
          />
          <Button type="submit" variant="outline" size="sm" disabled={busy}>
            חיפוש
          </Button>
        </div>
      </div>
      {hits !== null ? (
        hits.length === 0 ? (
          <p className={controls.hint}>לא מצאנו מוצר כזה. נסי ניסוח אחר.</p>
        ) : (
          <ul className={styles.hits} aria-label="תוצאות חיפוש">
            {hits.map((h) => (
              <li key={h.canonical_id}>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    onAdd(h);
                    setHits(null);
                    setText("");
                  }}
                >
                  הוספי: {h.display_name_he}
                </Button>
              </li>
            ))}
          </ul>
        )
      ) : null}
    </form>
  );
}

function ItemRow({
  item,
  onQuantity,
  onRemove,
}: {
  item: SharedItem;
  onQuantity: (q: number) => void;
  onRemove: () => void;
}) {
  return (
    <li className={styles.item} data-testid="shared-item">
      <div className={styles.itemMain}>
        <span className={styles.itemName}>{item.name}</span>
        <FlexChip level={item.flexLevel} size="sm" />
      </div>
      <Stepper value={item.quantity} onChange={onQuantity} min={1} label={item.name} />
      <Button
        variant="ghost"
        size="sm"
        onClick={onRemove}
        aria-label={`הסרת ${item.name} מהרשימה המשותפת`}
        iconStart={<IconClose size={16} />}
      >
        הסרה
      </Button>
    </li>
  );
}

function SharedListView({ listId }: { listId: number }) {
  const list = useSharedList(listId);
  const [sheet, setSheet] = useState(false);

  if (list.status === "loading") {
    return (
      <Card aria-busy="true" aria-label="טוענת את הרשימה" data-testid="shared-loading">
        <Skeleton width="50%" height={22} />
        <Skeleton height={44} />
        <Skeleton height={44} />
      </Card>
    );
  }
  if (list.status !== "ready") {
    const text =
      list.status === "not-found"
        ? "הרשימה לא נמצאה, או שאין לך גישה אליה."
        : list.status === "forbidden"
          ? "צריך להתחבר עם החשבון שהוזמן כדי לראות את הרשימה."
          : "לא הצלחנו לטעון את הרשימה. בדקי את החיבור ונסי שוב.";
    return (
      <Card role="alert" data-testid="shared-error">
        <p>{text}</p>
        <Button variant="outline" size="sm" onClick={() => void list.reload()}>
          נסי שוב
        </Button>
      </Card>
    );
  }

  return (
    <>
      <div className={styles.head}>
        <p className={styles.listName} data-testid="shared-name">
          {list.name}
        </p>
        <p className={styles.sync} data-testid="sync-state" data-mode={list.mode}>
          {list.mode === "realtime"
            ? list.live
              ? "מתעדכן בזמן אמת"
              : "מתחברת לעדכונים בזמן אמת…"
            : "מתעדכן כל כמה שניות"}
        </p>
        <Button onClick={() => setSheet(true)}>הזמנת בני משפחה</Button>
      </div>

      <div role="status" aria-live="polite">
        {list.message ? (
          <p className={styles.note} data-testid="shared-message">
            <IconInfo size={15} /> {list.message}
          </p>
        ) : null}
      </div>

      <Card as="section" aria-labelledby="items-heading" padding="none">
        <h2 id="items-heading" className={styles.itemsTitle}>
          פריטים ברשימה (<span dir="ltr">{list.items.length}</span>)
        </h2>
        {list.items.length === 0 ? (
          <p className={styles.empty}>הרשימה ריקה. הוסיפי פריט וכולם יראו אותו.</p>
        ) : (
          <ul className={styles.items} data-testid="shared-items">
            {list.items.map((it) => (
              <ItemRow
                key={it.id}
                item={it}
                onQuantity={(q) => void list.setQuantity(it.id, q)}
                onRemove={() => void list.remove(it.id)}
              />
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <AddItem onAdd={(c) => void list.add(c)} />
      </Card>

      <Members members={list.members} />

      <ShareSheet
        open={sheet}
        onClose={() => setSheet(false)}
        listId={listId}
        onInvited={() => void list.refreshMembers()}
      />
    </>
  );
}

/** `/lists/mine/share`: turn this device's list into a shared one (once), then open it. */
function MineGate() {
  const router = useRouter();
  const auth = useAuth();
  const { state, hydrated } = useList();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const needsSignIn = auth.configured && auth.status !== "loading" && auth.status !== "signed-in";

  useEffect(() => {
    const owned = readRegistry().ownedListId;
    if (owned !== null) router.replace(`/lists/${owned}/share`);
  }, [router]);

  const shareable = state.items.filter((i) => i.canonical && !i.notFound);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      ensureApiAuth();
      const created = await createList(localListToServer(state.name, state.items));
      setOwnedListId(created.id);
      rememberJoined({ id: created.id, name: created.name });
      router.replace(`/lists/${created.id}/share`);
    } catch (err) {
      setError(shareError(err));
      setBusy(false);
    }
  }

  if (!hydrated) return <Skeleton height={120} />;
  return (
    <Card as="section" aria-labelledby="mine-heading" data-testid="share-mine">
      <h2 id="mine-heading" className={styles.sectionTitle}>
        שיתוף הרשימה שלך
      </h2>
      {shareable.length === 0 ? (
        <>
          <p>הרשימה ריקה, ואין מה לשתף עדיין. הוסיפי פריטים ואז חזרי לכאן.</p>
          <Button href="/" variant="outline" size="sm">
            לבניית הרשימה
          </Button>
        </>
      ) : (
        <>
          <p>
            ניצור עותק משותף של &quot;{state.name}&quot; (<span dir="ltr">{shareable.length}</span>{" "}
            פריטים). מי שתזמיני תוכל לראות ולערוך אותו, ושינויים יופיעו אצל כולן. הרשימה שלך במכשיר
            נשארת כמו שהיא.
          </p>
          {needsSignIn ? (
            <Button onClick={auth.openSignIn}>התחברות</Button>
          ) : (
            <Button onClick={() => void start()} disabled={busy}>
              {busy ? "יוצרת…" : "יצירת רשימה משותפת"}
            </Button>
          )}
        </>
      )}
      {error ? (
        <p className={controls.error} role="alert">
          {error}
        </p>
      ) : null}
    </Card>
  );
}

export function SharedListScreen({ listId }: { listId: number | "mine" }) {
  return (
    <div className={styles.page}>
      {listId === "mine" ? (
        <MineGate />
      ) : (
        <>
          <SharedListView listId={listId} />
          <p className={styles.footnote}>
            <Link href="/">חזרה לרשימה שלי</Link>
          </p>
        </>
      )}
    </div>
  );
}

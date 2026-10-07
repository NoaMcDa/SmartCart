"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useState, type FormEvent } from "react";
import {
  createList,
  search,
  sharedWithMe,
  type CanonicalRef,
  type ListMember,
  type ShoppingList,
} from "@/api/client";
import { Button, Card, FlexChip, Skeleton, Stepper } from "@/components/ui";
import { IconClock, IconClose, IconInfo } from "@/components/ui/icons";
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

function Members({
  members,
  canManage,
  onRemove,
  onRevoke,
}: {
  members: ListMember[];
  /** Only the owner can remove members and cancel invites. */
  canManage: boolean;
  onRemove: (member: ListMember) => void;
  onRevoke: (invite: ListMember) => void;
}) {
  if (members.length === 0) return null;
  return (
    <Card as="section" aria-labelledby="members-heading">
      <h2 id="members-heading" className={styles.sectionTitle}>
        מי ברשימה
      </h2>
      <ul className={styles.members} data-testid="members">
        {members.map((m, i) => {
          const pending = !m.user_id && !m.is_owner;
          return (
            <li
              key={m.share_id != null ? `share-${m.share_id}` : `${m.user_id ?? "invite"}-${i}`}
              data-testid="member"
            >
              <span className={styles.memberName}>{memberLabel(m)}</span>
              <span className={styles.memberRole}>
                {m.is_owner ? "בעלים" : ROLE_LABEL[m.role]}
                {pending ? " · עדיין לא הצטרפה" : null}
              </span>
              {canManage && m.user_id && !m.is_owner ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onRemove(m)}
                  aria-label={`הסרת חברה מהרשימה (${ROLE_LABEL[m.role]})`}
                >
                  הסרה מהרשימה
                </Button>
              ) : null}
              {canManage && pending && m.share_id != null ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onRevoke(m)}
                  aria-label={`ביטול הזמנה ממתינה (${ROLE_LABEL[m.role]})`}
                >
                  ביטול ההזמנה
                </Button>
              ) : null}
            </li>
          );
        })}
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
  onChecked,
  onRemove,
}: {
  item: SharedItem;
  onQuantity: (q: number) => void;
  onChecked: (checked: boolean) => void;
  onRemove: () => void;
}) {
  return (
    <li className={styles.item} data-testid="shared-item" data-checked={item.checked}>
      <label className={styles.check}>
        <input
          type="checkbox"
          checked={item.checked}
          onChange={(e) => onChecked(e.target.checked)}
          aria-label={`סימון ${item.name} כנאסף`}
        />
      </label>
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
  const canManage = readRegistry().ownedListId === listId;

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
        <div role="status" aria-live="polite">
          {list.pending > 0 ? (
            <p className={styles.pending} data-testid="pending-sync">
              <IconClock size={14} /> ממתין לסנכרון (<span dir="ltr">{list.pending}</span>)
            </p>
          ) : null}
        </div>
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
                onChecked={(checked) => void list.setChecked(it.id, checked)}
                onRemove={() => void list.remove(it.id)}
              />
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <AddItem onAdd={(c) => void list.add(c)} />
      </Card>

      <Members
        members={list.members}
        canManage={canManage}
        onRemove={(member) => void list.removeListMember(member)}
        onRevoke={(invite) => void list.revokeInvite(invite)}
      />

      <ShareSheet
        open={sheet}
        onClose={() => setSheet(false)}
        listId={listId}
        onInvited={() => void list.refreshMembers()}
      />
    </>
  );
}

/** Lists other people shared with me (`GET /me/shared-lists`), each opening its page. */
function SharedWithMe() {
  const [lists, setLists] = useState<ShoppingList[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    ensureApiAuth();
    sharedWithMe().then(
      (l) => {
        if (!cancelled) setLists(l);
      },
      () => {
        if (!cancelled) setLists([]);
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);
  if (!lists || lists.length === 0) return null;
  return (
    <Card as="section" aria-labelledby="shared-with-me-heading" data-testid="shared-with-me">
      <h2 id="shared-with-me-heading" className={styles.sectionTitle}>
        רשימות ששיתפו איתך
      </h2>
      <ul className={styles.hits}>
        {lists.map((l) => (
          <li key={l.id}>
            <Button href={`/lists/${l.id}/share`} variant="ghost" size="sm">
              {l.name}
            </Button>
          </li>
        ))}
      </ul>
    </Card>
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
        <>
          <MineGate />
          <SharedWithMe />
        </>
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

"use client";

import type { Plan } from "@/api/client";
import { HandoffAction } from "./HandoffAction";

/**
 * The handoff action for every store of a plan card. Reads only the store's chain and the items
 * assigned to it: no price, saving or ranking field (tests/unit/handoff-independence.test.ts).
 */
export function PlanHandoff({ plan }: { plan: Plan }) {
  return (
    <>
      {plan.stores.map(({ store, item_ids }) => (
        <HandoffAction
          key={store.store_id}
          store={store}
          items={store.items.filter((i) => item_ids.includes(i.item_id))}
        />
      ))}
    </>
  );
}

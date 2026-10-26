import type { HomeAssistant } from './ha-types';

export type Band = 'green' | 'orange' | 'red' | 'unknown';
export type ProduceType = 'vegetable' | 'fruit';
export type ResolveAction = 'confirm' | 'wrong' | 'change' | 'ignore' | 'no_season';

export interface ItemRow {
  key: string;
  name: string;
  type: ProduceType;
  months: number[];
  residues: number | null;
  band: Band;
  in_season: boolean;
}

export interface Credit {
  label: string;
  organisations: string[];
  url: string;
  note: string;
}

export interface ItemsResponse {
  month: number;
  data_as_of: string;
  rows: ItemRow[];
  credits: Record<string, Credit>;
  provisional_cutoffs: ProduceType[];
}

export interface RecipeRow {
  slug: string;
  name: string;
  in_season: number;
  total: number;
}

export interface MealieStatus {
  mealie_configured: boolean;
  mealie_ok: boolean;
}

export interface QueueEntry {
  ingredient_key: string;
  text: string;
  current_item_key: string | null;
  suggestions: string[];
}

export interface ItemOption {
  key: string;
  name: string;
  type: ProduceType;
}

function call<T>(hass: HomeAssistant, type: string, data: Record<string, unknown> = {}): Promise<T> {
  return hass.connection.sendMessagePromise<T>({ type: `seasonal_groceries/${type}`, ...data });
}

export function getItems(
  hass: HomeAssistant,
  produceType: ProduceType,
  mode: 'now' | 'calendar',
  maxRows?: number,
): Promise<ItemsResponse> {
  return call(hass, 'items', { produce_type: produceType, mode, ...(maxRows ? { max_rows: maxRows } : {}) });
}

export function getRecipes(hass: HomeAssistant, limit?: number): Promise<{ recipes: RecipeRow[] } & MealieStatus> {
  return call(hass, 'recipes', limit ? { limit } : {});
}

export function getReviewQueue(hass: HomeAssistant): Promise<{ entries: QueueEntry[] } & MealieStatus> {
  return call(hass, 'review_queue');
}

export async function getItemOptions(hass: HomeAssistant): Promise<ItemOption[]> {
  return (await call<{ options: ItemOption[] }>(hass, 'item_options')).options;
}

export async function resolveEntry(
  hass: HomeAssistant,
  ingredientKey: string,
  action: ResolveAction,
  itemKey?: string,
): Promise<void> {
  await call(hass, 'review_resolve', {
    ingredient_key: ingredientKey,
    action,
    ...(itemKey ? { item_key: itemKey } : {}),
  });
}

/**
 * Calls `onUpdate` whenever the integration's data changed; resolves to an unsubscribe function.
 * Uses the integration's own subscribe command, which every user may call (bus events are admin-only).
 */
export async function subscribeUpdates(hass: HomeAssistant, onUpdate: () => void): Promise<() => void> {
  const unsubscribe = await hass.connection.subscribeMessage(() => onUpdate(), {
    type: 'seasonal_groceries/subscribe',
  });
  return () => {
    // HA rejects with "Subscription not found" if the socket reconnected (or the
    // subscription was already dropped) before we unsubscribe — nothing to clean up then.
    try {
      Promise.resolve(unsubscribe()).catch(() => {});
    } catch {
      /* already gone */
    }
  };
}

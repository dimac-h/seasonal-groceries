/** Minimal HA frontend types for what this integration's frontend actually uses. */

export type UnsubscribeFunc = () => void;

export interface Connection {
  sendMessagePromise<T>(message: Record<string, unknown>): Promise<T>;
  subscribeEvents<T>(callback: (ev: T) => void, eventType: string): Promise<UnsubscribeFunc>;
}

export interface HomeAssistant {
  connection: Connection;
  /** The user's language, e.g. "nl" or "en-GB". */
  language: string;
  user?: { is_admin: boolean };
}

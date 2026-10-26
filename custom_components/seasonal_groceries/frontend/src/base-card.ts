import { LitElement } from 'lit';
import { property, state } from 'lit/decorators.js';
import { subscribeUpdates } from './api';
import { translator } from './i18n';
import type { Translate } from './i18n';
import type { HomeAssistant } from './ha-types';

declare global {
  interface Window {
    customCards?: unknown[];
  }
}

/**
 * Shared behaviour of the cards: load data once `hass` arrives, reload whenever the
 * integration announces an update (new month, corrected match, new recipes), and
 * stop listening when the card leaves the page.
 */
export abstract class SeasonalCard extends LitElement {
  @property({ attribute: false }) hass!: HomeAssistant;
  @state() protected _failed = false;

  private _unsubscribe?: () => void;
  private _starting = false;

  /** Fetch whatever the card shows into its own state. Throw on failure. */
  protected abstract load(): Promise<void>;

  protected get t(): Translate {
    return translator(this.hass?.language);
  }

  connectedCallback(): void {
    super.connectedCallback();
    if (this.hass) void this._start();
  }

  updated(changed: Map<string, unknown>): void {
    if (changed.has('hass') && this.hass) void this._start();
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._unsubscribe?.();
    this._unsubscribe = undefined;
  }

  protected async _refresh(): Promise<void> {
    try {
      await this.load();
      this._failed = false;
    } catch {
      this._failed = true;
    }
  }

  private async _start(): Promise<void> {
    if (this._unsubscribe || this._starting) return;
    this._starting = true;
    try {
      await this._refresh();
      const unsubscribe = await subscribeUpdates(this.hass, () => void this._refresh());
      if (this.isConnected) this._unsubscribe = unsubscribe;
      else unsubscribe(); // removed from the DOM while subscribing
    } catch {
      this._failed = true;
    } finally {
      this._starting = false;
    }
  }
}

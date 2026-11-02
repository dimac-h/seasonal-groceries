import { html, css } from 'lit';
import { state } from 'lit/decorators.js';
import { customElement } from './register';
import { mdiSprout } from '@mdi/js';
import './credits-footer';
import './now-card-editor';
import { getItems } from './api';
import type { ItemsResponse, ProduceType } from './api';
import { SeasonalCard } from './base-card';
import { monthName } from './i18n';
import { bandColor, bandLabel } from './pesticide';
import { sharedStyles } from './styles';

export interface NowCardConfig {
  type: string;
  title?: string;
  produce_type: ProduceType;
  hide_unknown?: boolean;
}

@customElement('seasonal-groceries-now-card')
export class NowCard extends SeasonalCard {
  static styles = [
    sharedStyles,
    css`
      ha-alert {
        display: block;
        margin-block-end: var(--ha-space-4, 16px);
      }
    `,
  ];

  @state() private _config: NowCardConfig = { type: 'custom:seasonal-groceries-now-card', produce_type: 'vegetable' };
  @state() private _items?: ItemsResponse;

  setConfig(config: NowCardConfig): void {
    if (!config) throw new Error('Invalid configuration');
    if (config.produce_type !== 'vegetable' && config.produce_type !== 'fruit') {
      throw new Error('produce_type must be "vegetable" or "fruit"');
    }
    // An old `max_recipes` key from before the recipes moved to their own card is ignored.
    this._config = { ...config };
    if (this.hass) void this._refresh();
  }

  protected async load(): Promise<void> {
    this._items = await getItems(this.hass, this._config.produce_type, 'now', {
      hideUnknown: this._config.hide_unknown,
    });
  }

  getCardSize(): number {
    return 2 + Math.ceil((this._items?.rows.length ?? 5) / 2);
  }

  getGridOptions() {
    return { columns: 6, rows: 'auto', min_columns: 3, min_rows: 2 };
  }

  static getConfigElement(): HTMLElement {
    return document.createElement('seasonal-groceries-now-card-editor');
  }

  static getStubConfig(): NowCardConfig {
    return { type: 'custom:seasonal-groceries-now-card', produce_type: 'vegetable' };
  }

  private _renderItems() {
    const rows = this._items?.rows ?? [];
    if (!rows.length) return html`<div class="empty">${this.t('now.empty')}</div>`;
    return rows.map(
      row => html`
        <div class="row">
          <span class="name">${row.name}</span>
          <span class="band">
            <span class="dot" style="background:${bandColor(row.band)}"></span>${bandLabel(row.band, this.t)}
          </span>
        </div>
      `,
    );
  }

  render() {
    const type = this._config.produce_type;
    const title = this._config.title ?? `${this.t('now.title')} · ${this.t(`common.${type}`)}`;
    return html`
      <ha-card>
        <div class="header">
          <ha-svg-icon .path=${mdiSprout}></ha-svg-icon>
          <span>${title}</span>
          ${this._items
            ? html`<span class="subtitle">${monthName(this._items.month, this.hass?.language)}</span>`
            : ''}
        </div>
        ${this._failed ? html`<ha-alert alert-type="error">${this.t('common.error')}</ha-alert>` : ''}
        ${this._items ? this._renderItems() : html`<div class="muted">${this.t('common.loading')}</div>`}
        ${this._items
          ? html`<sg-credits-footer
              .credits=${this._items.credits}
              .dataAsOf=${this._items.data_as_of}
              .language=${this.hass?.language ?? 'en'}
            ></sg-credits-footer>`
          : ''}
      </ha-card>
    `;
  }
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'seasonal-groceries-now-card',
  name: 'Seasonal Groceries: in season now',
  description: 'Fruit or vegetables in season this month',
  preview: true,
  documentationURL: 'https://github.com/dimac-h/seasonal-groceries',
});

declare global {
  interface HTMLElementTagNameMap {
    'seasonal-groceries-now-card': NowCard;
  }
}

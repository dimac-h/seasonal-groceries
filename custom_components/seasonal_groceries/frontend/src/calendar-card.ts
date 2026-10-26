import { html, css } from 'lit';
import { state } from 'lit/decorators.js';
import { customElement } from './register';
import { mdiCalendarMonth } from '@mdi/js';
import './calendar-card-editor';
import './credits-footer';
import { getItems } from './api';
import type { ItemsResponse, ProduceType } from './api';
import { SeasonalCard } from './base-card';
import { monthInitial } from './i18n';
import { bandColor, bandLabel } from './pesticide';
import { sharedStyles } from './styles';

export interface CalendarCardConfig {
  type: string;
  title?: string;
  produce_type: ProduceType;
  max_rows?: number;
}

export const DEFAULT_MAX_ROWS = 15;
const MONTHS = Array.from({ length: 12 }, (_, index) => index + 1);

@customElement('seasonal-groceries-calendar-card')
export class CalendarCard extends SeasonalCard {
  static styles = [
    sharedStyles,
    css`
      .grid {
        display: grid;
        grid-template-columns: minmax(0, 1fr) repeat(12, minmax(8px, 12px));
        align-items: center;
        gap: var(--ha-space-3, 12px) 2px;
      }
      .head {
        text-align: center;
        font-size: 11px;
        color: var(--secondary-text-color);
      }
      .head.current {
        color: var(--primary-color);
        font-weight: 700;
      }
      .item {
        display: flex;
        flex-direction: column;
        min-width: 0;
        color: var(--primary-text-color);
      }
      .item .line {
        display: flex;
        align-items: center;
        gap: var(--ha-space-2, 8px);
        min-width: 0;
      }
      .item .label {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .item .unknown {
        margin-inline-start: calc(10px + var(--ha-space-2, 8px));
        font-size: 11px;
        color: var(--secondary-text-color);
      }
      .cell {
        height: 16px;
        border-radius: 3px;
        background: var(--divider-color);
        opacity: 0.5;
      }
      .cell.on {
        background: var(--primary-color);
        opacity: 0.9;
      }
      .cell.current {
        outline: 1px solid var(--primary-text-color);
        outline-offset: 1px;
        opacity: 1;
      }
    `,
  ];

  @state() private _config: CalendarCardConfig = {
    type: 'custom:seasonal-groceries-calendar-card',
    produce_type: 'vegetable',
  };
  @state() private _items?: ItemsResponse;

  setConfig(config: CalendarCardConfig): void {
    if (!config) throw new Error('Invalid configuration');
    if (config.produce_type !== 'vegetable' && config.produce_type !== 'fruit') {
      throw new Error('produce_type must be "vegetable" or "fruit"');
    }
    this._config = { max_rows: DEFAULT_MAX_ROWS, ...config };
    if (this.hass) void this._refresh();
  }

  protected async load(): Promise<void> {
    this._items = await getItems(
      this.hass,
      this._config.produce_type,
      'calendar',
      this._config.max_rows ?? DEFAULT_MAX_ROWS,
    );
  }

  getCardSize(): number {
    return 2 + Math.ceil((this._config.max_rows ?? DEFAULT_MAX_ROWS) * 0.6);
  }

  static getConfigElement(): HTMLElement {
    return document.createElement('seasonal-groceries-calendar-card-editor');
  }

  static getStubConfig(): CalendarCardConfig {
    return { type: 'custom:seasonal-groceries-calendar-card', produce_type: 'vegetable', max_rows: DEFAULT_MAX_ROWS };
  }

  private _renderGrid(items: ItemsResponse) {
    const language = this.hass?.language;
    return html`
      <div class="grid">
        <span></span>
        ${MONTHS.map(
          month => html`<span class="head ${month === items.month ? 'current' : ''}">${monthInitial(month, language)}</span>`,
        )}
        ${items.rows.map(
          row => html`
            <div class="item">
              <div class="line">
                <span
                  class="dot"
                  style="background:${bandColor(row.band)}"
                  title=${bandLabel(row.band, this.t)}
                ></span>
                <span class="label">${row.name}</span>
              </div>
              ${row.band === 'unknown' ? html`<span class="unknown">${bandLabel('unknown', this.t)}</span>` : ''}
            </div>
            ${MONTHS.map(
              month => html`<span
                class="cell ${row.months.includes(month) ? 'on' : ''} ${month === items.month ? 'current' : ''}"
              ></span>`,
            )}
          `,
        )}
      </div>
    `;
  }

  render() {
    const type = this._config.produce_type;
    const title = this._config.title ?? `${this.t('calendar.title')} · ${this.t(`common.${type}`)}`;
    return html`
      <ha-card>
        <div class="header">
          <ha-svg-icon .path=${mdiCalendarMonth}></ha-svg-icon>
          <span>${title}</span>
        </div>
        ${this._failed ? html`<ha-alert alert-type="error">${this.t('common.error')}</ha-alert>` : ''}
        ${!this._items
          ? html`<div class="muted">${this.t('common.loading')}</div>`
          : this._items.rows.length
            ? this._renderGrid(this._items)
            : html`<div class="empty">${this.t('calendar.empty')}</div>`}
        ${this._items
          ? html`<sg-credits-footer
              .credits=${this._items.credits}
              .dataAsOf=${this._items.data_as_of}
              .provisional=${this._items.provisional_cutoffs.filter(p => p === type)}
              .language=${this.hass?.language ?? 'en'}
            ></sg-credits-footer>`
          : ''}
      </ha-card>
    `;
  }
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'seasonal-groceries-calendar-card',
  name: 'Seasonal Groceries: year calendar',
  description: 'Which fruit or vegetables are in season in which month, with pesticide levels',
  preview: true,
  documentationURL: 'https://github.com/dimac-h/seasonal-groceries',
});

declare global {
  interface HTMLElementTagNameMap {
    'seasonal-groceries-calendar-card': CalendarCard;
  }
}

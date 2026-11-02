import { html, css } from 'lit';
import { state } from 'lit/decorators.js';
import { customElement } from './register';
import { mdiCalendarMonth } from '@mdi/js';
import './calendar-card-editor';
import './credits-footer';
import { getItems } from './api';
import type { ItemsResponse, ProduceType } from './api';
import { SeasonalCard } from './base-card';
import { monthInitial, monthShort } from './i18n';
import { bandColor, bandLabel } from './pesticide';
import { sharedStyles } from './styles';

export interface CalendarCardConfig {
  type: string;
  title?: string;
  produce_type: ProduceType;
  max_rows?: number;
  hide_unknown?: boolean;
}

export const DEFAULT_MAX_ROWS = 15;
/** Collapses a list of in-season months into [first, last] runs of consecutive months. */
export function seasonRuns(months: number[]): Array<[number, number]> {
  const runs: Array<[number, number]> = [];
  for (const month of [...months].sort((a, b) => a - b)) {
    const last = runs[runs.length - 1];
    if (last && month === last[1] + 1) last[1] = month;
    else if (!last || month > last[1]) runs.push([month, month]);
  }
  return runs;
}

const MONTHS = Array.from({ length: 12 }, (_, index) => index + 1);

@customElement('seasonal-groceries-calendar-card')
export class CalendarCard extends SeasonalCard {
  static styles = [
    sharedStyles,
    css`
      :host {
        /* Scale the month cells with the card's own width so wide dashboards use the space. */
        container-type: inline-size;
      }
      .grid {
        position: relative;
        display: grid;
        grid-template-columns: minmax(100px, 4fr) minmax(96px, 12fr);
        align-items: stretch;
      }
      .months,
      .bars {
        display: grid;
        grid-template-columns: repeat(12, minmax(0, 1fr));
      }
      .head {
        padding-block: var(--ha-space-2, 8px);
        text-align: center;
        font-size: 11px;
        color: var(--secondary-text-color);
      }
      .head.current {
        color: var(--primary-color);
        font-weight: 700;
      }
      .short {
        display: none;
      }
      .item,
      .track {
        position: relative;
        padding-block: var(--ha-space-2, 8px);
        border-block-start: 1px solid var(--divider-color);
      }
      .item {
        display: flex;
        flex-direction: column;
        justify-content: center;
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
      .track {
        display: flex;
        align-items: center;
      }
      .bars {
        position: relative;
        flex: 1;
        align-items: center;
        height: 14px;
      }
      /* The months outside the season are only a faint line, so the bars carry the data. */
      .bars::before {
        content: '';
        position: absolute;
        inset-inline: 0;
        top: 50%;
        height: 2px;
        margin-block-start: -1px;
        border-radius: 1px;
        background: var(--divider-color);
        opacity: 0.6;
      }
      .bar {
        position: relative;
        height: 100%;
        margin-inline: 1px;
        border-radius: 7px;
        background: var(--primary-color);
        opacity: 0.9;
      }
      /* Highlights the current month: a subtle column behind the header and every row. */
      .overlay {
        position: absolute;
        grid-column: 2;
        inset: 0;
        display: grid;
        grid-template-columns: repeat(12, minmax(0, 1fr));
        pointer-events: none;
      }
      .overlay span {
        border-inline: 1px solid color-mix(in srgb, var(--primary-color) 40%, transparent);
        border-radius: 6px;
        background: color-mix(in srgb, var(--primary-color) 10%, transparent);
      }
      @container (min-width: 600px) {
        .head {
          font-size: 14px;
        }
        .head .initial {
          display: none;
        }
        .head .short {
          display: inline;
        }
        .item,
        .track {
          padding-block: var(--ha-space-3, 12px);
        }
        .bars {
          height: 18px;
        }
        .bar {
          border-radius: 9px;
        }
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
    this._items = await getItems(this.hass, this._config.produce_type, 'calendar', {
      maxRows: this._config.max_rows ?? DEFAULT_MAX_ROWS,
      hideUnknown: this._config.hide_unknown,
    });
  }

  getGridOptions() {
    return { columns: 12, rows: 'auto', min_columns: 6, min_rows: 2 };
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
        <div class="overlay"><span style="grid-column:${items.month}"></span></div>
        <span></span>
        <div class="months">
          ${MONTHS.map(
            month => html`<span class="head ${month === items.month ? 'current' : ''}"
              ><span class="initial">${monthInitial(month, language)}</span
              ><span class="short">${monthShort(month, language)}</span></span
            >`,
          )}
        </div>
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
            <div class="track">
              <div class="bars">
                ${seasonRuns(row.months).map(
                  ([start, end]) => html`<span class="bar" style="grid-column:${start} / ${end + 1}"></span>`,
                )}
              </div>
            </div>
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

import { html, css } from 'lit';
import { state } from 'lit/decorators.js';
import { customElement } from './register';
import { mdiSprout } from '@mdi/js';
import './credits-footer';
import './now-card-editor';
import { getItems, getRecipes } from './api';
import type { ItemsResponse, MealieStatus, ProduceType, RecipeRow } from './api';
import { SeasonalCard } from './base-card';
import { monthName } from './i18n';
import { bandColor, bandLabel } from './pesticide';
import { sharedStyles } from './styles';

export interface NowCardConfig {
  type: string;
  title?: string;
  produce_type: ProduceType;
  max_recipes?: number;
}

export const DEFAULT_MAX_RECIPES = 5;

@customElement('seasonal-groceries-now-card')
export class NowCard extends SeasonalCard {
  static styles = [
    sharedStyles,
    css`
      .section-title {
        margin-block: var(--ha-space-4, 16px) var(--ha-space-1, 4px);
        font-weight: 500;
        color: var(--primary-text-color);
      }
      .score {
        color: var(--secondary-text-color);
        font-size: 12px;
        white-space: nowrap;
      }
      ha-alert {
        display: block;
        margin-block-end: var(--ha-space-2, 8px);
      }
    `,
  ];

  @state() private _config: NowCardConfig = { type: 'custom:seasonal-groceries-now-card', produce_type: 'vegetable' };
  @state() private _items?: ItemsResponse;
  @state() private _recipes: RecipeRow[] = [];
  @state() private _mealie: MealieStatus = { mealie_configured: false, mealie_ok: true };

  setConfig(config: NowCardConfig): void {
    if (!config) throw new Error('Invalid configuration');
    if (config.produce_type !== 'vegetable' && config.produce_type !== 'fruit') {
      throw new Error('produce_type must be "vegetable" or "fruit"');
    }
    this._config = { max_recipes: DEFAULT_MAX_RECIPES, ...config };
    if (this.hass) void this._refresh();
  }

  protected async load(): Promise<void> {
    const [items, recipes] = await Promise.all([
      getItems(this.hass, this._config.produce_type, 'now'),
      getRecipes(this.hass, this._config.max_recipes ?? DEFAULT_MAX_RECIPES),
    ]);
    this._items = items;
    this._recipes = recipes.recipes;
    this._mealie = { mealie_configured: recipes.mealie_configured, mealie_ok: recipes.mealie_ok };
  }

  getCardSize(): number {
    return 2 + Math.ceil((this._items?.rows.length ?? 5) / 2) + this._recipes.length;
  }

  static getConfigElement(): HTMLElement {
    return document.createElement('seasonal-groceries-now-card-editor');
  }

  static getStubConfig(): NowCardConfig {
    return { type: 'custom:seasonal-groceries-now-card', produce_type: 'vegetable', max_recipes: DEFAULT_MAX_RECIPES };
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

  private _renderRecipes() {
    if (!this._mealie.mealie_configured) return '';
    return html`
      <div class="section-title">${this.t('now.recipes')}</div>
      ${!this._mealie.mealie_ok
        ? html`<ha-alert alert-type="warning">${this.t('common.mealie_error')}</ha-alert>`
        : ''}
      ${this._recipes.length === 0 && this._mealie.mealie_ok
        ? html`<div class="muted">${this.t('now.no_recipes')}</div>`
        : this._recipes.map(
            recipe => html`
              <div class="row">
                <span class="name">${recipe.name}</span>
                <span class="score">
                  ${this.t('now.recipe_score', { in_season: recipe.in_season, total: recipe.total })}
                </span>
              </div>
            `,
          )}
    `;
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
        ${this._renderRecipes()}
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
  type: 'seasonal-groceries-now-card',
  name: 'Seasonal Groceries: in season now',
  description: 'Fruit or vegetables in season this month, with the most seasonal Mealie recipes',
  preview: true,
  documentationURL: 'https://github.com/dimac-h/seasonal-groceries',
});

declare global {
  interface HTMLElementTagNameMap {
    'seasonal-groceries-now-card': NowCard;
  }
}

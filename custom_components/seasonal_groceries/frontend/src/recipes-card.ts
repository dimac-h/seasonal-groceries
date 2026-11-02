import { html, css } from 'lit';
import { state } from 'lit/decorators.js';
import { customElement } from './register';
import { mdiChefHat, mdiHeart, mdiSilverwareForkKnife, mdiStar, mdiStarHalfFull, mdiStarOutline } from '@mdi/js';
import './recipes-card-editor';
import { getRecipes } from './api';
import type { MealieStatus, RecipeRow } from './api';
import { SeasonalCard } from './base-card';
import { starStates } from './rating';
import type { StarState } from './rating';
import { sharedStyles } from './styles';

export { starStates };

export interface RecipesCardConfig {
  type: string;
  title?: string;
  max_recipes?: number;
}

export const DEFAULT_MAX_RECIPES = 5;
const MAX_RECIPES_LIMIT = 20;

const STAR_ICONS: Record<StarState, string> = {
  full: mdiStar,
  half: mdiStarHalfFull,
  empty: mdiStarOutline,
};

@customElement('seasonal-groceries-recipes-card')
export class RecipesCard extends SeasonalCard {
  static styles = [
    sharedStyles,
    css`
      :host {
        /* The layout follows the card's own width, not the viewport: dashboard columns resize it. */
        container-type: inline-size;
      }
      ha-alert {
        display: block;
        margin-block-end: var(--ha-space-4, 16px);
      }
      .recipes {
        margin: 0;
        padding: 0;
        list-style: none;
      }
      .recipe {
        display: flex;
        gap: var(--ha-space-4, 16px);
        padding-block: var(--ha-space-3, 12px);
        color: var(--primary-text-color);
        text-decoration: none;
      }
      .recipe:focus-visible {
        outline: 2px solid var(--primary-color);
        outline-offset: 2px;
      }
      .media {
        position: relative;
        flex: 0 0 96px;
        align-self: flex-start;
        aspect-ratio: 1;
        overflow: hidden;
        border-radius: var(--ha-border-radius-md, 8px);
        background: var(--secondary-background-color);
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--secondary-text-color);
      }
      .media img {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
      .score {
        position: absolute;
        inset-inline-start: var(--ha-space-1, 4px);
        inset-block-end: var(--ha-space-1, 4px);
        max-width: calc(100% - 2 * var(--ha-space-1, 4px));
        padding: 2px var(--ha-space-2, 8px);
        border-radius: var(--ha-border-radius-pill, 12px);
        /* Inverse of the theme's text colour: dark on a light theme, light on a dark one. */
        background: color-mix(in srgb, var(--primary-text-color) 85%, transparent);
        color: var(--card-background-color);
        font-size: 12px;
        font-weight: 500;
        line-height: 1.4;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .body {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-1, 4px);
      }
      .title {
        display: flex;
        align-items: center;
        gap: var(--ha-space-2, 8px);
        min-width: 0;
      }
      .title .name {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-weight: 500;
      }
      .favorite {
        --mdc-icon-size: 18px;
        flex-shrink: 0;
        color: var(--red-color, var(--error-color));
      }
      .meta {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--ha-space-2, 8px);
        color: var(--secondary-text-color);
        font-size: 12px;
      }
      .stars {
        display: inline-flex;
        color: var(--warning-color);
        --mdc-icon-size: 16px;
      }
      .description {
        display: -webkit-box;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 3;
        overflow: hidden;
        overflow-wrap: anywhere;
        color: var(--secondary-text-color);
        font-size: 14px;
      }
      .tags {
        display: flex;
        flex-wrap: wrap;
        gap: var(--ha-space-1, 4px);
        margin: 0;
        padding: 0;
        list-style: none;
      }
      .tag {
        max-width: 100%;
        padding-inline: var(--ha-space-2, 8px);
        border-radius: var(--ha-border-radius-pill, 12px);
        background: var(--secondary-background-color);
        color: var(--secondary-text-color);
        font-size: 12px;
        overflow-wrap: anywhere;
      }
      @container (max-width: 420px) {
        .recipe {
          flex-direction: column;
          gap: var(--ha-space-2, 8px);
        }
        .media {
          flex: none;
          align-self: stretch;
          aspect-ratio: 16 / 9;
        }
      }
    `,
  ];

  @state() private _config: RecipesCardConfig = {
    type: 'custom:seasonal-groceries-recipes-card',
    max_recipes: DEFAULT_MAX_RECIPES,
  };
  @state() private _recipes: RecipeRow[] = [];
  @state() private _mealie?: MealieStatus;
  @state() private _brokenImages: ReadonlySet<string> = new Set();

  setConfig(config: RecipesCardConfig): void {
    if (!config) throw new Error('Invalid configuration');
    const max = config.max_recipes ?? DEFAULT_MAX_RECIPES;
    if (!Number.isInteger(max) || max < 1 || max > MAX_RECIPES_LIMIT) {
      throw new Error(`max_recipes must be a whole number from 1 to ${MAX_RECIPES_LIMIT}`);
    }
    this._config = { ...config, max_recipes: max };
    if (this.hass) void this._refresh();
  }

  protected async load(): Promise<void> {
    const response = await getRecipes(this.hass, this._config.max_recipes ?? DEFAULT_MAX_RECIPES);
    this._recipes = response.recipes;
    this._mealie = { mealie_configured: response.mealie_configured, mealie_ok: response.mealie_ok };
  }

  getCardSize(): number {
    return 1 + 2 * (this._recipes.length || (this._config.max_recipes ?? DEFAULT_MAX_RECIPES));
  }

  static getConfigElement(): HTMLElement {
    return document.createElement('seasonal-groceries-recipes-card-editor');
  }

  static getStubConfig(): RecipesCardConfig {
    return { type: 'custom:seasonal-groceries-recipes-card', max_recipes: DEFAULT_MAX_RECIPES };
  }

  private _markBroken(url: string): void {
    this._brokenImages = new Set([...this._brokenImages, url]);
  }

  private _renderImage(recipe: RecipeRow) {
    const url = recipe.image_url;
    return html`<div class="media">
      ${url && !this._brokenImages.has(url)
        ? html`<img src=${url} alt="" loading="lazy" @error=${() => this._markBroken(url)} />`
        : html`<ha-svg-icon .path=${mdiSilverwareForkKnife}></ha-svg-icon>`}
      <span class="score">${this.t('recipes.score', { in_season: recipe.in_season, total: recipe.total })}</span>
    </div>`;
  }

  private _renderRating(rating: number | null) {
    const stars = starStates(rating);
    if (!stars.length) return '';
    const label = this.t('recipes.rating', { rating: Math.min(Math.max(rating ?? 0, 0), 5) });
    return html`<span class="stars" role="img" aria-label=${label}>
      ${stars.map(state => html`<ha-svg-icon .path=${STAR_ICONS[state]}></ha-svg-icon>`)}
    </span>`;
  }

  private _renderRecipe(recipe: RecipeRow) {
    return html`
      <li>
        <a class="recipe" href=${recipe.url} target="_blank" rel="noopener noreferrer">
          ${this._renderImage(recipe)}
          <div class="body">
            <div class="title">
              <span class="name">${recipe.name}</span>
              ${recipe.favorite
                ? html`<ha-svg-icon
                    class="favorite"
                    .path=${mdiHeart}
                    role="img"
                    aria-label=${this.t('recipes.favorite')}
                  ></ha-svg-icon>`
                : ''}
            </div>
            <div class="meta">
              ${this._renderRating(recipe.rating)}
            </div>
            ${recipe.description ? html`<div class="description">${recipe.description}</div>` : ''}
            ${recipe.tags.length
              ? html`<ul class="tags">
                  ${recipe.tags.map(tag => html`<li class="tag">${tag}</li>`)}
                </ul>`
              : ''}
          </div>
        </a>
      </li>
    `;
  }

  private _renderBody() {
    const mealie = this._mealie;
    if (!mealie) return html`<div class="muted">${this.t('common.loading')}</div>`;
    if (!mealie.mealie_configured) {
      return html`<ha-alert alert-type="info">${this.t('recipes.not_configured')}</ha-alert>`;
    }
    return html`
      ${!mealie.mealie_ok ? html`<ha-alert alert-type="warning">${this.t('common.mealie_error')}</ha-alert>` : ''}
      ${this._recipes.length
        ? html`<ul class="recipes">
            ${this._recipes.map(recipe => this._renderRecipe(recipe))}
          </ul>`
        : mealie.mealie_ok
          ? html`<div class="muted">${this.t('recipes.no_recipes')}</div>`
          : ''}
    `;
  }

  render() {
    return html`
      <ha-card>
        <div class="header">
          <ha-svg-icon .path=${mdiChefHat}></ha-svg-icon>
          <span>${this._config.title ?? this.t('recipes.title')}</span>
        </div>
        ${this._failed ? html`<ha-alert alert-type="error">${this.t('common.error')}</ha-alert>` : ''}
        ${this._renderBody()}
      </ha-card>
    `;
  }
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'seasonal-groceries-recipes-card',
  name: 'Seasonal Groceries: recipes',
  description: 'The most seasonal Mealie recipes, with image, description, tags, favourite and rating',
  preview: true,
  documentationURL: 'https://github.com/dimac-h/seasonal-groceries',
});

declare global {
  interface HTMLElementTagNameMap {
    'seasonal-groceries-recipes-card': RecipesCard;
  }
}

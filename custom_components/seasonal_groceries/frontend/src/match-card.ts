import { html, css } from 'lit';
import { state } from 'lit/decorators.js';
import { customElement } from './register';
import { mdiLinkVariant } from '@mdi/js';
import './match-card-editor';
import { getItemOptions, getReviewQueue, resolveEntry } from './api';
import type { ItemOption, MealieStatus, QueueEntry, ResolveAction } from './api';
import { SeasonalCard } from './base-card';
import { sharedStyles } from './styles';

export interface MatchCardConfig {
  type: string;
  title?: string;
}

@customElement('seasonal-groceries-match-card')
export class MatchCard extends SeasonalCard {
  static styles = [
    sharedStyles,
    css`
      .question {
        color: var(--primary-text-color);
        font-size: 16px;
        margin-block-end: var(--ha-space-2, 8px);
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: var(--ha-space-3, 12px);
        margin-block-start: var(--ha-space-6, 24px);
      }
      ha-alert {
        display: block;
        margin-block-end: var(--ha-space-4, 16px);
      }
    `,
  ];

  @state() private _config: MatchCardConfig = { type: 'custom:seasonal-groceries-match-card' };
  @state() private _entries: QueueEntry[] = [];
  @state() private _options: ItemOption[] = [];
  @state() private _mealie?: MealieStatus;
  @state() private _changing = false;
  @state() private _picked = '';
  @state() private _actionFailed = false;
  // Entries whose resolve is still in flight; hidden so a refresh cannot bring them back.
  private _pending = new Set<string>();

  setConfig(config: MatchCardConfig): void {
    if (!config) throw new Error('Invalid configuration');
    this._config = config;
  }

  protected async load(): Promise<void> {
    // Fetch the item names every time: they follow the grocery language, which can change.
    const [queue, options] = await Promise.all([getReviewQueue(this.hass), getItemOptions(this.hass)]);
    this._entries = queue.entries.filter(entry => !this._pending.has(entry.ingredient_key));
    this._options = options;
    this._mealie = { mealie_configured: queue.mealie_configured, mealie_ok: queue.mealie_ok };
  }

  getGridOptions() {
    return { columns: 6, rows: 'auto', min_columns: 3, min_rows: 2 };
  }

  getCardSize(): number {
    return 4;
  }

  static getConfigElement(): HTMLElement {
    return document.createElement('seasonal-groceries-match-card-editor');
  }

  static getStubConfig(): MatchCardConfig {
    return { type: 'custom:seasonal-groceries-match-card' };
  }

  private get _isAdmin(): boolean {
    return this.hass?.user?.is_admin ?? true;
  }

  private _name(key: string | null | undefined): string | undefined {
    return key ? this._options.find(option => option.key === key)?.name : undefined;
  }

  private async _act(entry: QueueEntry, action: ResolveAction, itemKey?: string): Promise<void> {
    // Show the next entry at once; the server call (and any Mealie write-back) finishes in the background.
    const key = entry.ingredient_key;
    this._actionFailed = false;
    this._changing = false;
    this._picked = '';
    this._pending.add(key);
    this._entries = this._entries.filter(e => e.ingredient_key !== key);
    try {
      await resolveEntry(this.hass, key, action, itemKey);
    } catch {
      this._actionFailed = true;
    } finally {
      this._pending.delete(key);
      // While more actions are in flight the last one refreshes; the server also announces each change.
      if (this._pending.size === 0) await this._refresh();
    }
  }

  private _renderChange(entry: QueueEntry) {
    return html`
      <div @keydown=${(event: KeyboardEvent) => event.stopPropagation()}>
        <ha-form
          .hass=${this.hass}
          .data=${{ item: this._picked }}
          .schema=${[
            {
              name: 'item',
              selector: {
                select: {
                  mode: 'dropdown',
                  options: this._options.map(option => ({ value: option.key, label: option.name })),
                },
              },
            },
          ]}
          .computeLabel=${() => this.t('match.pick')}
          @value-changed=${(event: CustomEvent<{ value: { item?: string } }>) => {
            this._picked = event.detail.value.item ?? '';
          }}
        ></ha-form>
        <div class="actions">
          <ha-button
            appearance="filled"
            variant="brand"
            size="m"
            ?disabled=${!this._picked}
            @click=${() => this._act(entry, 'change', this._picked)}
            >${this.t('match.save')}</ha-button
          >
          <ha-button
            appearance="plain"
            variant="neutral"
            size="m"
            @click=${() => {
              this._changing = false;
            }}
            >${this.t('match.cancel')}</ha-button
          >
        </div>
      </div>
    `;
  }

  private _renderEntry(entry: QueueEntry) {
    const suggestion = this._name(entry.current_item_key ?? entry.suggestions[0]);
    const disabled = !this._isAdmin;
    return html`
      <div class="question">${this.t('match.question', { text: entry.text })}</div>
      <div class="muted">
        ${suggestion ? this.t('match.suggested', { name: suggestion }) : this.t('match.no_suggestion')}
      </div>
      ${this._changing
        ? this._renderChange(entry)
        : html`
            <div class="actions">
              <ha-button
                appearance="filled"
                variant="brand"
                size="m"
                ?disabled=${disabled || !entry.current_item_key}
                @click=${() => this._act(entry, 'confirm')}
                >${this.t('match.correct')}</ha-button
              >
              <ha-button
                appearance="plain"
                variant="neutral"
                size="m"
                ?disabled=${disabled || !entry.current_item_key}
                @click=${() => this._act(entry, 'wrong')}
                >${this.t('match.wrong')}</ha-button
              >
              <ha-button
                appearance="plain"
                variant="neutral"
                size="m"
                ?disabled=${disabled}
                @click=${() => {
                  this._changing = true;
                  this._picked = entry.current_item_key ?? '';
                }}
                >${this.t('match.change')}</ha-button
              >
              <ha-button
                appearance="plain"
                variant="neutral"
                size="m"
                ?disabled=${disabled}
                @click=${() => this._act(entry, 'no_season')}
                >${this.t('match.no_season')}</ha-button
              >
              <ha-button
                appearance="plain"
                variant="neutral"
                size="m"
                ?disabled=${disabled}
                @click=${() => this._act(entry, 'ignore')}
                >${this.t('match.ignore')}</ha-button
              >
            </div>
          `}
    `;
  }

  private _renderBody() {
    if (!this._mealie) return html`<div class="muted">${this.t('common.loading')}</div>`;
    if (!this._mealie.mealie_configured) {
      return html`<ha-alert alert-type="info">${this.t('match.not_connected')}</ha-alert>`;
    }
    return html`
      ${!this._mealie.mealie_ok
        ? html`<ha-alert alert-type="warning">${this.t('common.mealie_error')}</ha-alert>`
        : ''}
      ${!this._isAdmin ? html`<ha-alert alert-type="info">${this.t('match.admin_only')}</ha-alert>` : ''}
      ${this._entries.length
        ? this._renderEntry(this._entries[0])
        : html`<div class="empty">${this.t('match.empty')}</div>`}
    `;
  }

  render() {
    return html`
      <ha-card>
        <div class="header">
          <ha-svg-icon .path=${mdiLinkVariant}></ha-svg-icon>
          <span>${this._config.title ?? this.t('match.title')}</span>
        </div>
        ${this._failed || this._actionFailed
          ? html`<ha-alert alert-type="error">${this.t('common.error')}</ha-alert>`
          : ''}
        ${this._renderBody()}
      </ha-card>
    `;
  }
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'seasonal-groceries-match-card',
  name: 'Seasonal Groceries: match review',
  description: 'Confirm or fix how Mealie ingredients are matched to seasonal produce',
  preview: true,
  documentationURL: 'https://github.com/dimac-h/seasonal-groceries',
});

declare global {
  interface HTMLElementTagNameMap {
    'seasonal-groceries-match-card': MatchCard;
  }
}

import { LitElement, html } from 'lit';
import { property, state } from 'lit/decorators.js';
import { translator } from './i18n';
import type { Translate } from './i18n';
import type { HomeAssistant } from './ha-types';

/** Card editor built on `ha-form`: subclasses only describe the fields and their labels. */
export abstract class SeasonalEditor<C extends { type: string }> extends LitElement {
  @property({ attribute: false }) hass!: HomeAssistant;
  @state() protected _config!: C;

  protected abstract schema(t: Translate): Record<string, unknown>[];
  protected abstract labels(t: Translate): Record<string, string>;

  setConfig(config: C): void {
    this._config = config;
  }

  private _changed(event: CustomEvent<{ value: Partial<C> }>): void {
    this._config = { ...this._config, ...event.detail.value };
    this.dispatchEvent(
      new CustomEvent('config-changed', { detail: { config: this._config }, bubbles: true, composed: true }),
    );
  }

  render() {
    if (!this._config) return html``;
    const t = translator(this.hass?.language);
    const labels = this.labels(t);
    return html`
      <ha-form
        @keydown=${(event: KeyboardEvent) => event.stopPropagation()}
        .hass=${this.hass}
        .data=${this._config}
        .schema=${this.schema(t)}
        .computeLabel=${(schema: { name: string }) => labels[schema.name] ?? schema.name}
        @value-changed=${this._changed}
      ></ha-form>
    `;
  }
}

export function produceTypeSelector(t: Translate) {
  return {
    select: {
      mode: 'dropdown',
      options: [
        { value: 'vegetable', label: t('common.vegetable') },
        { value: 'fruit', label: t('common.fruit') },
      ],
    },
  };
}

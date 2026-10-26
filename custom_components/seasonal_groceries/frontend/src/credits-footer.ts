import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import type { Credit, ProduceType } from './api';
import { translator } from './i18n';

/** Footer shown on every card: who the data comes from, when, and what is provisional. */
@customElement('sg-credits-footer')
export class CreditsFooter extends LitElement {
  static styles = css`
    :host {
      display: block;
      margin-block-start: var(--ha-space-3, 12px);
      padding-block-start: var(--ha-space-2, 8px);
      border-block-start: 1px solid var(--divider-color);
      color: var(--secondary-text-color);
      font-size: 12px;
      line-height: 1.4;
    }
    a {
      color: var(--primary-color);
    }
  `;

  @property({ attribute: false }) credits: Record<string, Credit> = {};
  @property() dataAsOf = '';
  @property({ attribute: false }) provisional: ProduceType[] = [];
  @property() language = 'en';

  render() {
    const t = translator(this.language);
    const types = this.provisional.map(type => t(`common.${type}`).toLowerCase()).join(', ');
    return html`
      ${Object.values(this.credits).map(
        credit => html`<div>
          <a href=${credit.url} target="_blank" rel="noopener noreferrer">${credit.label}</a>
          · ${credit.organisations.join(', ')}
        </div>`,
      )}
      ${this.dataAsOf ? html`<div>${t('credits.data_as_of', { date: this.dataAsOf })}</div>` : ''}
      ${types ? html`<div>${t('credits.provisional', { types })}</div>` : ''}
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'sg-credits-footer': CreditsFooter;
  }
}

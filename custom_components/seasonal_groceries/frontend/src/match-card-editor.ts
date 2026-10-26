import { customElement } from './register';
import { SeasonalEditor } from './base-editor';
import type { MatchCardConfig } from './match-card';
import type { Translate } from './i18n';

@customElement('seasonal-groceries-match-card-editor')
export class MatchCardEditor extends SeasonalEditor<MatchCardConfig> {
  protected schema() {
    return [{ name: 'title', selector: { text: {} } }];
  }

  protected labels(t: Translate) {
    return { title: t('editor.title') };
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'seasonal-groceries-match-card-editor': MatchCardEditor;
  }
}

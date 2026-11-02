import { customElement } from './register';
import { SeasonalEditor, produceTypeSelector } from './base-editor';
import type { NowCardConfig } from './now-card';
import type { Translate } from './i18n';

@customElement('seasonal-groceries-now-card-editor')
export class NowCardEditor extends SeasonalEditor<NowCardConfig> {
  protected schema(t: Translate) {
    return [
      { name: 'title', selector: { text: {} } },
      { name: 'produce_type', selector: produceTypeSelector(t) },
      { name: 'hide_unknown', selector: { boolean: {} } },
    ];
  }

  protected labels(t: Translate) {
    return {
      title: t('editor.title'),
      produce_type: t('editor.produce_type'),
      hide_unknown: t('editor.hide_unknown'),
    };
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'seasonal-groceries-now-card-editor': NowCardEditor;
  }
}

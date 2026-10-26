import { customElement } from 'lit/decorators.js';
import { SeasonalEditor, produceTypeSelector } from './base-editor';
import type { CalendarCardConfig } from './calendar-card';
import type { Translate } from './i18n';

@customElement('seasonal-groceries-calendar-card-editor')
export class CalendarCardEditor extends SeasonalEditor<CalendarCardConfig> {
  protected schema(t: Translate) {
    return [
      { name: 'title', selector: { text: {} } },
      { name: 'produce_type', selector: produceTypeSelector(t) },
      { name: 'max_rows', selector: { number: { min: 1, max: 100, mode: 'box' } } },
    ];
  }

  protected labels(t: Translate) {
    return {
      title: t('editor.title'),
      produce_type: t('editor.produce_type'),
      max_rows: t('editor.max_rows'),
    };
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'seasonal-groceries-calendar-card-editor': CalendarCardEditor;
  }
}

import { customElement } from './register';
import { SeasonalEditor } from './base-editor';
import type { RecipesCardConfig } from './recipes-card';
import type { Translate } from './i18n';

@customElement('seasonal-groceries-recipes-card-editor')
export class RecipesCardEditor extends SeasonalEditor<RecipesCardConfig> {
  protected schema(_t: Translate) {
    return [
      { name: 'title', selector: { text: {} } },
      { name: 'max_recipes', selector: { number: { min: 1, max: 20, mode: 'box' } } },
    ];
  }

  protected labels(t: Translate) {
    return {
      title: t('editor.title'),
      max_recipes: t('editor.max_recipes'),
    };
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'seasonal-groceries-recipes-card-editor': RecipesCardEditor;
  }
}

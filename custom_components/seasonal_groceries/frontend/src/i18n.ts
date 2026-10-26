type Dictionary = Record<string, string>;

// Every translations/<code>.json is picked up automatically: adding a language
// means adding a file, no code changes.
const modules = import.meta.glob<{ default: Dictionary }>('./translations/*.json', { eager: true });
const dictionaries: Record<string, Dictionary> = {};
for (const [path, module] of Object.entries(modules)) {
  const code = /([^/]+)\.json$/.exec(path)?.[1];
  if (code) dictionaries[code] = module.default;
}

export type Translate = (key: string, vars?: Record<string, string | number>) => string;

/** Translator for a Home Assistant language code; unknown languages and missing keys fall back to English. */
export function translator(language: string | undefined): Translate {
  const base = (language ?? 'en').toLowerCase().split('-')[0];
  const primary = dictionaries[base] ?? dictionaries.en;
  return (key, vars = {}) => {
    const template = primary[key] ?? dictionaries.en[key] ?? key;
    return template.replace(/\{(\w+)\}/g, (match, name: string) => (name in vars ? String(vars[name]) : match));
  };
}

export function monthName(month: number, language: string | undefined): string {
  return new Intl.DateTimeFormat(language ?? 'en', { month: 'long' }).format(new Date(2000, month - 1, 1));
}

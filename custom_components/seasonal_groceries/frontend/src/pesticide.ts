import type { Band } from './api';
import type { Translate } from './i18n';

const BAND_COLORS: Record<Band, string> = {
  green: 'var(--success-color, #43a047)',
  orange: 'var(--warning-color, #ffa600)',
  red: 'var(--error-color, #db4437)',
  unknown: 'var(--disabled-text-color, #9e9e9e)',
};

export function bandColor(band: Band): string {
  return BAND_COLORS[band];
}

export function bandLabel(band: Band, t: Translate): string {
  return t(`band.${band}`);
}

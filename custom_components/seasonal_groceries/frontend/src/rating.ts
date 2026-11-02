export type StarState = 'full' | 'half' | 'empty';

const STARS = 5;

/** Five star states for a rating: clamped to 0 to 5, rounded to the nearest half star; all empty without a rating. */
export function starStates(rating: number | null): StarState[] {
  const valid = rating !== null && Number.isFinite(rating);
  const halves = valid ? Math.round(Math.min(Math.max(rating, 0), STARS) * 2) : 0;
  return Array.from({ length: STARS }, (_, index): StarState => {
    const left = halves - index * 2;
    if (left >= 2) return 'full';
    return left === 1 ? 'half' : 'empty';
  });
}

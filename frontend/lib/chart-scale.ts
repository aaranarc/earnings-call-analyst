// Rounded, data-fitted axes. No speculative values beyond chart padding.
export function chartScale(values: number[], includeZero = false) {
  const finite = values.filter(Number.isFinite);
  let low = finite.length ? Math.min(...finite) : 0;
  let high = finite.length ? Math.max(...finite) : 1;
  if (includeZero) { low = Math.min(0, low); high = Math.max(0, high); }
  if (low === high) { const pad = Math.max(Math.abs(low) * 0.05, 0.1); high += pad; if (!includeZero || low < 0) low -= pad; }
  const raw = (high - low) / 3;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map(n => n * power).find(n => n >= raw)!;
  const min = includeZero && low >= 0 ? 0 : Math.floor(low / step) * step;
  let max = Math.ceil(high / step) * step;
  if (max <= high && high > 0) max += step;
  if (Math.round((max - min) / step) < 3) max = min + step * 3;
  const ticks = Array.from({length: Math.round((max - min) / step) + 1}, (_, i) => Number((min + i * step).toPrecision(12)));
  return {min, max, ticks};
}

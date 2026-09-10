export const DEFAULT_WATERMARK_CONFIG = Object.freeze({
  text: 'HPoker',
  opacity: 0.12,
  density: 4,
  tilt: -20,
});

export const WATERMARK_LIMITS = Object.freeze({
  opacity: Object.freeze({ min: 0, max: 1 }),
  density: Object.freeze({ min: 1, max: 8 }),
  tilt: Object.freeze({ min: -45, max: 45 }),
});

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const finiteOr = (value, fallback) => {
  if (value === null || value === undefined || value === '') return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
};

export function normalizeWatermarkConfig(config = {}) {
  const source = config && typeof config === 'object' ? config : {};
  const rawText = source.text === undefined ? DEFAULT_WATERMARK_CONFIG.text : source.text;
  const rawOpacity = finiteOr(source.opacity, DEFAULT_WATERMARK_CONFIG.opacity);
  const rawDensity = finiteOr(source.density, DEFAULT_WATERMARK_CONFIG.density);
  const rawTilt = finiteOr(source.tilt, DEFAULT_WATERMARK_CONFIG.tilt);

  return {
    text: typeof rawText === 'string' ? rawText.trim() : DEFAULT_WATERMARK_CONFIG.text,
    opacity: clamp(rawOpacity, WATERMARK_LIMITS.opacity.min, WATERMARK_LIMITS.opacity.max),
    density: Math.round(clamp(rawDensity, WATERMARK_LIMITS.density.min, WATERMARK_LIMITS.density.max)),
    tilt: clamp(rawTilt, WATERMARK_LIMITS.tilt.min, WATERMARK_LIMITS.tilt.max),
  };
}

export function getWatermarkTileCount(config = {}) {
  const { density } = normalizeWatermarkConfig(config);
  return density * density;
}

export function getWatermarkStyle(config = {}) {
  const normalized = normalizeWatermarkConfig(config);
  return {
    '--watermark-opacity': normalized.opacity,
    '--watermark-density': normalized.density,
    '--watermark-tilt': `${normalized.tilt}deg`,
  };
}

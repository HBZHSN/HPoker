import assert from 'node:assert/strict';
import test from 'node:test';

import {
  DEFAULT_WATERMARK_CONFIG,
  getWatermarkGridDimensions,
  getWatermarkStyle,
  getWatermarkTileCount,
  normalizeWatermarkConfig,
} from '../watermark.js';

test('watermark normalization keeps defaults and trims text', () => {
  assert.deepEqual(
    normalizeWatermarkConfig({ text: '  内部使用  ', opacity: 0.25, density: 6, tilt: 18 }),
    { text: '内部使用', opacity: 0.25, density: 6, tilt: 18 },
  );
  assert.deepEqual(normalizeWatermarkConfig(), DEFAULT_WATERMARK_CONFIG);
});

test('watermark normalization clamps malformed numeric values', () => {
  assert.deepEqual(
    normalizeWatermarkConfig({ text: '', opacity: 4, density: 12.4, tilt: -90 }),
    { text: '', opacity: 1, density: 8, tilt: -45 },
  );
  assert.deepEqual(
    normalizeWatermarkConfig({ opacity: 'bad', density: null, tilt: undefined }),
    DEFAULT_WATERMARK_CONFIG,
  );
});

test('watermark grid count and CSS variables follow normalized density', () => {
  assert.equal(getWatermarkTileCount({ density: 3 }), 9);
  assert.deepEqual(getWatermarkStyle({ opacity: 0.4, density: 2, tilt: 12.5 }), {
    '--watermark-opacity': 0.4,
    '--watermark-columns': 2,
    '--watermark-rows': 2,
    '--watermark-tilt': '12.5deg',
  });
});

test('watermark density keeps tile proportions consistent in landscape and portrait', () => {
  const landscape = getWatermarkGridDimensions({ density: 4 }, { width: 16, height: 9 });
  const portrait = getWatermarkGridDimensions({ density: 4 }, { width: 9, height: 16 });

  assert.deepEqual(landscape, { columns: 8, rows: 4 });
  assert.deepEqual(portrait, { columns: 4, rows: 8 });
  assert.equal(getWatermarkTileCount({ density: 4 }, { width: 16, height: 9 }), 32);
  assert.equal(getWatermarkTileCount({ density: 4 }, { width: 9, height: 16 }), 32);
});

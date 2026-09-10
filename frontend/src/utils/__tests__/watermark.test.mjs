import assert from 'node:assert/strict';
import test from 'node:test';

import {
  DEFAULT_WATERMARK_CONFIG,
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
    '--watermark-density': 2,
    '--watermark-tilt': '12.5deg',
  });
});

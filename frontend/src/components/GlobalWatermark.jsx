import React from 'react';
import {
  getWatermarkStyle,
  getWatermarkTileCount,
  normalizeWatermarkConfig,
} from '../utils/watermark';

export default function GlobalWatermark({ config }) {
  const normalized = normalizeWatermarkConfig(config);
  if (!normalized.text || normalized.opacity <= 0) return null;

  return (
    <div className="global-watermark-layer" aria-hidden="true">
      <div className="global-watermark-grid" style={getWatermarkStyle(normalized)}>
        {Array.from({ length: getWatermarkTileCount(normalized) }, (_, index) => (
          <span className="global-watermark-label" key={`${normalized.text}-${index}`}>
            <span className="global-watermark-text">{normalized.text}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

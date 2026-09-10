import React, { useEffect, useState } from 'react';
import {
  getWatermarkStyle,
  getWatermarkTileCount,
  normalizeWatermarkConfig,
} from '../utils/watermark';

const getViewportSize = () => {
  if (typeof window === 'undefined') return { width: 1, height: 1 };
  return {
    width: window.innerWidth || 1,
    height: window.innerHeight || 1,
  };
};

export default function GlobalWatermark({ config }) {
  const normalized = normalizeWatermarkConfig(config);
  const [viewport, setViewport] = useState(getViewportSize);

  useEffect(() => {
    const updateViewport = () => setViewport(getViewportSize());
    window.addEventListener('resize', updateViewport);
    window.addEventListener('orientationchange', updateViewport);
    return () => {
      window.removeEventListener('resize', updateViewport);
      window.removeEventListener('orientationchange', updateViewport);
    };
  }, []);

  if (!normalized.text || normalized.opacity <= 0) return null;

  return (
    <div className="global-watermark-layer" aria-hidden="true">
      <div className="global-watermark-grid" style={getWatermarkStyle(normalized, viewport)}>
        {Array.from({ length: getWatermarkTileCount(normalized, viewport) }, (_, index) => (
          <span className="global-watermark-label" key={`${normalized.text}-${index}`}>
            <span className="global-watermark-text">{normalized.text}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

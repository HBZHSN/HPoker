import test from 'node:test';
import assert from 'node:assert/strict';
import {
  isStandaloneMode,
  isIOS,
  isMobile,
  isFullscreenActive,
  getInstallGuideType,
  initAppHeightSync,
} from '../pwa.js';

test('isStandaloneMode: correctly identifies standalone mode across platforms', () => {
  assert.equal(isStandaloneMode(null), false);

  // iOS standalone
  const mockIosWin = {
    navigator: { standalone: true },
    matchMedia: () => ({ matches: false }),
  };
  assert.equal(isStandaloneMode(mockIosWin), true);

  // Android / Desktop standalone display-mode
  const mockChromeWin = {
    navigator: { standalone: false },
    matchMedia: (query) => ({ matches: query.includes('display-mode: standalone') }),
  };
  assert.equal(isStandaloneMode(mockChromeWin), true);

  // Standard browser tab
  const mockBrowserWin = {
    navigator: { standalone: false },
    matchMedia: () => ({ matches: false }),
  };
  assert.equal(isStandaloneMode(mockBrowserWin), false);
});

test('isIOS: correctly detects iPhone, iPad, and modern iPadOS', () => {
  assert.equal(isIOS(null), false);

  // iPhone
  const iphoneNav = {
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
  };
  assert.equal(isIOS(iphoneNav), true);

  // iPadOS with MacIntel + multi-touch
  const ipadOsNav = {
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    platform: 'MacIntel',
    maxTouchPoints: 5,
  };
  assert.equal(isIOS(ipadOsNav), true);

  // Android
  const androidNav = {
    userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36',
    platform: 'Linux armv8l',
    maxTouchPoints: 5,
  };
  assert.equal(isIOS(androidNav), false);

  // Desktop Windows
  const winNav = {
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    platform: 'Win32',
    maxTouchPoints: 0,
  };
  assert.equal(isIOS(winNav), false);
});

test('isMobile: detects mobile viewport and mobile user agent', () => {
  // Small screen
  const mobileWin = { innerWidth: 414 };
  assert.equal(isMobile(mobileWin, null), true);

  // Desktop screen with Android UA
  const desktopWin = { innerWidth: 1440 };
  const androidNav = { userAgent: 'Mozilla/5.0 (Linux; Android 14)' };
  assert.equal(isMobile(desktopWin, androidNav), true);

  // Desktop screen with Desktop UA
  const desktopNav = { userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)' };
  assert.equal(isMobile(desktopWin, desktopNav), false);
});

test('isFullscreenActive: detects standard and vendor fullscreen elements', () => {
  assert.equal(isFullscreenActive(null), false);
  assert.equal(isFullscreenActive({}), false);

  // Standard
  assert.equal(isFullscreenActive({ fullscreenElement: {} }), true);

  // Webkit
  assert.equal(isFullscreenActive({ webkitFullscreenElement: {} }), true);
});

test('getInstallGuideType: prioritizes already installed, native prompt, and iOS guide', () => {
  const standaloneWin = {
    navigator: { standalone: true },
    matchMedia: () => ({ matches: false }),
  };
  assert.equal(getInstallGuideType({}, standaloneWin, false), 'already_installed');

  const browserWin = {
    navigator: { standalone: false },
    matchMedia: () => ({ matches: false }),
  };

  // Has native deferred prompt
  assert.equal(getInstallGuideType({}, browserWin, true), 'native');

  // iOS Safari
  const iosNav = {
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',
  };
  assert.equal(getInstallGuideType(iosNav, browserWin, false), 'ios');

  // Other browser without native prompt
  const genericNav = { userAgent: 'Mozilla/5.0 (Windows NT 10.0)' };
  assert.equal(getInstallGuideType(genericNav, browserWin, false), 'manual');
});

test('initAppHeightSync: sets --app-height based on window.innerHeight and listens for events', () => {
  const customProps = {};
  const mockDoc = {
    documentElement: {
      style: {
        setProperty: (key, val) => {
          customProps[key] = val;
        },
      },
    },
    addEventListener: () => {},
    removeEventListener: () => {},
  };
  const mockWin = {
    innerHeight: 844,
    addEventListener: () => {},
    removeEventListener: () => {},
  };

  const cleanup = initAppHeightSync(mockWin, mockDoc);
  assert.equal(customProps['--app-height'], '844px');
  assert.equal(typeof cleanup, 'function');
  cleanup();
});


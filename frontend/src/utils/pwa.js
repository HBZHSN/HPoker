/**
 * PWA (Progressive Web App) & Mobile Fullscreen Utilities
 */

/**
 * Register service worker if supported
 */
export function registerServiceWorker() {
  if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
    return;
  }

  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js', { scope: '/' })
      .then((registration) => {
        // Automatically activate new service worker when available
        registration.addEventListener('updatefound', () => {
          const installingWorker = registration.installing;
          if (installingWorker) {
            installingWorker.addEventListener('statechange', () => {
              if (
                installingWorker.state === 'installed' &&
                navigator.serviceWorker.controller
              ) {
                // New content is available, reload to pick up new version immediately
                console.log('[PWA] New version ready, reloading to activate...');
                window.location.reload();
              }
            });
          }
        });
      })
      .catch((error) => {
        console.warn('[PWA] Service worker registration failed:', error);
      });
  });
}

/**
 * Check whether the web app is running in standalone (installed / PWA) mode
 */
export function isStandaloneMode(win = typeof window !== 'undefined' ? window : null) {
  if (!win) return false;
  const nav = win.navigator;
  const isIosStandalone = Boolean(nav && nav.standalone);
  const isMediaStandalone = Boolean(
    win.matchMedia &&
      (win.matchMedia('(display-mode: standalone)').matches ||
        win.matchMedia('(display-mode: fullscreen)').matches)
  );
  return isIosStandalone || isMediaStandalone;
}

/**
 * Detect whether the user is on an iOS device (iPhone/iPad/iPod)
 */
export function isIOS(nav = typeof navigator !== 'undefined' ? navigator : null) {
  if (!nav) return false;
  const ua = nav.userAgent || '';
  const isIosUa = /iPad|iPhone|iPod/.test(ua) && !('MSStream' in (typeof window !== 'undefined' ? window : {}));
  // Modern iPadOS may report MacIntel with multi-touch
  const isIpadOS = nav.platform === 'MacIntel' && nav.maxTouchPoints > 1;
  return isIosUa || isIpadOS;
}

/**
 * Detect mobile screen or mobile user agent
 */
export function isMobile(
  win = typeof window !== 'undefined' ? window : null,
  nav = typeof navigator !== 'undefined' ? navigator : null
) {
  if (win && typeof win.innerWidth === 'number' && win.innerWidth <= 1024) {
    return true;
  }
  if (!nav) return false;
  const ua = nav.userAgent || '';
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua);
}

/**
 * Check if the document is currently in browser fullscreen mode
 */
export function isFullscreenActive(doc = typeof document !== 'undefined' ? document : null) {
  if (!doc) return false;
  return Boolean(
    doc.fullscreenElement ||
      doc.webkitFullscreenElement ||
      doc.mozFullScreenElement ||
      doc.msFullscreenElement
  );
}

/**
 * Toggle browser fullscreen
 */
export async function toggleFullscreen(
  doc = typeof document !== 'undefined' ? document : null,
  rootElem = typeof document !== 'undefined' ? document.documentElement : null
) {
  if (!doc || !rootElem) return false;

  try {
    if (isFullscreenActive(doc)) {
      if (doc.exitFullscreen) {
        await doc.exitFullscreen();
      } else if (doc.webkitExitFullscreen) {
        await doc.webkitExitFullscreen();
      } else if (doc.mozCancelFullScreen) {
        await doc.mozCancelFullScreen();
      } else if (doc.msExitFullscreen) {
        await doc.msExitFullscreen();
      }
      return false;
    } else {
      if (rootElem.requestFullscreen) {
        await rootElem.requestFullscreen({ navigationUI: 'hide' });
      } else if (rootElem.webkitRequestFullscreen) {
        await rootElem.webkitRequestFullscreen();
      } else if (rootElem.mozRequestFullScreen) {
        await rootElem.mozRequestFullScreen();
      } else if (rootElem.msRequestFullscreen) {
        await rootElem.msRequestFullscreen();
      }
      return true;
    }
  } catch (err) {
    console.warn('[PWA] Toggle fullscreen error:', err);
    return isFullscreenActive(doc);
  }
}

/**
 * Determine the installation guide type based on platform and prompt availability
 */
export function getInstallGuideType(nav, win, hasNativePrompt) {
  if (isStandaloneMode(win)) {
    return 'already_installed';
  }
  if (hasNativePrompt) {
    return 'native';
  }
  if (isIOS(nav)) {
    return 'ios';
  }
  return 'manual';
}

/**
 * Synchronize actual viewport height to CSS variable --app-height
 * Solves mobile browser & PWA viewport discrepancies where 100vh or 100dvh
 * leaves blank/gray bars at the bottom of the screen.
 * On iOS PWA (standalone mode), WebKit notoriously underreports innerHeight
 * due to phantom toolbar/safe-area deductions; this compensates using true
 * physical device screen boundaries.
 */
export function initAppHeightSync(
  win = typeof window !== 'undefined' ? window : null,
  doc = typeof document !== 'undefined' ? document : null
) {
  if (!win || !doc || !doc.documentElement) {
    return () => {};
  }

  const update = () => {
    let vh = win.innerHeight;
    const isIOSDevice = isIOS(win.navigator);
    const isStandalone = isStandaloneMode(win);

    // If on iOS in standalone/fullscreen mode, WebKit often reports window.innerHeight
    // reduced by safe areas or phantom toolbars. The true physical standalone viewport
    // spans the entire device screen height.
    if (isIOSDevice && isStandalone && win.screen) {
      const isLandscape = Boolean(
        (win.matchMedia && win.matchMedia('(orientation: landscape)').matches) ||
        (typeof win.orientation === 'number' && Math.abs(win.orientation) === 90) ||
        (typeof win.innerWidth === 'number' && typeof win.innerHeight === 'number' && win.innerWidth > win.innerHeight)
      );
      const screenH = isLandscape
        ? Math.min(win.screen.width, win.screen.height)
        : Math.max(win.screen.width, win.screen.height);
      if (typeof screenH === 'number' && screenH > vh) {
        vh = screenH;
      }
    } else if (win.visualViewport && typeof win.visualViewport.height === 'number') {
      vh = Math.round(win.visualViewport.height);
    }

    if (typeof vh === 'number' && vh > 0) {
      doc.documentElement.style.setProperty('--app-height', `${vh}px`);
    }

    // Attach standalone and iOS platform marker classes for deterministic CSS rules
    if (isStandalone) {
      doc.documentElement.classList.add('pwa-standalone');
    } else {
      doc.documentElement.classList.remove('pwa-standalone');
    }

    if (isIOSDevice) {
      doc.documentElement.classList.add('ios-device');
    } else {
      doc.documentElement.classList.remove('ios-device');
    }
  };

  update();
  win.addEventListener('resize', update, { passive: true });
  win.addEventListener('orientationchange', update, { passive: true });
  doc.addEventListener('fullscreenchange', update, { passive: true });
  doc.addEventListener('webkitfullscreenchange', update, { passive: true });
  if (win.visualViewport) {
    win.visualViewport.addEventListener('resize', update, { passive: true });
  }

  return () => {
    win.removeEventListener('resize', update);
    win.removeEventListener('orientationchange', update);
    doc.removeEventListener('fullscreenchange', update);
    doc.removeEventListener('webkitfullscreenchange', update);
    if (win.visualViewport) {
      win.visualViewport.removeEventListener('resize', update);
    }
  };
}


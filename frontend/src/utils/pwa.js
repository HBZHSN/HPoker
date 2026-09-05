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
                // New content is available, prompt or reload
                console.log('[PWA] New version ready.');
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

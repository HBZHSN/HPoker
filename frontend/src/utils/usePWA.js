import { useState, useEffect, useCallback } from 'react';
import {
  isStandaloneMode,
  isIOS,
  isMobile,
  isMobileDevice,
  isInAppBrowser,
  isFullscreenActive,
  toggleFullscreen,
  getInstallGuideType,
} from './pwa';

export function usePWA() {
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [isStandalone, setIsStandalone] = useState(() => isStandaloneMode());
  const [isFullscreen, setIsFullscreen] = useState(() => isFullscreenActive());
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [iosDevice, setIosDevice] = useState(() => isIOS());
  const [mobileDevice, setMobileDevice] = useState(() => isMobile());
  const [physicalMobile, setPhysicalMobile] = useState(() => isMobileDevice());
  const [inApp, setInApp] = useState(() => isInAppBrowser());

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const handleBeforeInstallPrompt = (e) => {
      // Prevent browser's default prompt to coordinate our own UI
      e.preventDefault();
      setDeferredPrompt(e);
    };

    const handleAppInstalled = () => {
      setDeferredPrompt(null);
      setIsStandalone(true);
      setIsModalOpen(false);
    };

    const handleFullscreenChange = () => {
      setIsFullscreen(isFullscreenActive());
    };

    const handleResize = () => {
      setMobileDevice(isMobile());
      setPhysicalMobile(isMobileDevice());
      setInApp(isInAppBrowser());
      setIsStandalone(isStandaloneMode());
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleAppInstalled);
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleAppInstalled);
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  const promptInstall = useCallback(async () => {
    if (deferredPrompt) {
      try {
        await deferredPrompt.prompt();
        const choice = await deferredPrompt.userChoice;
        if (choice && choice.outcome === 'accepted') {
          setIsStandalone(true);
        }
      } catch (err) {
        console.warn('[PWA] Native install prompt error:', err);
      } finally {
        setDeferredPrompt(null);
      }
    } else {
      // Open instructional guidance modal
      setIsModalOpen(true);
    }
  }, [deferredPrompt]);

  const handleToggleFullscreen = useCallback(async () => {
    const active = await toggleFullscreen();
    setIsFullscreen(active);
  }, []);

  const guideType = getInstallGuideType(
    typeof navigator !== 'undefined' ? navigator : null,
    typeof window !== 'undefined' ? window : null,
    Boolean(deferredPrompt)
  );

  return {
    isInstallable: Boolean(deferredPrompt) || (iosDevice && !isStandalone),
    hasNativePrompt: Boolean(deferredPrompt),
    isStandalone,
    isFullscreen,
    isIOS: iosDevice,
    isMobile: mobileDevice,
    isMobileDevice: physicalMobile,
    isInAppBrowser: inApp,
    isModalOpen,
    guideType,
    openInstallModal: () => setIsModalOpen(true),
    closeInstallModal: () => setIsModalOpen(false),
    promptInstall,
    toggleFullscreen: handleToggleFullscreen,
  };
}

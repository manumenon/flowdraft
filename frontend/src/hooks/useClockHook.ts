import { useEffect } from 'react';
import { gsap } from 'gsap';

declare global {
  interface Window {
    __CLOCK_CONTROLLER__?: {
      freeze: () => void;
      advance: (ms: number) => void;
      seek: (ms: number) => void;
      unfreeze: () => void;
    };
  }
}

let isFrozen = false;
let currentTime = 0; // in seconds

export function useClockHook(active: boolean = false) {
  useEffect(() => {
    if (!active) return;

    window.__CLOCK_CONTROLLER__ = {
      freeze: () => {
        isFrozen = true;
        gsap.ticker.sleep();
        currentTime = 0;
        gsap.updateRoot(currentTime);
        gsap.globalTimeline.time(0);
        gsap.globalTimeline.getChildren(true, true, true).forEach((t) => {
          t.time(0);
        });
      },
      advance: (ms: number) => {
        if (!isFrozen) {
          console.warn('Clock controller is not frozen. Call freeze() first.');
          return;
        }
        currentTime += ms / 1000;
        // Manually update all GSAP timelines and tweens
        gsap.updateRoot(currentTime);
      },
      seek: (ms: number) => {
        currentTime = ms / 1000;
        gsap.updateRoot(currentTime);
      },
      unfreeze: () => {
        isFrozen = false;
        // Resume GSAP's global ticker
        gsap.ticker.wake();
      },
    };

    return () => {
      if (window.__CLOCK_CONTROLLER__) {
        window.__CLOCK_CONTROLLER__.unfreeze();
        delete window.__CLOCK_CONTROLLER__;
      }
    };
  }, [active]);
}
export default useClockHook;

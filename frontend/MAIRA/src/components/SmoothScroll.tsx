
import Lenis from 'lenis';
import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

export default function SmoothScroll() {
    const lenisRef = useRef<Lenis | null>(null);
    const location = useLocation();

    useEffect(() => {
        // Disable Lenis on interactive app-like routes that handle their own scrolling
        if (location.pathname.startsWith('/chat') || location.pathname === '/paper-writer') {
            return;
        }

        const lenis = new Lenis({
            duration: 1.2,
            easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
            orientation: 'vertical',
            gestureOrientation: 'vertical',
            smoothWheel: true,
            touchMultiplier: 2,
        });

        lenisRef.current = lenis;

        let reqId: number;

        function raf(time: number) {
            lenis.raf(time);
            reqId = requestAnimationFrame(raf);
        }

        reqId = requestAnimationFrame(raf);

        return () => {
            lenis.destroy();
            lenisRef.current = null;
            cancelAnimationFrame(reqId);
        };
    }, [location.pathname]);

    return null;
}

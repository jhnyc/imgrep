import { useCallback, useRef, useState } from 'react';

export interface ViewportState {
  x: number;
  y: number;
  scale: number;
}

const MIN_SCALE = 0.1;
const MAX_SCALE = 10;
const WHEEL_SENSITIVITY = 0.001;

export function useCanvasPanZoom(initialScale = 1) {
  const [viewport, setViewport] = useState<ViewportState>({
    x: 0,
    y: 0,
    scale: initialScale,
  });

  const [isLocked, setIsLocked] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);
  const [isDraggingState, setIsDraggingState] = useState(false);

  const isDragging = useRef(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const viewportStart = useRef({ x: 0, y: 0 });
  const animationRef = useRef<number | null>(null);
  
  // Inertia tracking
  const velocity = useRef({ x: 0, y: 0 });
  const lastMousePos = useRef({ x: 0, y: 0 });
  const lastTimestamp = useRef(0);
  const inertiaFrameRef = useRef<number | null>(null);

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      if (isLocked) return;
      e.preventDefault();
      
      // Stop inertia on wheel
      if (inertiaFrameRef.current) {
        cancelAnimationFrame(inertiaFrameRef.current);
        inertiaFrameRef.current = null;
      }

      const bounds = (e.target as HTMLElement).getBoundingClientRect();
      const cursorX = e.clientX - bounds.left;
      const cursorY = e.clientY - bounds.top;

      const worldX = (cursorX - viewport.x) / viewport.scale;
      const worldY = (cursorY - viewport.y) / viewport.scale;

      const delta = -e.deltaY * WHEEL_SENSITIVITY;
      const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, viewport.scale * (1 + delta)));

      const newX = cursorX - worldX * newScale;
      const newY = cursorY - worldY * newScale;

      setViewport({ x: newX, y: newY, scale: newScale });
    },
    [viewport, isLocked]
  );

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (isLocked) return;
    if (e.button === 1 || e.button === 0) {
      // Stop any existing inertia or animation
      if (inertiaFrameRef.current) {
          cancelAnimationFrame(inertiaFrameRef.current);
          inertiaFrameRef.current = null;
      }
      if (animationRef.current) {
          cancelAnimationFrame(animationRef.current);
          animationRef.current = null;
      }

      isDragging.current = true;
      setIsDraggingState(true);
      dragStart.current = { x: e.clientX, y: e.clientY };
      viewportStart.current = { x: viewport.x, y: viewport.y };
      
      // Initialize velocity tracking
      lastMousePos.current = { x: e.clientX, y: e.clientY };
      lastTimestamp.current = performance.now();
      velocity.current = { x: 0, y: 0 };

      (e.target as HTMLElement).style.cursor = 'grabbing';
    }
  }, [viewport, isLocked]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging.current || isLocked) return;

    const now = performance.now();
    const dt = now - lastTimestamp.current;
    
    // Calculate new viewport position
    const dx = e.clientX - dragStart.current.x;
    const dy = e.clientY - dragStart.current.y;

    setViewport({
      ...viewport,
      x: viewportStart.current.x + dx,
      y: viewportStart.current.y + dy,
    });

    // Track velocity (pixels per millisecond)
    if (dt > 0) {
        const vx = (e.clientX - lastMousePos.current.x) / dt;
        const vy = (e.clientY - lastMousePos.current.y) / dt;
        // Simple smoothing
        velocity.current = { 
            x: vx * 0.2 + velocity.current.x * 0.8, 
            y: vy * 0.2 + velocity.current.y * 0.8 
        };
    }
    
    lastMousePos.current = { x: e.clientX, y: e.clientY };
    lastTimestamp.current = now;

  }, [viewport, isLocked]);

  const handleMouseUp = useCallback(() => {
    if (isDragging.current) {
      isDragging.current = false;
      setIsDraggingState(false);
      (document.activeElement as HTMLElement)?.blur();

      // Apply inertia if velocity is sufficient
      const v = velocity.current;
      const speed = Math.sqrt(v.x * v.x + v.y * v.y);
      
      if (speed > 0.1) {
          const friction = 0.95;
          const stopThreshold = 0.01;
          
          let currentVx = v.x * 12; // Boost velocity slightly for better feel
          let currentVy = v.y * 12;

          const step = () => {
              if (Math.abs(currentVx) < stopThreshold && Math.abs(currentVy) < stopThreshold) {
                  inertiaFrameRef.current = null;
                  return;
              }

              setViewport(prev => ({
                  ...prev,
                  x: prev.x + currentVx,
                  y: prev.y + currentVy,
              }));

              currentVx *= friction;
              currentVy *= friction;
              
              inertiaFrameRef.current = requestAnimationFrame(step);
          };
          
          inertiaFrameRef.current = requestAnimationFrame(step);
      }
    }
  }, []);

  const toggleLock = useCallback(() => {
    setIsLocked((prev) => !prev);
  }, []);

  const animateTo = useCallback((targetX: number, targetY: number, targetScale: number, duration = 400) => {
    if (animationRef.current) cancelAnimationFrame(animationRef.current);
    if (inertiaFrameRef.current) cancelAnimationFrame(inertiaFrameRef.current);

    setIsAnimating(true);
    const startTime = performance.now();
    const startX = viewport.x;
    const startY = viewport.y;
    const startScale = viewport.scale;

    const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = easeOutCubic(progress);

      const newX = startX + (targetX - startX) * eased;
      const newY = startY + (targetY - startY) * eased;
      const newScale = startScale + (targetScale - startScale) * eased;

      setViewport({ x: newX, y: newY, scale: newScale });

      if (progress < 1) {
        animationRef.current = requestAnimationFrame(animate);
      } else {
        setIsAnimating(false);
        animationRef.current = null;
      }
    };

    animationRef.current = requestAnimationFrame(animate);
  }, [viewport]);

  const centerOnPoints = useCallback((points: { x: number; y: number }[], padding = 100) => {
    if (points.length === 0) return;

    // Calculate bounding box
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const p of points) {
      minX = Math.min(minX, p.x);
      maxX = Math.max(maxX, p.x);
      minY = Math.min(minY, p.y);
      maxY = Math.max(maxY, p.y);
    }

    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    const width = maxX - minX + padding * 2;
    const height = maxY - minY + padding * 2;

    // Calculate scale to fit
    const scaleX = window.innerWidth / width;
    const scaleY = window.innerHeight / height;
    const targetScale = Math.min(Math.max(Math.min(scaleX, scaleY), MIN_SCALE), 2);

    // Calculate viewport position to center
    const targetX = window.innerWidth / 2 - centerX * targetScale;
    const targetY = window.innerHeight / 2 - centerY * targetScale;

    animateTo(targetX, targetY, targetScale);
  }, [animateTo]);

  const resetView = useCallback(() => {
    animateTo(0, 0, initialScale);
  }, [initialScale, animateTo]);

  return {
    viewport,
    setViewport,
    handleWheel,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    resetView,
    isLocked,
    toggleLock,
    isAnimating,
    isDragging: isDraggingState,
    centerOnPoints,
    animateTo,
  };
}

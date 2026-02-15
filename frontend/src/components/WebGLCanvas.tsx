
import { Viewport } from 'pixi-viewport';
import * as PIXI from 'pixi.js';
import { useEffect, useRef, useState } from 'react';
import type { ClusterNode, ImagePosition } from '../api/client';

interface WebGLCanvasProps {
    clusters: ClusterNode[];
    images: ImagePosition[];
    searchResults: number[] | null;
    explosionEnabled?: boolean;
    registerFocus?: (fn: (imageId: number, x?: number, y?: number) => void) => void;
}

export default function WebGLCanvas({
    images,
    searchResults,
    explosionEnabled = false,
    registerFocus,
}: WebGLCanvasProps) {
    const canvasRef = useRef<HTMLDivElement>(null);
    const appRef = useRef<PIXI.Application | null>(null);
    const viewportRef = useRef<Viewport | null>(null);
    const [isReady, setIsReady] = useState(false);

    useEffect(() => {
        if (!canvasRef.current) return;

        const initApp = async () => {
            const app = new PIXI.Application();
            await app.init({
                width: window.innerWidth,
                height: window.innerHeight,
                backgroundColor: 0xffffff,
                antialias: true,
                resolution: window.devicePixelRatio || 1,
                autoDensity: true,
            });

            if (!canvasRef.current) return;
            canvasRef.current.appendChild(app.canvas);
            appRef.current = app;

            const viewport = new Viewport({
                screenWidth: window.innerWidth,
                screenHeight: window.innerHeight,
                worldWidth: 10000,
                worldHeight: 10000,
                events: app.renderer.events,
            });

            app.stage.addChild(viewport);
            viewportRef.current = viewport;

            viewport
                .drag()
                .pinch()
                .wheel()
                .decelerate();

            renderContent(viewport, images, searchResults, explosionEnabled);
            setIsReady(true);
        };

        initApp();

        return () => {
            if (appRef.current) {
                appRef.current.destroy(true, { children: true, texture: true });
                appRef.current = null;
            }
        };
    }, []);

    useEffect(() => {
        const handleResize = () => {
            if (appRef.current && viewportRef.current) {
                appRef.current.renderer.resize(window.innerWidth, window.innerHeight);
                viewportRef.current.resize(window.innerWidth, window.innerHeight);
            }
        };

        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    const positionsMap = useRef<Map<number, { x: number, y: number }>>(new Map());

    useEffect(() => {
        if (registerFocus) {
            registerFocus((imageId, x, y) => {
                console.log('WebGLCanvas: focus requested for', { imageId, x, y });

                if (imageId === -1) {
                    viewportRef.current?.animate({
                        position: { x: 5000, y: 5000 },
                        scale: 0.1,
                        time: 1000,
                        ease: 'easeInOutQuad'
                    });
                    return;
                }

                let targetX = x;
                let targetY = y;

                const pos = positionsMap.current.get(imageId);
                if (pos) {
                    console.log('WebGLCanvas: found local position', pos);
                    targetX = pos.x;
                    targetY = pos.y;
                } else if (targetX !== undefined) {
                    console.log('WebGLCanvas: using fallback coordinates', { targetX, targetY });
                } else {
                    console.warn('WebGLCanvas: could not find position for image', imageId);
                }

                if (targetX !== undefined && targetY !== undefined && viewportRef.current) {
                    viewportRef.current.plugins.remove('snap');
                    viewportRef.current.snap(targetX, targetY, {
                        removeOnInterrupt: true,
                        time: 800,
                        ease: 'easeInOutQuad'
                    });

                    if (viewportRef.current.scale.x < 0.5) {
                        viewportRef.current.animate({
                            scale: 1,
                            time: 800,
                            ease: 'easeInOutQuad'
                        });
                    }
                }
            });
        }
    }, [registerFocus, isReady]);

    useEffect(() => {
        if (viewportRef.current && isReady) {
            viewportRef.current.removeChildren();
            const { positions } = renderContent(viewportRef.current, images, searchResults, explosionEnabled);
            positionsMap.current = new Map(positions.map(p => [p.id, { x: p.x, y: p.y }]));
            console.log('WebGLCanvas: updated positionsMap, size:', positionsMap.current.size);
        }
    }, [images, searchResults, explosionEnabled, isReady]);

    return <div ref={canvasRef} className="w-full h-full" />;
}

function renderContent(
    viewport: Viewport,
    images: ImagePosition[],
    searchResults: number[] | null,
    explosionEnabled: boolean
): { positions: ImagePosition[] } {
    let positions = [...images];

    if (explosionEnabled) {
        // Simple force-directed relaxation to separate overlapping images
        const iterations = 5;
        const minDistance = 110; // Card size + padding

        for (let i = 0; i < iterations; i++) {
            for (let j = 0; j < positions.length; j++) {
                for (let k = j + 1; k < positions.length; k++) {
                    const imgA = positions[j];
                    const imgB = positions[k];

                    const dx = imgB.x - imgA.x;
                    const dy = imgB.y - imgA.y;
                    const distanceSq = dx * dx + dy * dy;

                    if (distanceSq < minDistance * minDistance && distanceSq > 0) {
                        const distance = Math.sqrt(distanceSq);
                        const force = (minDistance - distance) / distance * 0.5;
                        const fx = dx * force;
                        const fy = dy * force;

                        // Push both away
                        positions[j] = { ...imgA, x: imgA.x - fx, y: imgA.y - fy };
                        positions[k] = { ...imgB, x: imgB.x + fx, y: imgB.y + fy };
                    }
                }
            }
        }
    }

    positions.forEach((img) => {
        const isDimmed = searchResults && !searchResults.includes(img.id);

        // Container for interaction and cards
        const container = new PIXI.Container();
        container.x = img.x;
        container.y = img.y;
        container.alpha = isDimmed ? 0.35 : 1;

        // Rotation based on ID for a natural look
        container.rotation = (((img.id * 137) % 5) - 2.5) * (Math.PI / 180);

        container.eventMode = 'static';
        container.cursor = 'pointer';

        // Hover scale effect
        container.on('pointerenter', () => {
            container.scale.set(1.1);
            document.body.style.cursor = 'pointer';
            // Bring to front
            viewport.addChild(container);
        });
        container.on('pointerleave', () => {
            container.scale.set(1);
            document.body.style.cursor = 'default';
        });

        // Click to open viewer
        container.on('click', (e) => {
            e.stopPropagation();
            window.dispatchEvent(new CustomEvent('open-image-viewer', { detail: { imageId: img.id } }));
        });
        container.on('tap', (e) => {
            e.stopPropagation();
            window.dispatchEvent(new CustomEvent('open-image-viewer', { detail: { imageId: img.id } }));
        });

        // Card background (white)
        const g = new PIXI.Graphics();
        g.roundRect(-50, -50, 100, 100, 8);
        g.fill(0xffffff);

        // Simple shadow
        const shadow = new PIXI.Graphics();
        shadow.roundRect(-50, -46, 100, 100, 8);
        shadow.fill({ color: 0x000000, alpha: 0.1 });

        container.addChild(shadow);
        container.addChild(g);
        viewport.addChild(container);

        // Load and render thumbnail
        if (img.thumbnail_url) {
            PIXI.Assets.load(`http://localhost:8001${img.thumbnail_url}`).then((texture) => {
                if (!container.destroyed) {
                    const sprite = new PIXI.Sprite(texture);
                    sprite.anchor.set(0.5);

                    // Fit sprite inside card with padding
                    const maxSize = 88; // 100px card - 6px padding each side
                    const scale = Math.min(maxSize / sprite.width, maxSize / sprite.height);
                    sprite.scale.set(scale);

                    container.addChild(sprite);
                }
            }).catch(() => { });
        }
    });

    return { positions };
}

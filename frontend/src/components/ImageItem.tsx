import Konva from 'konva';
import { memo, useEffect, useMemo, useRef, useState } from 'react';
import { Group, Image as KonvaImage, Rect } from 'react-konva';
import type { ImagePosition } from '../api/client';
import { useImage } from '../hooks/useImage';

interface ImageItemProps {
  image: ImagePosition;
  x: number;
  y: number;
  isDimmed: boolean;
  isLowDetail?: boolean;
}

const MAX_SIZE = 100;
const FRAME_PADDING = 6;
const CORNER_RADIUS = 10;

function ImageItem({ image, x, y, isDimmed, isLowDetail = false }: ImageItemProps) {
  // If low detail, render a simple placeholder without loading the image
  if (isLowDetail) {
    return (
      <Rect
        x={x - 20}
        y={y - 20}
        width={40}
        height={40}
        fill={isDimmed ? "#e5e7eb" : "#9ca3af"}
        cornerRadius={4}
        opacity={isDimmed ? 0.35 : 0.8}
        rotation={((image.id * 137) % 5) - 2.5}
        perfectDrawEnabled={false}
        listening={false} // Disable interaction when zoomed out
      />
    );
  }

  const [imgElement, status] = useImage(
    image.thumbnail_url ? `http://localhost:8001${image.thumbnail_url}` : null,
    'anonymous'
  );

  const [imgSize, setImgSize] = useState({ width: MAX_SIZE, height: MAX_SIZE });
  const groupRef = useRef<Konva.Group>(null);

  // Deterministic rotation based on ID to avoid re-render wobbles
  const rotation = useMemo(() => ((image.id * 137) % 5) - 2.5, [image.id]);

  useEffect(() => {
    if (status === 'loaded' && imgElement) {
      // Calculate size preserving aspect ratio
      const aspectRatio = imgElement.naturalWidth / imgElement.naturalHeight;
      let width, height;

      if (aspectRatio > 1) {
        // Landscape
        width = MAX_SIZE;
        height = MAX_SIZE / aspectRatio;
      } else {
        // Portrait or square
        height = MAX_SIZE;
        width = MAX_SIZE * aspectRatio;
      }

      setImgSize({ width, height });
    }
  }, [status, imgElement]);

  const frameWidth = imgSize.width + FRAME_PADDING * 2;
  const frameHeight = imgSize.height + FRAME_PADDING * 2;
  const error = status === 'failed';

  // Caching logic
  useEffect(() => {
    const node = groupRef.current;
    if (!node) return;

    if (status === 'loaded' || status === 'failed' || (!image.thumbnail_url && status !== 'loading')) {
      // Small timeout to ensure rendering is done before caching
      // (sometimes Konva needs a tick update for images)
      const timer = setTimeout(() => {
        try {
          if (node) {
            // Cache with pixel ratio 2 for better quality on zoom, but kept reasonable
            node.cache({
              pixelRatio: 1.5,
            });
          }
        } catch (e) {
          console.warn("Failed to cache node", e);
        }
      }, 10);

      return () => clearTimeout(timer);
    }
  }, [status, imgSize, isDimmed]);
  // We include isDimmed because it changes opacity. 
  // However, Opacity on Group is applied POST cache? 
  // Konva docs: "When you cache a node, it is drawn into an offline canvas... 
  // The cached image is then drawn onto the main canvas."
  // Group properties (x, y, rotation, opacity, scale) are applied to the cached bitmap.
  // Children properties are baked in.
  // So if we change Group opacity, we DO NOT need to re-cache!
  // But wait, the Group content is what is cached.

  const handleClick = () => {
    window.dispatchEvent(
      new CustomEvent('open-image-viewer', {
        detail: { imageId: image.id },
      })
    );
  };

  return (
    <Group
      ref={groupRef}
      x={x}
      y={y}
      rotation={rotation}
      onClick={handleClick}
      onMouseEnter={() => {
        document.body.style.cursor = 'pointer';
      }}
      onMouseLeave={() => {
        document.body.style.cursor = 'default';
      }}
      opacity={isDimmed ? 0.35 : 1}
    >
      {/* Card background with soft shadow */}
      <Rect
        x={-frameWidth / 2}
        y={-frameHeight / 2}
        width={frameWidth}
        height={frameHeight}
        fill="white"
        cornerRadius={CORNER_RADIUS}
        shadowColor="rgba(0, 0, 0, 0.15)"
        shadowBlur={15}
        shadowOffsetX={0}
        shadowOffsetY={5}
        shadowEnabled={true}
        perfectDrawEnabled={false}
      />

      {/* Image or placeholder */}
      {imgElement && status === 'loaded' ? (
        <KonvaImage
          image={imgElement}
          x={-imgSize.width / 2}
          y={-imgSize.height / 2}
          width={imgSize.width}
          height={imgSize.height}
          cornerRadius={CORNER_RADIUS - 2}
          perfectDrawEnabled={false}
        />
      ) : (
        <Rect
          x={-imgSize.width / 2}
          y={-imgSize.height / 2}
          width={imgSize.width}
          height={imgSize.height}
          fill={error ? '#fef2f2' : '#f5f5f5'}
          cornerRadius={CORNER_RADIUS - 2}
        />
      )}
    </Group>
  );
}

export default memo(ImageItem);

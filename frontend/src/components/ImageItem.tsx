import { useMemo, useRef, useState } from 'react';
import { Group, Image as KonvaImage, Rect } from 'react-konva';
import type { ImagePosition } from '../api/client';

interface ImageItemProps {
  image: ImagePosition;
  x: number;
  y: number;
  isDimmed: boolean;
}

const MAX_SIZE = 100;
const FRAME_PADDING = 6;
const CORNER_RADIUS = 10;

export default function ImageItem({ image, x, y, isDimmed }: ImageItemProps) {
  const [imgElement, setImgElement] = useState<HTMLImageElement | null>(null);
  const [imgSize, setImgSize] = useState({ width: MAX_SIZE, height: MAX_SIZE });
  const [error, setError] = useState(false);
  const imageRef = useRef<HTMLImageElement>(null);

  const rotation = useMemo(() => (Math.random() - 0.5) * 4, []);

  const [loaded, setLoaded] = useState(false);

  if (!loaded && image.thumbnail_url) {
    const img = new window.Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      // Calculate size preserving aspect ratio
      const aspectRatio = img.naturalWidth / img.naturalHeight;
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
      setImgElement(img);
      setError(false);
      setLoaded(true);
    };
    img.onerror = () => {
      setError(true);
      setLoaded(true);
    };
    img.src = `http://localhost:8001${image.thumbnail_url}`;
    imageRef.current = img;
  }

  const handleClick = () => {
    window.dispatchEvent(
      new CustomEvent('open-image-viewer', {
        detail: { imageId: image.id },
      })
    );
  };

  const frameWidth = imgSize.width + FRAME_PADDING * 2;
  const frameHeight = imgSize.height + FRAME_PADDING * 2;

  return (
    <Group
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
        shadowColor="rgba(0, 0, 0, 0.1)"
        shadowBlur={12}
        shadowOffsetX={0}
        shadowOffsetY={4}
      />

      {/* Image or placeholder */}
      {imgElement ? (
        <KonvaImage
          image={imgElement}
          x={-imgSize.width / 2}
          y={-imgSize.height / 2}
          width={imgSize.width}
          height={imgSize.height}
          cornerRadius={CORNER_RADIUS - 2}
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

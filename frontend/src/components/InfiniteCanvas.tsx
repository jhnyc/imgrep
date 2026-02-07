import { useEffect, useMemo } from 'react';
import { Circle, Group, Layer, Stage } from 'react-konva';
import type { ClusterNode as ClusterNodeType, ImagePosition } from '../api/client';
import { useCanvasPanZoom } from '../hooks/useCanvasPanZoom';
import { calculateSpiralPosition, useClusterAnimation } from '../hooks/useClusterAnimation';
import ClusterNode from './ClusterNode';
import ImageItem from './ImageItem';

interface InfiniteCanvasProps {
  clusters: ClusterNodeType[];
  images: ImagePosition[];
  searchResults: number[] | null;
  isLocked: boolean;
  onToggleLock: () => void;
  onRecenter: () => void;
  registerRecenter: (fn: () => void) => void;
  registerFocusOnImage: (fn: (imageId: number) => void) => void;
}

export default function InfiniteCanvas({
  clusters,
  images,
  searchResults,
  isLocked,
  registerRecenter,
  registerFocusOnImage,
}: InfiniteCanvasProps) {
  const {
    viewport,
    handleWheel,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    centerOnPoints,
    animateTo,
  } = useCanvasPanZoom(0.8);

  const { handleClusterHover, isClusterExpanded } = useClusterAnimation();

  // Group images by cluster
  const imagesByCluster = useMemo(() => {
    const grouped = new Map<number | null, ImagePosition[]>();

    clusters.forEach((c) => grouped.set(c.id, []));

    const noiseImages: ImagePosition[] = [];

    images.forEach((img) => {
      if (img.cluster_label === null) {
        noiseImages.push(img);
      } else {
        const clusterImages = grouped.get(img.cluster_label) || [];
        clusterImages.push(img);
        grouped.set(img.cluster_label, clusterImages);
      }
    });

    return { grouped, noiseImages };
  }, [clusters, images]);

  // Build a map of image positions for quick lookup
  const imagePositions = useMemo(() => {
    const positions = new Map<number, { x: number; y: number }>();

    // Images in clusters - use cluster position (since they're grouped there)
    clusters.forEach((cluster) => {
      const clusterImages = imagesByCluster.grouped.get(cluster.id) || [];
      clusterImages.forEach((img) => {
        positions.set(img.id, { x: cluster.x, y: cluster.y });
      });
    });

    // Noise images - calculate their actual position
    imagesByCluster.noiseImages.forEach((img, i) => {
      const angle = (i / imagesByCluster.noiseImages.length) * Math.PI * 2;
      const radius = 1800;
      positions.set(img.id, {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
      });
    });

    return positions;
  }, [clusters, imagesByCluster]);

  // Register recenter function
  useEffect(() => {
    const recenter = () => {
      const points = clusters.map(c => ({ x: c.x, y: c.y }));

      imagesByCluster.noiseImages.forEach((_, i) => {
        const angle = (i / imagesByCluster.noiseImages.length) * Math.PI * 2;
        const radius = 1800;
        points.push({
          x: Math.cos(angle) * radius,
          y: Math.sin(angle) * radius,
        });
      });

      if (points.length > 0) {
        centerOnPoints(points, 150);
      }
    };

    registerRecenter(recenter);
  }, [clusters, imagesByCluster.noiseImages, centerOnPoints, registerRecenter]);

  // Register focus on image function
  useEffect(() => {
    const focusOnImage = (imageId: number) => {
      const pos = imagePositions.get(imageId);
      if (!pos) return;

      // Center viewport on this image with a nice zoom level
      const targetScale = 1.2;
      const targetX = window.innerWidth / 2 - pos.x * targetScale;
      const targetY = window.innerHeight / 2 - pos.y * targetScale;

      animateTo(targetX, targetY, targetScale);
    };

    registerFocusOnImage(focusOnImage);
  }, [imagePositions, animateTo, registerFocusOnImage]);

  return (
    <div
      className={`w-full h-full ${isLocked ? 'cursor-not-allowed' : 'cursor-grab active:cursor-grabbing'}`}
      onWheel={isLocked ? undefined : handleWheel}
      onMouseDown={isLocked ? undefined : handleMouseDown}
      onMouseMove={isLocked ? undefined : handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <Stage
        width={window.innerWidth}
        height={window.innerHeight}
        scaleX={viewport.scale}
        scaleY={viewport.scale}
        x={viewport.x}
        y={viewport.y}
      >
        <Layer>
          {/* Draw connections between images in clusters */}
          {clusters.map((cluster) => {
            const clusterImages = imagesByCluster.grouped.get(cluster.id) || [];
            const expanded = isClusterExpanded(cluster.id);

            if (!expanded || clusterImages.length < 2) return null;

            const connections = clusterImages.map((_img, i) => {
              const pos = calculateSpiralPosition(i, clusterImages.length, cluster.x, cluster.y);
              return (
                <Circle
                  key={`connection-${cluster.id}-${i}`}
                  x={pos.x}
                  y={pos.y}
                  radius={2}
                  fill="#4b5563"
                  opacity={0.3}
                />
              );
            });

            return <Group key={`connections-${cluster.id}`}>{connections}</Group>;
          })}

          {/* Draw cluster nodes */}
          {clusters.map((cluster) => {
            const clusterImages = imagesByCluster.grouped.get(cluster.id) || [];
            const isDimmed = Boolean(
              searchResults && !clusterImages.some((img) => searchResults.includes(img.id))
            );

            return (
              <ClusterNode
                key={cluster.id}
                cluster={cluster}
                images={clusterImages}
                isExpanded={isClusterExpanded(cluster.id)}
                onHover={() => handleClusterHover(cluster.id)}
                onUnhover={() => handleClusterHover(null)}
                isDimmed={isDimmed}
              />
            );
          })}

          {/* Draw noise images (not in any cluster) */}
          {imagesByCluster.noiseImages.map((img, i) => {
            const isDimmed = Boolean(
              searchResults && !searchResults.includes(img.id)
            );
            const angle = (i / imagesByCluster.noiseImages.length) * Math.PI * 2;
            const radius = 1800;
            const x = Math.cos(angle) * radius;
            const y = Math.sin(angle) * radius;

            return (
              <ImageItem
                key={img.id}
                image={img}
                x={x}
                y={y}
                isDimmed={isDimmed}
              />
            );
          })}
        </Layer>
      </Stage>
    </div>
  );
}

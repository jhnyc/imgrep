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
  explosionEnabled?: boolean;
}

export default function InfiniteCanvas({
  clusters,
  images,
  searchResults,
  isLocked,
  onToggleLock,
  onRecenter,
  registerRecenter,
  registerFocusOnImage,
  explosionEnabled = false,
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

  const relaxedClusters = useMemo(() => {
    if (!explosionEnabled) return clusters;

    let positions = clusters.map(c => ({ ...c }));
    const iterations = 5;
    const minDistance = 300; // Cluster nodes are larger

    for (let i = 0; i < iterations; i++) {
      for (let j = 0; j < positions.length; j++) {
        for (let k = j + 1; k < positions.length; k++) {
          const cA = positions[j];
          const cB = positions[k];

          const dx = cB.x - cA.x;
          const dy = cB.y - cA.y;
          const distanceSq = dx * dx + dy * dy;

          if (distanceSq < minDistance * minDistance && distanceSq > 0) {
            const distance = Math.sqrt(distanceSq);
            const force = (minDistance - distance) / distance * 0.5;
            const fx = dx * force;
            const fy = dy * force;

            positions[j].x -= fx;
            positions[j].y -= fy;
            positions[k].x += fx;
            positions[k].y += fy;
          }
        }
      }
    }
    return positions;
  }, [clusters, explosionEnabled]);

  // Build a map of image positions for quick lookup
  const imagePositions = useMemo(() => {
    const positions = new Map<number, { x: number; y: number }>();

    // Images in clusters - use relaxed cluster position
    relaxedClusters.forEach((cluster) => {
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
  }, [relaxedClusters, imagesByCluster]);

  // Viewport Culling Calculation
  const visibleBounds = useMemo(() => {
    const buffer = 500; // Render items 500px outside viewport
    // Calculate world coordinates of the viewport
    const x = -viewport.x / viewport.scale;
    const y = -viewport.y / viewport.scale;
    const width = window.innerWidth / viewport.scale;
    const height = window.innerHeight / viewport.scale;

    return {
      minX: x - buffer,
      maxX: x + width + buffer,
      minY: y - buffer,
      maxY: y + height + buffer,
    };
  }, [viewport]);

  const isVisible = (x: number, y: number, radius = 100) => {
    return (
      x + radius > visibleBounds.minX &&
      x - radius < visibleBounds.maxX &&
      y + radius > visibleBounds.minY &&
      y - radius < visibleBounds.maxY
    );
  };

  // Register recenter function
  useEffect(() => {
    const recenter = () => {
      const points = relaxedClusters.map(c => ({ x: c.x, y: c.y }));

      // Use pre-calculated positions for noise images
      imagesByCluster.noiseImages.forEach((img) => {
        const pos = imagePositions.get(img.id);
        if (pos) points.push(pos);
      });

      if (points.length > 0) {
        centerOnPoints(points, 150);
      }
    };

    registerRecenter(recenter);
  }, [relaxedClusters, imagesByCluster.noiseImages, centerOnPoints, registerRecenter, imagePositions]);

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
          {relaxedClusters.map((cluster) => {
            // Cull invisible clusters
            if (!isVisible(cluster.x, cluster.y, 200)) return null;

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
                  perfectDrawEnabled={false}
                />
              );
            });

            return <Group key={`connections-${cluster.id}`}>{connections}</Group>;
          })}

          {/* Draw cluster nodes */}
          {relaxedClusters.map((cluster) => {
            // Cull invisible clusters
            if (!isVisible(cluster.x, cluster.y, 200)) return null;

            const clusterImages = imagesByCluster.grouped.get(cluster.id) || [];
            const isDimmed = Boolean(
              searchResults && !clusterImages.some((img) => searchResults.includes(img.id))
            );

            // LOD: Hide details when zoomed out
            const isLowDetail = viewport.scale < 0.45;

            return (
              <ClusterNode
                key={cluster.id}
                cluster={cluster}
                images={clusterImages}
                isExpanded={isClusterExpanded(cluster.id)}
                onHover={() => handleClusterHover(cluster.id)}
                onUnhover={() => handleClusterHover(null)}
                isDimmed={isDimmed}
                isLowDetail={isLowDetail}
              />
            );
          })}

          {/* Draw noise images (not in any cluster) */}
          {imagesByCluster.noiseImages.map((img) => {
            const pos = imagePositions.get(img.id);
            if (!pos) return null; // Should not happen

            // Cull invisible images
            if (!isVisible(pos.x, pos.y, 100)) return null;

            const isDimmed = Boolean(
              searchResults && !searchResults.includes(img.id)
            );

            const isLowDetail = viewport.scale < 0.45;

            return (
              <ImageItem
                key={img.id}
                image={img}
                x={pos.x}
                y={pos.y}
                isDimmed={isDimmed}
                isLowDetail={isLowDetail}
              />
            );
          })}
        </Layer>
      </Stage>
    </div>
  );
}

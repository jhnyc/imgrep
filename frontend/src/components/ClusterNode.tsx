import { useMemo } from 'react';
import { Circle, Group, Text } from 'react-konva';
import type { ClusterNode as ClusterNodeType, ImagePosition } from '../api/client';
import { calculateSpiralPosition } from '../hooks/useClusterAnimation';
import ImageItem from './ImageItem';

interface ClusterNodeProps {
  cluster: ClusterNodeType;
  images: ImagePosition[];
  isExpanded: boolean;
  onHover: () => void;
  onUnhover: () => void;
  isDimmed: boolean;
}

// Modern soft pastel colors
const CLUSTER_COLORS = [
  '#ffb3b3', '#ffd4a8', '#fff3b0', '#c7f5bd',
  '#a8e6f5', '#b3d4ff', '#d4b3ff', '#ffb3e6',
];

function getClusterColor(id: number): string {
  return CLUSTER_COLORS[id % CLUSTER_COLORS.length];
}

export default function ClusterNode({
  cluster,
  images,
  isExpanded,
  onHover,
  onUnhover,
  isDimmed,
}: ClusterNodeProps) {
  const clusterRadius = Math.max(32, Math.min(100, Math.sqrt(cluster.image_count) * 16));
  const clusterColor = getClusterColor(cluster.id);

  // Slightly darker stroke from fill
  const strokeColor = useMemo(() => {
    const hex = clusterColor.replace('#', '');
    const r = Math.max(0, parseInt(hex.slice(0, 2), 16) - 30);
    const g = Math.max(0, parseInt(hex.slice(2, 4), 16) - 30);
    const b = Math.max(0, parseInt(hex.slice(4, 6), 16) - 30);
    return `rgb(${r}, ${g}, ${b})`;
  }, [clusterColor]);

  return (
    <Group
      x={cluster.x}
      y={cluster.y}
      onMouseEnter={() => {
        onHover();
        document.body.style.cursor = 'pointer';
      }}
      onMouseLeave={() => {
        onUnhover();
        document.body.style.cursor = 'default';
      }}
    >
      {/* Clean circle - Excalidraw style */}
      <Circle
        radius={clusterRadius}
        fill={clusterColor}
        stroke={strokeColor}
        strokeWidth={1.5}
        opacity={isDimmed ? 0.25 : 0.92}
        shadowColor="rgba(0, 0, 0, 0.1)"
        shadowBlur={16}
        shadowOffsetX={0}
        shadowOffsetY={6}
      />

      {/* Image count */}
      {!isExpanded && (
        <Text
          text={cluster.image_count.toString()}
          fontSize={Math.max(16, clusterRadius * 0.45)}
          fill="#374151"
          fontFamily="system-ui, -apple-system, sans-serif"
          fontStyle="600"
          align="center"
          width={clusterRadius * 2}
          offsetX={clusterRadius}
          offsetY={clusterRadius * 0.2}
          opacity={isDimmed ? 0.35 : 1}
        />
      )}

      {/* Expanded images */}
      {isExpanded &&
        images.map((img, i) => {
          const pos = calculateSpiralPosition(i, images.length, 0, 0, clusterRadius + 50);
          return (
            <ImageItem
              key={img.id}
              image={img}
              x={pos.x}
              y={pos.y}
              isDimmed={isDimmed}
            />
          );
        })}
    </Group>
  );
}

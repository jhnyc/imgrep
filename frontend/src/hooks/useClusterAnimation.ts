import { useState, useCallback } from 'react';

export interface ClusterAnimationState {
  [clusterId: number]: {
    isExpanded: boolean;
    progress: number; // 0 to 1
  };
}

export function useClusterAnimation() {
  const [hoveredCluster, setHoveredCluster] = useState<number | null>(null);
  const [animationState, setAnimationState] = useState<ClusterAnimationState>({});

  const handleClusterHover = useCallback((clusterId: number | null) => {
    setHoveredCluster(clusterId);

    if (clusterId !== null) {
      setAnimationState(prev => ({
        ...prev,
        [clusterId]: { isExpanded: true, progress: 1 },
      }));
    } else {
      // Collapse all
      setAnimationState(prev => {
        const newState = { ...prev };
        for (const key in newState) {
          newState[key] = { ...newState[key], isExpanded: false, progress: 0 };
        }
        return newState;
      });
    }
  }, []);

  const isClusterExpanded = useCallback((clusterId: number) => {
    return animationState[clusterId]?.isExpanded ?? false;
  }, [animationState]);

  const getExpandProgress = useCallback((clusterId: number) => {
    return animationState[clusterId]?.progress ?? 0;
  }, [animationState]);

  return {
    hoveredCluster,
    setHoveredCluster,
    handleClusterHover,
    isClusterExpanded,
    getExpandProgress,
    animationState,
  };
}

// Calculate spiral position for items in a cluster
export function calculateSpiralPosition(
  index: number,
  total: number,
  centerX: number,
  centerY: number,
  maxRadius: number = 200
): { x: number; y: number } {
  if (total === 0) return { x: centerX, y: centerY };
  if (total === 1) return { x: centerX + maxRadius, y: centerY };

  // Golden angle for better distribution
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  const angle = index * goldenAngle;

  // Radius grows with sqrt to maintain density
  const radius = maxRadius * Math.sqrt(index / total);

  return {
    x: centerX + Math.cos(angle) * radius,
    y: centerY + Math.sin(angle) * radius,
  };
}

// Calculate circular position for items in a cluster
export function calculateCircularPosition(
  index: number,
  total: number,
  centerX: number,
  centerY: number,
  radius: number = 150
): { x: number; y: number } {
  if (total === 0) return { x: centerX, y: centerY };
  if (total === 1) return { x: centerX + radius, y: centerY };

  const angle = (index / total) * Math.PI * 2 - Math.PI / 2;

  return {
    x: centerX + Math.cos(angle) * radius,
    y: centerY + Math.sin(angle) * radius,
  };
}

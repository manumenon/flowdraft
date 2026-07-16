import React, { useEffect, useRef } from 'react';
import type { EdgeProps } from '@xyflow/react';
import { gsap } from 'gsap';
import { getManhattanPath, computeParallelOffset, getRoundedPath } from '../../utils/routing';

export const RoutedEdge: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data = {},
}) => {
  const packetsRef = useRef<(SVGCircleElement | null)[]>([]);
  const edgeData = data as any;
  const edgeColor = edgeData.color || '#a6adc8';
  const connectionStyle = edgeData.style || 'solid';

  // 1. Calculate path points
  const basePoints = (edgeData.points as [number, number][]) || getManhattanPath(
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition
  );

  // 2. Apply parallel offsets
  const offset = edgeData.parallelIndex !== undefined && edgeData.parallelCount !== undefined && edgeData.parallelCount > 1
    ? (edgeData.parallelIndex - (edgeData.parallelCount - 1) / 2) * 12
    : 0;

  const offsetPoints = computeParallelOffset(basePoints, offset);

  // 3. Round the corners
  const d = getRoundedPath(offsetPoints, 12);

  // 4. Packet animation using GSAP
  useEffect(() => {
    const activePackets = packetsRef.current.filter((p): p is SVGCircleElement => p !== null);
    if (activePackets.length === 0 || !d) return;

    const tweens: gsap.core.Tween[] = [];

    activePackets.forEach((packet, idx) => {
      // Set initial state
      gsap.set(packet, { offsetDistance: '0%' });

      const duration = 4.0;
      const delay = idx * (duration / activePackets.length);

      const tween = gsap.to(packet, {
        offsetDistance: '100%',
        duration: duration,
        repeat: -1,
        ease: 'none',
        delay: delay,
      });

      tweens.push(tween);
    });

    return () => {
      tweens.forEach((t) => t.kill());
    };
  }, [d]);

  // Dash array mapping
  let strokeDasharray = undefined;
  if (connectionStyle === 'dashed') {
    strokeDasharray = '6, 6';
  } else if (connectionStyle === 'dotted') {
    strokeDasharray = '2, 4';
  }

  return (
    <>
      <path
        id={id}
        className="react-flow__edge-path transition-all duration-300"
        d={d}
        fill="none"
        stroke={edgeColor}
        strokeWidth={style.strokeWidth || 2}
        strokeDasharray={strokeDasharray}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke: edgeColor,
          opacity: 0.85,
        }}
      />

      {/* Flowing packets along the path */}
      {d &&
        Array.from({ length: 3 }).map((_, idx) => (
          <circle
            key={idx}
            ref={(el) => {
              packetsRef.current[idx] = el;
            }}
            r={3.5}
            fill={edgeColor}
            style={{
              offsetPath: `path('${d}')`,
              offsetRotate: 'auto',
              pointerEvents: 'none',
            }}
          />
        ))}
    </>
  );
};

export default RoutedEdge;

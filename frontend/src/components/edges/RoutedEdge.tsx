import React, { useEffect, useRef } from 'react';
import { EdgeLabelRenderer, type EdgeProps } from '@xyflow/react';
import { gsap } from 'gsap';
import { getManhattanPath, getRoundedPath } from '../../utils/routing';

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
  selected,
}) => {
  const packetsRef = useRef<(SVGGElement | null)[]>([]);
  const edgeData = data as any;
  const edgeColor = edgeData.color || '#a6adc8';
  const connectionStyle = edgeData.style || 'solid';

  // 1. Shift source coordinates if multiple connections share the exit port
  let shiftedSourceX = sourceX;
  let shiftedSourceY = sourceY;
  if (edgeData.sourceCount > 1 && edgeData.sourceIndex !== undefined) {
    const sOffset = (edgeData.sourceIndex - (edgeData.sourceCount - 1) / 2) * 12;
    if (sourcePosition === 'top' || sourcePosition === 'bottom') {
      shiftedSourceX += sOffset;
    } else {
      shiftedSourceY += sOffset;
    }
  }

  // 2. Shift target coordinates if multiple connections share the entry port
  let shiftedTargetX = targetX;
  let shiftedTargetY = targetY;
  if (edgeData.targetCount > 1 && edgeData.targetIndex !== undefined) {
    const tOffset = (edgeData.targetIndex - (edgeData.targetCount - 1) / 2) * 12;
    if (targetPosition === 'top' || targetPosition === 'bottom') {
      shiftedTargetX += tOffset;
    } else {
      shiftedTargetY += tOffset;
    }
  }

  // 3. Compute midpoint corridor and exit port offsets for this edge
  const sourceFanOffset = edgeData.sourceCount > 1 && edgeData.sourceIndex !== undefined
    ? (edgeData.sourceIndex - (edgeData.sourceCount - 1) / 2) * 18
    : 0;

  const corridorSpacing = edgeData.corridorCount > 1
    ? Math.min(16, 60 / (edgeData.corridorCount - 1))
    : 0;

  const corridorOffset = edgeData.corridorCount > 1 && edgeData.corridorIndex !== undefined
    ? (edgeData.corridorIndex - (edgeData.corridorCount - 1) / 2) * corridorSpacing
    : 0;

  const midpointOffset = corridorOffset || sourceFanOffset;

  // 4. Calculate path points
  const basePoints = (edgeData.points as [number, number][]) || getManhattanPath(
    shiftedSourceX,
    shiftedSourceY,
    sourcePosition,
    shiftedTargetX,
    shiftedTargetY,
    targetPosition,
    midpointOffset
  );

  // 5. Round the corners directly (we bypass computeParallelOffset because anchors and midpoints are already staggered)
  const d = getRoundedPath(basePoints, 12);

  // 4. Packet animation using GSAP
  useEffect(() => {
    const activePackets = packetsRef.current.filter((p): p is SVGGElement => p !== null);
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

  // 5. Calculate middle point for label
  const midPoint = basePoints[Math.floor(basePoints.length / 2)] || [
    (sourceX + targetX) / 2,
    (sourceY + targetY) / 2,
  ];

  return (
    <>
      {/* 1. Subtle ambient glow path */}
      {d && (
        <path
          d={d}
          fill="none"
          stroke={edgeColor}
          strokeWidth={(Number(style.strokeWidth) || 2) * 3}
          className={`opacity-[0.08] blur-[2px] transition-all duration-300 ${selected ? 'opacity-[0.20]' : ''}`}
          style={{ pointerEvents: 'none' }}
        />
      )}

      {/* 2. Core connection path */}
      <path
        id={id}
        className="react-flow__edge-path transition-all duration-300"
        d={d}
        fill="none"
        stroke={selected ? '#3b82f6' : edgeColor}
        strokeWidth={selected ? (Number(style.strokeWidth) || 2) + 1 : style.strokeWidth || 2}
        strokeDasharray={strokeDasharray}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke: selected ? '#3b82f6' : edgeColor,
          opacity: 0.95,
        }}
      />

      {/* 3. Flowing glowing packets along the path */}
      {d &&
        Array.from({ length: 3 }).map((_, idx) => (
          <g
            key={idx}
            ref={(el) => {
              packetsRef.current[idx] = el;
            }}
            style={{
              offsetPath: `path('${d}')`,
              offsetRotate: 'auto',
              pointerEvents: 'none',
            }}
          >
            {/* Soft ambient aura */}
            <circle r={4} fill={edgeColor} opacity={0.2} />
            {/* Compact particle core */}
            <circle r={2} fill="#ffffff" opacity={0.9} />
          </g>
        ))}

      {/* 4. Glassmorphic Connection Label Badge */}
      {edgeData.label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${midPoint[0]}px,${midPoint[1]}px)`,
              pointerEvents: 'all',
            }}
            className="px-2 py-0.5 rounded bg-surface-1/90 border border-border-themed shadow-md text-[10px] font-bold text-text-primary uppercase tracking-widest font-mono text-center max-w-[120px] truncate select-none"
          >
            {edgeData.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
};

export default RoutedEdge;

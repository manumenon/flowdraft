import React, { useEffect, useRef } from 'react';
import { EdgeLabelRenderer, type EdgeProps } from '@xyflow/react';
import { gsap } from 'gsap';
import { getManhattanPath } from '../../utils/routing';

interface Segment {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  isHorizontal: boolean;
}

function getSegments(points: [number, number][]): Segment[] {
  const segments: Segment[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[i + 1];
    const isHorizontal = Math.abs(y1 - y2) < 0.1;
    segments.push({ x1, y1, x2, y2, isHorizontal });
  }
  return segments;
}

function getRoundedPathWithJumps(points: [number, number][], radius: number, intersections: any[]): string {
  if (points.length === 0) return '';
  if (points.length === 1) return `M ${points[0][0].toFixed(1)} ${points[0][1].toFixed(1)}`;

  const R = 6; // Arc jump radius
  let path = `M ${points[0][0].toFixed(1)} ${points[0][1].toFixed(1)}`;

  for (let i = 1; i < points.length; i++) {
    const prev = points[i - 1];
    const curr = points[i];

    const dx = curr[0] - prev[0];
    const dy = curr[1] - prev[1];
    const dist = Math.hypot(dx, dy);

    if (dist === 0) continue;

    const isHorizontal = Math.abs(dy) < 0.1;
    const segIdx = i - 1;
    const segIntersects = intersections.filter((inNode) => inNode.segIdx === segIdx);

    const isLast = i === points.length - 1;
    const next = isLast ? null : points[i + 1];
    const nextDx = next ? next[0] - curr[0] : 0;
    const nextDy = next ? next[1] - curr[1] : 0;
    const nextDist = next ? Math.hypot(nextDx, nextDy) : 0;

    const rCorner = next && nextDist > 0 ? Math.min(radius, dist / 2, nextDist / 2) : 0;

    const rPrev = i > 1 ? Math.min(radius, dist / 2, Math.hypot(prev[0] - points[i - 2][0], prev[1] - points[i - 2][1]) / 2) : 0;
    const startX = prev[0] + (dx / dist) * rPrev;
    const startY = prev[1] + (dy / dist) * rPrev;

    const endX = curr[0] - (dx / dist) * rCorner;
    const endY = curr[1] - (dy / dist) * rCorner;

    if (isHorizontal && segIntersects.length > 0) {
      const isLtr = prev[0] < curr[0];
      const sortedIntersects = [...segIntersects].sort((a, b) => isLtr ? a.x - b.x : b.x - a.x);
      const dir = isLtr ? 1 : -1;

      sortedIntersects.forEach((intersect) => {
        const inBounds = isLtr 
          ? (intersect.x - R > startX && intersect.x + R < endX)
          : (intersect.x + R < startX && intersect.x - R > endX);

        if (inBounds) {
          path += ` L ${(intersect.x - R * dir).toFixed(1)} ${startY.toFixed(1)}`;
          path += ` A ${R} ${R} 0 0 1 ${(intersect.x + R * dir).toFixed(1)} ${startY.toFixed(1)}`;
        }
      });
      path += ` L ${endX.toFixed(1)} ${endY.toFixed(1)}`;
    } else {
      path += ` L ${endX.toFixed(1)} ${endY.toFixed(1)}`;
    }

    if (next && rCorner > 0) {
      const nextX = curr[0] + (nextDx / nextDist) * rCorner;
      const nextY = curr[1] + (nextDy / nextDist) * rCorner;
      path += ` Q ${curr[0].toFixed(1)} ${curr[1].toFixed(1)} ${nextX.toFixed(1)} ${nextY.toFixed(1)}`;
    }
  }

  return path;
}

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

  // 4. Calculate base points (invalidate static waypoints if handle coordinates drift during node drag)
  let staticPoints = edgeData.points as [number, number][] | undefined;
  if (staticPoints && staticPoints.length >= 2) {
    const sDist = Math.hypot(staticPoints[0][0] - shiftedSourceX, staticPoints[0][1] - shiftedSourceY);
    const lastPt = staticPoints[staticPoints.length - 1];
    const tDist = Math.hypot(lastPt[0] - shiftedTargetX, lastPt[1] - shiftedTargetY);
    if (sDist > 15 || tDist > 15 || edgeData.isDragging) {
      staticPoints = undefined;
    }
  }

  const rawPoints = staticPoints || getManhattanPath(
    shiftedSourceX,
    shiftedSourceY,
    sourcePosition,
    shiftedTargetX,
    shiftedTargetY,
    targetPosition,
    midpointOffset
  );

  // Clone points to avoid mutating state references
  const basePoints = rawPoints.map((pt) => [...pt] as [number, number]);

  // 5. Shorten final segment to keep the target arrowhead fully visible outside target border
  if (basePoints.length >= 2) {
    const lastIdx = basePoints.length - 1;
    const pLast = basePoints[lastIdx];
    const pPrev = basePoints[lastIdx - 1];
    const dx = pLast[0] - pPrev[0];
    const dy = pLast[1] - pPrev[1];
    const dist = Math.hypot(dx, dy);
    if (dist > 10) {
      pLast[0] = pLast[0] - (dx / dist) * 8;
      pLast[1] = pLast[1] - (dy / dist) * 8;
    }
  }

  // 6. Path segments & intersection calculation
  const segments = getSegments(basePoints);
  if (!(window as any).__FLOWDRAFT_PATHS__) {
    (window as any).__FLOWDRAFT_PATHS__ = {};
  }
  (window as any).__FLOWDRAFT_PATHS__[id] = segments;

  const [registryCount, setRegistryCount] = React.useState(0);
  useEffect(() => {
    const checkRegistry = () => {
      const count = Object.keys((window as any).__FLOWDRAFT_PATHS__ || {}).length;
      if (count !== registryCount) {
        setRegistryCount(count);
      }
    };
    checkRegistry();
    const interval = setInterval(checkRegistry, 100);
    return () => clearInterval(interval);
  }, [registryCount]);

  const R_jump = 6;
  const intersections: { x: number; y: number; segIdx: number }[] = [];
  if (connectionStyle === 'solid') {
    Object.entries((window as any).__FLOWDRAFT_PATHS__).forEach(([otherId, otherSegs]) => {
      if (otherId === id) return;

      segments.forEach((seg, sIdx) => {
        if (!seg.isHorizontal) return;
        const xMin = Math.min(seg.x1, seg.x2);
        const xMax = Math.max(seg.x1, seg.x2);

        (otherSegs as Segment[]).forEach((oSeg) => {
          if (oSeg.isHorizontal) return;
          const yMin = Math.min(oSeg.y1, oSeg.y2);
          const yMax = Math.max(oSeg.y1, oSeg.y2);

          if (oSeg.x1 > xMin + R_jump && oSeg.x1 < xMax - R_jump) {
            if (seg.y1 > yMin + R_jump && seg.y1 < yMax - R_jump) {
              intersections.push({ x: oSeg.x1, y: seg.y1, segIdx: sIdx });
            }
          }
        });
      });
    });
  }

  const d = getRoundedPathWithJumps(basePoints, 12, intersections);

  // 7. Packet animation using GSAP
  useEffect(() => {
    const activePackets = packetsRef.current.filter((p): p is SVGGElement => p !== null);
    if (activePackets.length === 0 || !d) return;

    const tweens: gsap.core.Tween[] = [];
    const speedMultiplier = edgeData.animationSpeed ?? 1.0;
    const duration = 6.5 / speedMultiplier;

    activePackets.forEach((packet, idx) => {
      gsap.set(packet, { offsetDistance: '0%' });

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
  }, [d, edgeData.animationSpeed, edgeData.particleCount]);

  let strokeDasharray = undefined;
  if (connectionStyle === 'dashed') {
    strokeDasharray = '6, 6';
  } else if (connectionStyle === 'dotted') {
    strokeDasharray = '2, 4';
  }

  const midPoint = basePoints[Math.floor(basePoints.length / 2)] || [
    (sourceX + targetX) / 2,
    (sourceY + targetY) / 2,
  ];

  return (
    <g className="group cursor-pointer">
      {/* Subtle ambient glow path */}
      {d && (
        <path
          d={d}
          fill="none"
          stroke={selected ? '#6366f1' : edgeColor}
          strokeWidth={(Number(style.strokeWidth) || 2) * 5}
          className={`transition-all duration-300 ${
            selected 
              ? 'opacity-[0.35] blur-[4px]' 
              : 'opacity-[0.06] blur-[2px] group-hover:opacity-[0.25] group-hover:blur-[3px]'
          }`}
          style={{ pointerEvents: 'none' }}
        />
      )}

      {/* Core connection path */}
      <path
        id={id}
        className={`react-flow__edge-path transition-all duration-300 group-hover:opacity-100 ${
          strokeDasharray ? 'dashed-edge-flow' : ''
        }`}
        d={d}
        fill="none"
        stroke={selected ? '#6366f1' : edgeColor}
        strokeWidth={selected ? (Number(style.strokeWidth) || 2) + 1.5 : style.strokeWidth || 2}
        strokeDasharray={strokeDasharray}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke: selected ? '#6366f1' : edgeColor,
          opacity: selected ? 1 : 0.85,
        }}
      />

      {/* Flowing glowing packets along the path */}
      {d &&
        edgeData.particleCount !== 0 &&
        Array.from({ length: edgeData.particleCount ?? 3 }).map((_, idx) => (
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
            <circle r={4} fill={edgeColor} opacity={0.2} />
            <circle r={2} fill="#ffffff" opacity={0.9} />
          </g>
        ))}

      {/* Glassmorphic Connection Label Badge */}
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
    </g>
  );
};

export default RoutedEdge;

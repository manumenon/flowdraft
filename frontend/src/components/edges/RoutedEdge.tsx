import React, { useEffect, useRef, useMemo } from 'react';
import { EdgeLabelRenderer, useNodes, type EdgeProps } from '@xyflow/react';
import { gsap } from 'gsap';
import { getManhattanPath, type RectObstacle } from '../../utils/routing';

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

    if (segIntersects.length > 0) {
      if (isHorizontal) {
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
      } else {
        const isTtb = prev[1] < curr[1];
        const sortedIntersects = [...segIntersects].sort((a, b) => isTtb ? a.y - b.y : b.y - a.y);
        const dir = isTtb ? 1 : -1;

        sortedIntersects.forEach((intersect) => {
          const inBounds = isTtb
            ? (intersect.y - R > startY && intersect.y + R < endY)
            : (intersect.y + R < startY && intersect.y - R > endY);

          if (inBounds) {
            path += ` L ${startX.toFixed(1)} ${(intersect.y - R * dir).toFixed(1)}`;
            path += ` A ${R} ${R} 0 0 1 ${startX.toFixed(1)} ${(intersect.y + R * dir).toFixed(1)}`;
          }
        });
      }
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

function getArcLengthMidpoint(points: [number, number][]): [number, number] {
  if (!points || points.length === 0) return [0, 0];
  if (points.length === 1) return points[0];

  const segLengths: number[] = [];
  let totalLength = 0;

  for (let i = 0; i < points.length - 1; i++) {
    const dx = points[i + 1][0] - points[i][0];
    const dy = points[i + 1][1] - points[i][1];
    const len = Math.hypot(dx, dy);
    segLengths.push(len);
    totalLength += len;
  }

  if (totalLength === 0) return points[0];

  const halfLength = totalLength / 2;
  let accumulated = 0;

  for (let i = 0; i < segLengths.length; i++) {
    const len = segLengths[i];
    if (accumulated + len >= halfLength) {
      if (len === 0) return points[i];
      const remaining = halfLength - accumulated;
      const ratio = remaining / len;
      const x = points[i][0] + ratio * (points[i + 1][0] - points[i][0]);
      const y = points[i][1] + ratio * (points[i + 1][1] - points[i][1]);
      return [x, y];
    }
    accumulated += len;
  }

  return points[points.length - 1];
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
  const nodes = useNodes();
  const edgeData = data as any;
  const edgeColor = edgeData.color || '#a6adc8';
  const connectionStyle = edgeData.style || 'solid';

  const obstacles: RectObstacle[] = useMemo(() => {
    const nodeMap = new Map<string, any>();
    nodes.forEach((n) => nodeMap.set(n.id, n));

    const getAbsPosition = (node: any): { x: number; y: number } => {
      let x = node.position?.x ?? 0;
      let y = node.position?.y ?? 0;
      let curr = node;
      while (curr && curr.parentId) {
        const parent = nodeMap.get(curr.parentId);
        if (!parent) break;
        x += parent.position?.x ?? 0;
        y += parent.position?.y ?? 0;
        curr = parent;
      }
      return { x, y };
    };

    return nodes.map((n) => {
      const abs = getAbsPosition(n);
      return {
        x: abs.x,
        y: abs.y,
        width: n.measured?.width || n.width || (n.style?.width as number) || 180,
        height: n.measured?.height || n.height || (n.style?.height as number) || 100,
      };
    });
  }, [nodes]);

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
  if (edgeData.isDragging) {
    staticPoints = undefined;
  } else if (staticPoints && staticPoints.length >= 2) {
    const sDist = Math.hypot(staticPoints[0][0] - shiftedSourceX, staticPoints[0][1] - shiftedSourceY);
    const lastPt = staticPoints[staticPoints.length - 1];
    const tDist = Math.hypot(lastPt[0] - shiftedTargetX, lastPt[1] - shiftedTargetY);
    if (sDist > 15 || tDist > 15) {
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
    midpointOffset,
    obstacles
  );

  // Clone points to avoid mutating state references
  const basePoints = rawPoints.map((pt) => [...pt] as [number, number]);

  // 5. Shorten final segment to keep the target arrowhead aligned precisely outside target border
  if (basePoints.length >= 2) {
    const lastIdx = basePoints.length - 1;
    const pLast = basePoints[lastIdx];
    const pPrev = basePoints[lastIdx - 1];
    const dx = pLast[0] - pPrev[0];
    const dy = pLast[1] - pPrev[1];
    const dist = Math.hypot(dx, dy);
    const MARKER_REF_OFFSET = 5.0; // Match SVG arrowhead marker refX offset exactly
    if (dist > MARKER_REF_OFFSET + 1.0) {
      const clampOffset = Math.min(MARKER_REF_OFFSET, dist - 1.0);
      pLast[0] = pLast[0] - (dx / dist) * clampOffset;
      pLast[1] = pLast[1] - (dy / dist) * clampOffset;
    }
  }

  // 6. Path segments & intersection calculation
  const segments = getSegments(basePoints);
  if (!(window as any).__FLOWDRAFT_PATHS__) {
    (window as any).__FLOWDRAFT_PATHS__ = {};
  }
  (window as any).__FLOWDRAFT_PATHS__[id] = segments;

  const R_jump = 6;
  const intersections: { x: number; y: number; segIdx: number }[] = [];
  const allPaths = (window as any).__FLOWDRAFT_PATHS__ || {};
  Object.entries(allPaths).forEach(([otherId, otherSegs]) => {
    if (otherId === id) return;

    segments.forEach((seg, sIdx) => {
      (otherSegs as Segment[]).forEach((oSeg) => {
        if (seg.isHorizontal !== oSeg.isHorizontal) {
          const horiz = seg.isHorizontal ? seg : oSeg;
          const vert = seg.isHorizontal ? oSeg : seg;

          const xMin = Math.min(horiz.x1, horiz.x2);
          const xMax = Math.max(horiz.x1, horiz.x2);
          const yMin = Math.min(vert.y1, vert.y2);
          const yMax = Math.max(vert.y1, vert.y2);

          if (vert.x1 > xMin + R_jump && vert.x1 < xMax - R_jump &&
              horiz.y1 > yMin + R_jump && horiz.y1 < yMax - R_jump) {
            if (id.localeCompare(otherId) < 0) {
              intersections.push({ x: vert.x1, y: horiz.y1, segIdx: sIdx });
            }
          }
        }
      });
    });
  });

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

  const midPoint = getArcLengthMidpoint(basePoints);

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
              zIndex: 30,
            }}
            className="px-2.5 py-1 rounded-md bg-surface-1/95 border border-border-strong shadow-lg text-[9px] font-extrabold text-text-primary uppercase tracking-wider font-mono text-center max-w-[160px] break-words whitespace-normal leading-tight select-none backdrop-blur-md hover:z-40 transition-all"
          >
            {edgeData.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </g>
  );
};

export default RoutedEdge;

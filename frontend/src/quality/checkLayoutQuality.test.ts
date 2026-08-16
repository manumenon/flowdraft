import { describe, it, expect } from 'vitest';
import type { FlowSpec } from '../types/spec';
import { compileSpec } from '../utils/specCompiler';
import { computeLayout, resolveLabelPositions, type LabelResolutionEdge, type LabelResolutionNode } from '../workers/layoutCore';
import { defaultSpec } from '../assets/defaultSpec';
import { stressSpec } from '../assets/stressSpec';
import {
  checkLayoutQuality,
  checkNoLabelOverlaps,
  flattenLayoutNodes,
  flattenLayoutEdges,
  type QualityConnection,
} from './checkLayoutQuality';

async function runQualityCheck(spec: FlowSpec) {
  const compiled = compileSpec(spec, (spec.theme as string) || 'dark');
  const layoutResult = await computeLayout({
    elements: compiled.flatElements,
    connections: spec.connections || [],
    title: spec.title,
    layoutDirection: spec.canvas?.layoutDirection,
    layoutAlgorithm: spec.canvas?.layoutAlgorithm,
  });

  const nodes = flattenLayoutNodes(layoutResult, compiled.flatElements);
  const connections = flattenLayoutEdges(layoutResult, spec.connections || []);
  return { report: checkLayoutQuality(nodes, connections), nodes, connections };
}

describe('checkLayoutQuality', () => {
  it('passes against the real default spec (compiled + laid out end to end)', async () => {
    const { report } = await runQualityCheck(defaultSpec);

    // On failure, surface which specific sub-check(s) failed and why —
    // the aggregate ok:false alone isn't enough to debug.
    const failed = report.checks.filter((c) => !c.ok);
    expect(failed, JSON.stringify(failed, null, 2)).toEqual([]);
    expect(report.ok).toBe(true);
  });

  it('passes for panels using flow/grid child layout (stage 3)', async () => {
    const flowGridSpec: FlowSpec = {
      canvas: { width: 1600, height: 1200 },
      theme: 'dark',
      title: { prefix: 'Flow/Grid', highlight: 'Layout Check' },
      elements: [
        {
          id: 'flow_panel',
          type: 'panel',
          title: 'Flow Panel (row-major, wraps after 2)',
          layout: { direction: 'flow', gap: 16, max_cols: 2 },
          style: { strokeColor: '#22c86f' },
          children: [
            { id: 'f1', type: 'card', title: 'Alpha', body: 'first' },
            { id: 'f2', type: 'card', title: 'Beta', body: 'second' },
            { id: 'f3', type: 'card', title: 'Gamma', body: 'third' },
          ],
        },
        {
          id: 'grid_panel',
          type: 'panel',
          title: 'Grid Panel (uniform 2-col cells)',
          badge: 'v2',
          layout: { direction: 'grid', gap: 16, grid_cols: 2 },
          style: { strokeColor: '#1d8be8' },
          children: [
            { id: 'g1', type: 'card', title: 'One' },
            { id: 'g2', type: 'card', title: 'Two' },
            { id: 'g3', type: 'card', title: 'Three' },
            { id: 'g4', type: 'card', title: 'Four' },
          ],
        },
      ],
      connections: [
        { from: 'f1', to: 'g1', exitPort: 'right', entryPort: 'left' },
        { from: 'f2', to: 'g2', exitPort: 'right', entryPort: 'left' },
        { from: 'f3', to: 'g3', exitPort: 'right', entryPort: 'left' },
      ],
    };

    const { report } = await runQualityCheck(flowGridSpec);
    const failed = report.checks.filter((c) => !c.ok);
    expect(failed, JSON.stringify(failed, null, 2)).toEqual([]);
    expect(report.ok).toBe(true);
  });

  it('passes against the bigger stress fixture (stage 5: ~65+ elements, 3 levels of nesting, mixed row/column/flow/grid)', async () => {
    // Sanity-check the fixture's own claimed scale before trusting the quality
    // report about it — a depth/count regression in stressSpec.ts itself
    // should fail loudly here rather than silently shrinking test coverage.
    const countElements = (els: FlowSpec['elements']): number =>
      els.reduce((sum, el) => sum + 1 + (el.children ? countElements(el.children) : 0) + (el.footer ? 1 : 0), 0);
    const maxDepth = (els: FlowSpec['elements'], depth = 0): number =>
      els.reduce((max, el) => {
        const childDepth = el.children && el.children.length ? maxDepth(el.children, depth + 1) : depth;
        return Math.max(max, childDepth);
      }, depth);

    const elementCount = countElements(stressSpec.elements);
    const connectionCount = (stressSpec.connections || []).length;
    const nestingDepth = maxDepth(stressSpec.elements);

    expect(elementCount).toBeGreaterThanOrEqual(60);
    expect(elementCount).toBeLessThanOrEqual(80);
    expect(nestingDepth).toBe(3);

    const { report } = await runQualityCheck(stressSpec);
    const failed = report.checks.filter((c) => !c.ok);
    expect(
      failed,
      `fixture: ${elementCount} elements, ${connectionCount} connections, ${nestingDepth} levels of nesting\n` +
        JSON.stringify(failed, null, 2)
    ).toEqual([]);
    expect(report.ok).toBe(true);
  });
});

describe('checkNoLabelOverlaps / resolveLabelPositions (label overlap regression)', () => {
  // Reproduces, in miniature, the real bug confirmed this session: two
  // nearly-parallel connections' independently-computed label positions
  // ("VOD REQUEST" and "EMIT PLAYBACK EVENT") landed stacked directly on
  // top of each other, because the label position used to be computed per
  // edge, at render time, with zero awareness of any other edge's label.
  //
  // Two Z-shaped orthogonal paths (mirroring ELK's own routing style),
  // offset 30px from each other on both the entry and exit legs, sharing
  // the same long horizontal middle segment's y-coordinate — exactly the
  // "two nearly-parallel connections" shape from the real bug.
  const vodEdge: LabelResolutionEdge = {
    id: 'edge-vod',
    label: 'VOD REQUEST',
    points: [
      [50, 100],
      [50, 150],
      [250, 150],
      [250, 200],
    ],
  };
  const emitEdge: LabelResolutionEdge = {
    id: 'edge-emit',
    label: 'EMIT PLAYBACK EVENT',
    points: [
      [80, 100],
      [80, 150],
      [280, 150],
      [280, 200],
    ],
  };

  // Mirrors RoutedEdge.tsx's OLD, pre-fix behavior exactly: each edge's
  // label sat at the raw arc-length midpoint of its own path, with no
  // perpendicular offset and no awareness of any other edge's label.
  function naiveArcLengthMidpoint(points: [number, number][]): { x: number; y: number } {
    let total = 0;
    const segLens: number[] = [];
    for (let i = 0; i < points.length - 1; i++) {
      const len = Math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]);
      segLens.push(len);
      total += len;
    }
    let accumulated = 0;
    const half = total / 2;
    for (let i = 0; i < segLens.length; i++) {
      const len = segLens[i];
      if (accumulated + len >= half) {
        const ratio = len > 0 ? (half - accumulated) / len : 0;
        return {
          x: points[i][0] + ratio * (points[i + 1][0] - points[i][0]),
          y: points[i][1] + ratio * (points[i + 1][1] - points[i][1]),
        };
      }
      accumulated += len;
    }
    return { x: points[points.length - 1][0], y: points[points.length - 1][1] };
  }

  it('the naive (pre-fix) independent-per-edge midpoint DOES collide — proves the check catches the original bug', () => {
    const naiveConnections: QualityConnection[] = [vodEdge, emitEdge].map((e) => {
      const mid = naiveArcLengthMidpoint(e.points);
      return { id: e.id, from: 'a', to: 'b', points: e.points, label: e.label, labelX: mid.x, labelY: mid.y };
    });

    const report = checkNoLabelOverlaps(naiveConnections);
    expect(report.ok, JSON.stringify(report, null, 2)).toBe(false);
    expect((report.overlaps as any[]).length).toBeGreaterThan(0);
  });

  it('resolveLabelPositions places both labels with zero overlap, sliding the second along its own path to clear the first', () => {
    const nodes: LabelResolutionNode[] = [];
    const edges: LabelResolutionEdge[] = [vodEdge, emitEdge];

    const positions = resolveLabelPositions(edges, nodes);
    expect(positions.size).toBe(2);

    const vodPos = positions.get('edge-vod')!;
    const emitPos = positions.get('edge-emit')!;
    expect(vodPos).toBeDefined();
    expect(emitPos).toBeDefined();

    // VOD REQUEST is processed first, with no other labels placed yet, so
    // it keeps its plain arc-length midpoint (offset 12px off the
    // horizontal middle segment, per resolveLabelPositions's normal rule).
    expect(vodPos.x).toBeCloseTo(150, 0);
    expect(vodPos.y).toBeCloseTo(138, 0);

    // EMIT PLAYBACK EVENT's own midpoint (fraction 0.5) collides with
    // VOD REQUEST's already-placed box, and so do 0.35/0.65/0.2 — only the
    // 0.8 candidate clears it, which is where it should land.
    expect(emitPos.x).toBeCloseTo(270, 0);
    expect(emitPos.y).toBeCloseTo(138, 0);

    const connectionsWithLabels: QualityConnection[] = edges.map((e) => {
      const pos = positions.get(e.id)!;
      return { id: e.id, from: 'a', to: 'b', points: e.points, label: e.label, labelX: pos.x, labelY: pos.y };
    });

    const report = checkNoLabelOverlaps(connectionsWithLabels);
    expect(report.ok, JSON.stringify(report, null, 2)).toBe(true);
    expect((report.overlaps as any[]).length).toBe(0);
  });

  it('passes end to end (compileSpec -> computeLayout -> checkLayoutQuality) for a spec with dense, differently-sized parallel labels', async () => {
    const denseLabelSpec: FlowSpec = {
      canvas: { width: 1400, height: 900 },
      theme: 'dark',
      title: { highlight: 'Dense Parallel Labels' },
      elements: [
        { id: 'src_top', type: 'card', title: 'Source Top' },
        { id: 'src_bottom', type: 'card', title: 'Source Bottom' },
        { id: 'dst_top', type: 'card', title: 'Dest Top' },
        { id: 'dst_bottom', type: 'card', title: 'Dest Bottom' },
      ],
      connections: [
        {
          from: 'src_top',
          to: 'dst_top',
          exitPort: 'right',
          entryPort: 'left',
          label: 'VOD REQUEST',
        },
        {
          from: 'src_bottom',
          to: 'dst_bottom',
          exitPort: 'right',
          entryPort: 'left',
          label: 'EMIT PLAYBACK EVENT',
        },
      ],
    };

    const { report } = await runQualityCheck(denseLabelSpec);
    const failed = report.checks.filter((c) => !c.ok);
    expect(failed, JSON.stringify(failed, null, 2)).toEqual([]);
    expect(report.ok).toBe(true);

    const labelCheck = report.checks.find((c) => c.name === 'no_label_overlaps')!;
    expect(labelCheck.ok).toBe(true);
  });
});

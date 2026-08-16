import { describe, it, expect } from 'vitest';
import type { FlowSpec } from '../types/spec';
import { compileSpec } from '../utils/specCompiler';
import { computeLayout, resolveLabelPositions, estimateLabelBoxSize, type LabelResolutionEdge, type LabelResolutionNode } from '../workers/layoutCore';
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
  return { report: checkLayoutQuality(nodes, connections, spec.canvas?.layoutDirection), nodes, connections };
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

describe('checkColumnRowAlignment (elkjs#26 direction-mismatch cascade regression)', () => {
  // The exact case named in the bug report: a 'column'-direction panel
  // (mismatched against the default RIGHT root) with a chained
  // Dynamic Planner -> Ephemeral Tools -> Persona Registry topology,
  // previously rendered as a diagonal cascade instead of a clean stack —
  // see layoutCore.ts's postProcessLayoutResult ("row/column panels whose
  // declared ELK direction") for the fix.
  it('stacks defaultSpec.ts\'s "Agent Execution Fabric" panel in a single column, in topological order, with its internal edges intact', async () => {
    const { nodes, edges } = await runQualityCheck(defaultSpec).then(async (r) => {
      const compiled = compileSpec(defaultSpec, (defaultSpec.theme as string) || 'dark');
      const layoutResult = await computeLayout({
        elements: compiled.flatElements,
        connections: defaultSpec.connections || [],
        title: defaultSpec.title,
        layoutDirection: defaultSpec.canvas?.layoutDirection,
        layoutAlgorithm: defaultSpec.canvas?.layoutAlgorithm,
      });
      return {
        ...r,
        nodes: flattenLayoutNodes(layoutResult, compiled.flatElements),
        edges: flattenLayoutEdges(layoutResult, defaultSpec.connections || []),
      };
    });

    const planner = nodes.find((n) => n.id === 'right_0')!;
    const tools = nodes.find((n) => n.id === 'right_1')!;
    const persona = nodes.find((n) => n.id === 'right_2')!;
    expect(planner.title).toBe('Dynamic Planner');
    expect(tools.title).toBe('Ephemeral Tools');
    expect(persona.title).toBe('Persona Registry');

    // Clean single-axis column stack: same x, strictly increasing y, in
    // exactly the declared Planner -> Tools -> Persona order (not the
    // "sort by x+y of a diagonal cascade" order this reprojects away).
    expect(planner.x).toBeCloseTo(tools.x, 0);
    expect(tools.x).toBeCloseTo(persona.x, 0);
    expect(planner.y).toBeLessThan(tools.y);
    expect(tools.y).toBeLessThan(persona.y);

    // The panel's own internal chain edges still connect to the real,
    // reprojected node positions (not stale, pre-reprojection ones — the
    // failure mode a naive "just move the nodes" fix would produce).
    const plannerToTools = edges.find((e) => e.from === 'right_0' && e.to === 'right_1')!;
    const toolsToPersona = edges.find((e) => e.from === 'right_1' && e.to === 'right_2')!;
    const near = (p: [number, number], n: typeof planner, margin = 8) =>
      p[0] >= n.absX - margin && p[0] <= n.absX + n.width + margin &&
      p[1] >= n.absY - margin && p[1] <= n.absY + n.height + margin;
    expect(near(plannerToTools.points[0], planner)).toBe(true);
    expect(near(plannerToTools.points[plannerToTools.points.length - 1], tools)).toBe(true);
    expect(near(toolsToPersona.points[0], tools)).toBe(true);
    expect(near(toolsToPersona.points[toolsToPersona.points.length - 1], persona)).toBe(true);
  });

  it('also fixes a "row"-direction panel mismatched against a vertical (DOWN) root', async () => {
    const verticalSpec: FlowSpec = {
      canvas: { width: 1600, height: 1400, layoutDirection: 'vertical' },
      theme: 'dark',
      title: { highlight: 'Vertical Root Row Panel' },
      elements: [
        {
          id: 'row_panel',
          type: 'panel',
          title: 'Row Panel',
          layout: { direction: 'row', gap: 16 },
          children: [
            { id: 'r0', type: 'card', title: 'Alpha' },
            { id: 'r1', type: 'card', title: 'Beta' },
            { id: 'r2', type: 'card', title: 'Gamma' },
          ],
        },
      ],
      connections: [
        { from: 'r0', to: 'r1', exitPort: 'right', entryPort: 'left' },
        { from: 'r1', to: 'r2', exitPort: 'right', entryPort: 'left' },
      ],
    };

    const { report, nodes } = await runQualityCheck(verticalSpec);
    const failed = report.checks.filter((c) => !c.ok);
    expect(failed, JSON.stringify(failed, null, 2)).toEqual([]);

    const kids = ['r0', 'r1', 'r2'].map((id) => nodes.find((n) => n.id === id)!);
    const ys = kids.map((k) => k.y);
    expect(Math.max(...ys) - Math.min(...ys)).toBeLessThan(2);
    expect(kids[0].x).toBeLessThan(kids[1].x);
    expect(kids[1].x).toBeLessThan(kids[2].x);
  });

  it('known limitation: leaves a mismatched panel un-reprojected (cascade intact) rather than risk a routing regression, when its stacked children are too disproportionate to fit ELK\'s own reserved footprint', async () => {
    // right_agent_panel stacks two 140px cards below a 943px-tall nested
    // flow panel (6 tools, 3 cols) — a clean column stack genuinely needs
    // more height than ELK's diagonal cascade reserved for it. Confirmed,
    // during development, that reprojecting it anyway makes
    // checkNoUnrelatedPanelCrossings newly fail elsewhere in this same
    // fixture (other edges routed assuming the smaller original
    // footprint). The fix bails out for exactly this case instead —
    // checkColumnRowAlignment (see its own comment) derives the identical
    // "would it fit" condition and doesn't assert alignment here either,
    // so the full checkLayoutQuality suite still passes overall; this test
    // just documents, explicitly, that this specific known case is not
    // (yet) actually fixed, so a future improvement doesn't silently go
    // unnoticed.
    const { nodes } = await runQualityCheck(stressSpec);
    const kids = nodes.filter((n) => n.parent === 'right_agent_panel');
    const xs = kids.map((k) => k.x);
    expect(Math.max(...xs) - Math.min(...xs)).toBeGreaterThan(100);
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

  // Live testing (this session) found a near-miss checkNoLabelOverlaps'
  // plain, zero-margin AABB test doesn't catch: two edges leaving the SAME
  // node on the SAME exit side (e.g. two parallel "exit right" connections,
  // fanned ~20px apart per makeFannedPorts' PORT_PITCH), each labeled. Their
  // resolved label boxes can end up only a few px apart — passing
  // checkNoLabelOverlaps outright (any gap > 0 counts as "no overlap") while
  // still reading as touching/colliding in a real render, connector lines
  // visibly crossing right at that point.
  //
  // Reproduced here in miniature: two near-parallel, same-direction
  // (both exit right) horizontal edges offset 20px in y — vod's is the
  // shorter path, live's is longer, so their 5 candidate fractions land at
  // different points along each path (a straight offset clone of the same
  // length, as the "VOD REQUEST"/"EMIT PLAYBACK EVENT" fixture above uses,
  // doesn't exercise this: same-length paths' first-clearing candidate is
  // never a near-miss for this exact pair of label texts). Confirmed by
  // hand (temporarily setting layoutCore.ts's MIN_LABEL_GAP to 0 and rerunning):
  // pre-fix, live's label resolves to (245, 108) — only 6px of real
  // clearance from vod's box, despite 6 > 0 meaning checkNoLabelOverlaps
  // passes it clean. That's the exact near-miss this fixture pins down.
  it('resolveLabelPositions gives two same-node, same-direction parallel edges REAL separation, not just a technical non-overlap', () => {
    const vodEdge: LabelResolutionEdge = {
      id: 'edge-vod-exit',
      label: 'VOD REQUEST',
      points: [
        [50, 100],
        [250, 100],
      ],
    };
    const liveEdge: LabelResolutionEdge = {
      id: 'edge-live-exit',
      // 20px below vod's exit -- the same fan pitch makeFannedPorts uses
      // for two connections sharing one node's exit side.
      label: 'LIVE REQUEST',
      points: [
        [50, 120],
        [350, 120],
      ],
    };

    const positions = resolveLabelPositions([vodEdge, liveEdge], []);
    const vodPos = positions.get('edge-vod-exit')!;
    const livePos = positions.get('edge-live-exit')!;

    // vod is placed first, keeping its own plain midpoint.
    expect(vodPos.x).toBeCloseTo(150, 0);
    expect(vodPos.y).toBeCloseTo(88, 0);

    // Pre-fix (MIN_LABEL_GAP = 0), live would land on its own 0.65-fraction
    // candidate (245, 108) -- the first one whose box doesn't literally
    // intersect vod's, but only by 6px. With the margin fix, that candidate
    // now counts as a collision too, so live gets nudged one step further
    // along its own path to the 0.8-fraction candidate instead.
    expect(livePos.x).toBeCloseTo(290, 0);
    expect(livePos.y).toBeCloseTo(108, 0);

    const vodSize = estimateLabelBoxSize('VOD REQUEST');
    const liveSize = estimateLabelBoxSize('LIVE REQUEST');
    const vBox = {
      x1: vodPos.x - vodSize.width / 2,
      x2: vodPos.x + vodSize.width / 2,
      y1: vodPos.y - vodSize.height / 2,
      y2: vodPos.y + vodSize.height / 2,
    };
    const lBox = {
      x1: livePos.x - liveSize.width / 2,
      x2: livePos.x + liveSize.width / 2,
      y1: livePos.y - liveSize.height / 2,
      y2: livePos.y + liveSize.height / 2,
    };
    // Real gap along whichever axis actually separates the two boxes (they
    // still overlap on the other axis here, same as any two boxes offset
    // mostly along one direction) -- not just "some pixel of daylight".
    const gap = Math.max(vBox.x1 - lBox.x2, lBox.x1 - vBox.x2, vBox.y1 - lBox.y2, lBox.y1 - vBox.y2);
    expect(gap).toBeGreaterThanOrEqual(8); // the MIN_LABEL_GAP margin itself
    expect(gap).toBeGreaterThan(6); // strictly more than the pre-fix near-miss gap

    // Also still passes the existing strict (zero-margin) check, same as
    // the pre-fix near-miss position technically did -- proving this test
    // is asserting something checkNoLabelOverlaps alone can't.
    const connectionsWithLabels: QualityConnection[] = [vodEdge, liveEdge].map((e) => {
      const pos = positions.get(e.id)!;
      return { id: e.id, from: 'a', to: 'b', points: e.points, label: e.label, labelX: pos.x, labelY: pos.y };
    });
    const report = checkNoLabelOverlaps(connectionsWithLabels);
    expect(report.ok, JSON.stringify(report, null, 2)).toBe(true);
  });
});

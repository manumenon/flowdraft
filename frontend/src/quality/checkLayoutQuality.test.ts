import { describe, it, expect } from 'vitest';
import type { FlowSpec } from '../types/spec';
import { compileSpec } from '../utils/specCompiler';
import { computeLayout } from '../workers/layoutCore';
import { defaultSpec } from '../assets/defaultSpec';
import { stressSpec } from '../assets/stressSpec';
import { checkLayoutQuality, flattenLayoutNodes, flattenLayoutEdges } from './checkLayoutQuality';

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

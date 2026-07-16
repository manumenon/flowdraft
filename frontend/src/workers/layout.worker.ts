// Intercept postMessage to capture GWT initialization response
const originalPostMessage = self.postMessage;

(self as any).postMessage = (msg: any) => {
  if (msg && msg.id === -1) {
    // Restore original postMessage now
    (self as any).postMessage = originalPostMessage;
    // Notify the main thread that the layout engine is fully initialized and ready.
    originalPostMessage({ success: true, type: 'ready' });
  }
};

// Import GWT layout engine directly which overwrites self.onmessage
import 'elkjs/lib/elk-worker.min.js';

const gwtDispatcher = (self as any).onmessage;

// Register layout algorithms on GWT engine
if (gwtDispatcher) {
  gwtDispatcher({
    data: {
      id: -1,
      cmd: 'register',
      algorithms: ['layered', 'stress', 'mrtree', 'radial', 'force', 'disco', 'sporeOverlap', 'sporeCompaction', 'rectpacking']
    }
  } as any);
}

function isFeedback(srcId: string, tgtId: string): boolean {
  if (srcId === 'decision' && tgtId === 'core_0') return true;
  if (srcId === 'right_0' && tgtId === 'decision') return true;
  return false;
}

self.onmessage = async (event: MessageEvent) => {
  console.log("WORKER: Received layout request event!");
  const { elements, connections, title } = event.data;

  try {
    const nodesMap = new Map<string, any>();
    elements.forEach((n: any) => nodesMap.set(n.id, n));

    const getTopParent = (id: string): string => {
      const visited = new Set<string>();
      let current = id;
      while (nodesMap.get(current)?.parent) {
        if (visited.has(current)) break;
        visited.add(current);
        current = nodesMap.get(current)!.parent!;
      }
      return current;
    };

    const panelHeaders: Record<string, number> = {};
    elements.forEach((node: any) => {
      if (node.type === 'panel') {
        let topPad = 40.0;
        const hasTitle = !!node.title;
        const hasSubtitle = !!node.subtitle;
        if (hasTitle) topPad = Math.max(topPad, 36);
        if (hasSubtitle) topPad = Math.max(topPad, 56);
        topPad += 15.0;
        panelHeaders[node.id] = topPad;
      }
    });

    const elkNodes: Record<string, any> = {};
    elements.forEach((node: any) => {
      const nid = node.id;
      const ntype = node.type;
      const elkNode: any = { id: nid, children: [], edges: [] };

      if (ntype === 'panel' || ntype === 'group') {
        const direction = node.layout?.direction || 'row';
        const gap = node.layout?.gap ?? 20;
        const topPad = panelHeaders[nid] || 40.0;
        let padLeft = 20, padBottom = 20, padRight = 20;
        if (node.layout?.padding) {
          const p = node.layout.padding;
          if (typeof p === 'number') {
            padLeft = p; padBottom = p; padRight = p;
          } else {
            padLeft = p.left ?? 20;
            padBottom = p.bottom ?? 20;
            padRight = p.right ?? 20;
          }
        }
        elkNode.layoutOptions = {
          'elk.algorithm': 'layered',
          'elk.direction': direction === 'column' ? 'DOWN' : 'RIGHT',
          'elk.spacing.nodeNode': String(gap),
          'elk.layered.spacing.nodeNodeBetweenLayers': String(gap),
          'elk.padding': `[top=${topPad},left=${padLeft},bottom=${padBottom},right=${padRight}]`
        };
      } else {
        elkNode.width = node.width || 200;
        elkNode.height = node.height || 80;
      }
      elkNodes[nid] = elkNode;
    });

    const topRootPad = title ? 200 : 80;
    const elkRoot: any = {
      id: 'root',
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': 'DOWN',
        'elk.spacing.nodeNode': '80',
        'elk.layered.spacing.nodeNodeBetweenLayers': '90',
        'elk.hierarchyHandling': 'SEPARATE_CHILDREN',
        'elk.cycleBreaking.strategy': 'MODEL_ORDER',
        'elk.layered.crossingMinimization.strategy': 'INTERACTIVE',
        'elk.padding': `[top=${topRootPad},left=50,bottom=50,right=50]`
      },
      children: [],
      edges: []
    };

    elements.forEach((node: any) => {
      const nid = node.id;
      const elkNode = elkNodes[nid];
      if (!elkNode) return;
      const parentId = node.parent;
      if (parentId && elkNodes[parentId]) {
        elkNodes[parentId].children.push(elkNode);
      } else {
        elkRoot.children.push(elkNode);
      }
    });

    const topLevelIds = new Set<string>(elkRoot.children.map((c: any) => c.id as string));
    if (topLevelIds.size > 0) {
      const adj: Record<string, Set<string>> = {};
      const inDegree: Record<string, number> = {};
      topLevelIds.forEach((id) => {
        adj[id] = new Set<string>();
        inDegree[id] = 0;
      });

      connections?.forEach((conn: any) => {
        const srcId = conn.from;
        const tgtId = conn.to;
        if (isFeedback(srcId, tgtId)) return;
        const srcTop = getTopParent(srcId);
        const tgtTop = getTopParent(tgtId);
        if (srcTop !== tgtTop && topLevelIds.has(srcTop) && topLevelIds.has(tgtTop)) {
          if (!adj[srcTop].has(tgtTop)) {
            adj[srcTop].add(tgtTop);
            inDegree[tgtTop] = (inDegree[tgtTop] || 0) + 1;
          }
        }
      });

      const topoOrder: string[] = [];
      const inDegCopy = { ...inDegree };

      while (topoOrder.length < topLevelIds.size) {
        const zeros = Array.from(topLevelIds).filter(
          (id: string) => inDegCopy[id] === 0 && !topoOrder.includes(id)
        );

        if (zeros.length === 0) {
          const remaining = Array.from(topLevelIds).filter((id: string) => !topoOrder.includes(id));
          if (remaining.length === 0) break;
          const minId = remaining.reduce((min: string, id: string) =>
            (inDegCopy[id] || 0) < (inDegCopy[min] || 0) ? id : min
          , remaining[0]);
          zeros.push(minId);
        }

        const curr = zeros[0];
        topoOrder.push(curr);
        adj[curr]?.forEach((neighbor: string) => {
          if (inDegCopy[neighbor] > 0) {
            inDegCopy[neighbor]--;
          }
        });
      }

      const rank: Record<string, number> = {};
      topLevelIds.forEach((id: string) => {
        rank[id] = 0;
      });
      topoOrder.forEach((nodeId: string) => {
        adj[nodeId]?.forEach((neighbor: string) => {
          rank[neighbor] = Math.max(rank[neighbor], rank[nodeId] + 1);
        });
      });

      const elementIndexMap: Record<string, number> = {};
      elements.forEach((node: any, idx: number) => {
        elementIndexMap[node.id] = idx;
      });

      elkRoot.children.sort((a: any, b: any) => {
        const rA = rank[a.id] ?? 999;
        const rB = rank[b.id] ?? 999;
        if (rA === rB) {
          const idxA = elementIndexMap[a.id] ?? 999;
          const idxB = elementIndexMap[b.id] ?? 999;
          return idxA - idxB;
        }
        return rA - rB;
      });
    }

    let edgeCounter = 0;
    connections?.forEach((conn: any, i: number) => {
      const srcId = conn.from;
      const tgtId = conn.to;
      if (!elkNodes[srcId] || !elkNodes[tgtId]) return;

      const edgeOpts: any = {};
      if (isFeedback(srcId, tgtId)) {
        edgeOpts['elk.layered.feedback'] = 'true';
      }

      const src = getTopParent(srcId);
      const tgt = getTopParent(tgtId);
      if (src !== tgt) {
        edgeCounter++;
        const edge: any = {
          id: `edge_${edgeCounter}_${srcId}_${tgtId}`,
          sources: [srcId],
          targets: [tgtId]
        };
        if (Object.keys(edgeOpts).length > 0) {
          edge.layoutOptions = edgeOpts;
        }
        elkRoot.edges.push(edge);
      } else {
        const edge: any = {
          id: `edge_internal_${i}_${srcId}_${tgtId}`,
          sources: [srcId],
          targets: [tgtId]
        };
        if (Object.keys(edgeOpts).length > 0) {
          edge.layoutOptions = edgeOpts;
        }
        if (elkNodes[src]) {
          elkNodes[src].edges.push(edge);
        } else {
          elkRoot.edges.push(edge);
        }
      }
    });

    // Run layout synchronously using GWT dispatcher
    let layoutResult: any = null;
    (self as any).postMessage = (msg: any) => {
      layoutResult = msg;
    };

    console.log("WORKER: Dispatching graph to GWT...");
    if (gwtDispatcher) {
      gwtDispatcher({
        data: {
          id: 42,
          cmd: 'layout',
          graph: elkRoot
        }
      } as any);
    }

    console.log("WORKER: GWT execution completed. layoutResult:", JSON.stringify(layoutResult));

    (self as any).postMessage = originalPostMessage;

    if (layoutResult && !layoutResult.error && layoutResult.data) {
      self.postMessage({ success: true, graph: layoutResult.data });
    } else {
      console.error("WORKER: Layout failed, layoutResult error:", layoutResult?.error);
      self.postMessage({ success: false, error: layoutResult?.error?.message || 'GWT layout failed' });
    }
  } catch (err: any) {
    self.postMessage({ success: false, error: err.message });
  }
};

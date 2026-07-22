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

function findFeedbackEdges(elements: any[], connections: any[]): Set<string> {
  const adj: Record<string, string[]> = {};
  elements.forEach((n: any) => {
    adj[n.id] = [];
  });
  
  connections?.forEach((conn: any) => {
    const from = conn.from;
    const to = conn.to;
    if (adj[from] && adj[to]) {
      adj[from].push(to);
    }
  });

  const visited = new Set<string>();
  const recStack = new Set<string>();
  const feedbackEdges = new Set<string>();

  const dfs = (node: string) => {
    visited.add(node);
    recStack.add(node);

    const neighbors = adj[node] || [];
    for (const neighbor of neighbors) {
      if (!visited.has(neighbor)) {
        dfs(neighbor);
      } else if (recStack.has(neighbor)) {
        feedbackEdges.add(`${node}->${neighbor}`);
      }
    }

    recStack.delete(node);
  };

  elements.forEach((n: any) => {
    if (!visited.has(n.id)) {
      dfs(n.id);
    }
  });

  return feedbackEdges;
}

self.onmessage = async (event: MessageEvent) => {
  console.log("WORKER: Received layout request event!");
  const { elements, connections, title, layoutDirection, layoutAlgorithm } = event.data;
  const feedbackEdges = findFeedbackEdges(elements, connections);
  const isFeedback = (srcId: string, tgtId: string): boolean => {
    return feedbackEdges.has(`${srcId}->${tgtId}`);
  };

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
        const titleText = node.title || '';
        const titleLines = Math.max(1, Math.ceil(titleText.length / 28));
        const subtitleText = node.subtitle || '';
        const subtitleLines = subtitleText ? Math.max(1, Math.ceil(subtitleText.length / 32)) : 0;
        topPad = Math.max(44, 20 + titleLines * 20 + subtitleLines * 16);
        panelHeaders[node.id] = topPad;
      }
    });

    const isFooterNode = (node: any): boolean => {
      if (!node) return false;
      if (node._role === 'footer' || node.data?.role === 'footer') return true;
      if (typeof node.id === 'string' && node.id.toLowerCase().includes('footer')) return true;
      return false;
    };

    const elkNodes: Record<string, any> = {};
    elements.forEach((node: any) => {
      const nid = node.id;
      if (isFooterNode(node)) {
        return;
      }
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
        const footerNode = elements.find(
          (el: any) => el.parent === nid && isFooterNode(el)
        );
        if (footerNode) {
          const footerW = 260.0;
          const titleText = footerNode.title || footerNode.body || '';
          const lineCount = Math.max(1, Math.ceil((titleText.length * 7) / (footerW - 40)));
          const footerH = Math.max(48, 32 + lineCount * 18);
          padBottom += footerH + 16.0;
        }
        elkNode.layoutOptions = {
          'org.eclipse.elk.algorithm': 'layered',
          'org.eclipse.elk.direction': direction === 'column' ? 'DOWN' : 'RIGHT',
          'org.eclipse.elk.spacing.nodeNode': String(gap),
          'org.eclipse.elk.layered.spacing.nodeNodeBetweenLayers': String(gap),
          'org.eclipse.elk.spacing.edgeNode': '20',
          'org.eclipse.elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
          'org.eclipse.elk.edgeRouting': 'ORTHOGONAL',
          'org.eclipse.elk.portConstraints': 'FIXED_SIDE',
          'org.eclipse.elk.padding': `[top=${topPad},left=${padLeft},bottom=${padBottom},right=${padRight}]`
        };

      } else {
        const W = node.width || 200;
        const H = node.height || 80;
        elkNode.width = W;
        elkNode.height = H;
        
        elkNode.layoutOptions = {
          'org.eclipse.elk.portConstraints': 'FIXED_SIDE'
        };
        
        elkNode.ports = [
          {
            id: `${nid}-port-top`,
            width: 1,
            height: 1,
            x: W / 2,
            y: 0,
            layoutOptions: { 'org.eclipse.elk.port.side': 'NORTH' }
          },
          {
            id: `${nid}-port-bottom`,
            width: 1,
            height: 1,
            x: W / 2,
            y: H,
            layoutOptions: { 'org.eclipse.elk.port.side': 'SOUTH' }
          },
          {
            id: `${nid}-port-left`,
            width: 1,
            height: 1,
            x: 0,
            y: H / 2,
            layoutOptions: { 'org.eclipse.elk.port.side': 'WEST' }
          },
          {
            id: `${nid}-port-right`,
            width: 1,
            height: 1,
            x: W,
            y: H / 2,
            layoutOptions: { 'org.eclipse.elk.port.side': 'EAST' }
          }
        ];
      }
      elkNodes[nid] = elkNode;
    });

    const topRootPad = title ? 150 : 60;
    const rootAlgorithm = layoutAlgorithm || 'layered';
    const rootDirection = layoutDirection === 'vertical' ? 'DOWN' : 'RIGHT';

    const elkRoot: any = {
      id: 'root',
      layoutOptions: {
        'org.eclipse.elk.algorithm': rootAlgorithm,
        'org.eclipse.elk.direction': rootDirection,
        'org.eclipse.elk.spacing.nodeNode': '60',
        'org.eclipse.elk.layered.spacing.nodeNodeBetweenLayers': '70',
        'org.eclipse.elk.spacing.edgeNode': '25',
        'org.eclipse.elk.spacing.edgeEdge': '12',
        'org.eclipse.elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
        'org.eclipse.elk.cycleBreaking.strategy': 'GREEDY',
        'org.eclipse.elk.edgeRouting': 'ORTHOGONAL',
        'org.eclipse.elk.hierarchyHandling': 'INCLUDE_CHILDREN',
        'org.eclipse.elk.portConstraints': 'FIXED_SIDE',
        'org.eclipse.elk.padding': `[top=${topRootPad},left=40,bottom=40,right=40]`
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
        edgeOpts['org.eclipse.elk.layered.feedback'] = 'true';
      }

      const src = getTopParent(srcId);
      const tgt = getTopParent(tgtId);
      const exitPort = conn.exitPort || conn.fromPort || 'bottom';
      const entryPort = conn.entryPort || conn.toPort || 'top';
      const srcPortId = `${srcId}-port-${exitPort}`;
      const tgtPortId = `${tgtId}-port-${entryPort}`;

      if (src !== tgt) {
        edgeCounter++;
        const edge: any = {
          id: `edge-${srcId}-${tgtId}-${i}`,
          sources: [srcPortId],
          targets: [tgtPortId]
        };
        if (Object.keys(edgeOpts).length > 0) {
          edge.layoutOptions = edgeOpts;
        }
        elkRoot.edges.push(edge);
      } else {
        const edge: any = {
          id: `edge-${srcId}-${tgtId}-${i}`,
          sources: [srcPortId],
          targets: [tgtPortId]
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

    // Run layout asynchronously using GWT dispatcher
    const layoutPromise = new Promise<any>((resolve) => {
      (self as any).postMessage = (msg: any) => {
        if (msg && msg.id === 42) {
          resolve(msg);
        }
      };
    });

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

    const layoutResult = await layoutPromise;
    console.log("WORKER: GWT execution completed. layoutResult:", JSON.stringify(layoutResult));

    (self as any).postMessage = originalPostMessage;

    if (layoutResult && !layoutResult.error && layoutResult.data) {
      const flatResultNodes: any[] = [];
      const collectNodes = (node: any) => {
        flatResultNodes.push(node);
        node.children?.forEach(collectNodes);
      };
      collectNodes(layoutResult.data);
      const resultMap = new Map<string, any>();
      flatResultNodes.forEach((n) => resultMap.set(n.id, n));

      // Post-process manually positioned panel footers and container bounds
      elements.forEach((node: any) => {
        if (node.type === 'panel') {
          const panelId = node.id;
          const resultPanel = resultMap.get(panelId);
          if (!resultPanel) return;

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

          const allChildren = flatResultNodes.filter(
            (n) => nodesMap.get(n.id)?.parent === panelId
          );

          if (allChildren.length > 0) {
            const maxRight = Math.max(...allChildren.map((c) => (c.x || 0) + (c.width || 200)));
            const maxBottom = Math.max(...allChildren.map((c) => (c.y || 0) + (c.height || 80)));
            resultPanel.width = Math.max(resultPanel.width, maxRight + padRight);
            resultPanel.height = Math.max(resultPanel.height, maxBottom + padBottom);
          }

          // Find the footer child node in the input elements list if present
          const footerNode = elements.find(
            (el: any) => el.parent === panelId && isFooterNode(el)
          );
          if (!footerNode) return;

          const otherChildren = allChildren.filter((n) => n.id !== footerNode.id);
          let maxY = 40;
          if (otherChildren.length > 0) {
            maxY = Math.max(...otherChildren.map((c) => (c.y || 0) + (c.height || 80)));
          }

          const footerW = Math.max(200.0, resultPanel.width - padLeft - padRight);
          const titleText = footerNode.title || footerNode.body || '';
          const lineCount = Math.max(1, Math.ceil((titleText.length * 7) / (footerW - 40)));
          const footerH = Math.max(48, 32 + lineCount * 18);

          const inputFooter = elements.find((el: any) => el.id === footerNode.id);
          if (inputFooter) {
            inputFooter.width = footerW;
            inputFooter.height = footerH;
          }

          const footerX = padLeft + (resultPanel.width - padLeft - padRight - footerW) / 2.0;
          const footerY = maxY + 16.0;

          const resultFooter: any = {
            id: footerNode.id,
            x: footerX,
            y: footerY,
            width: footerW,
            height: footerH
          };

          if (!resultPanel.children) {
            resultPanel.children = [];
          }
          if (!resultPanel.children.some((c: any) => c.id === footerNode.id)) {
            resultPanel.children.push(resultFooter);
          }

          const neededPanelH = footerY + footerH + padBottom;
          resultPanel.height = Math.max(resultPanel.height, neededPanelH);
        }
      });

      self.postMessage({ success: true, graph: layoutResult.data });
    } else {
      console.error("WORKER: Layout failed, layoutResult error:", layoutResult?.error);
      self.postMessage({ success: false, error: layoutResult?.error?.message || 'GWT layout failed' });
    }
  } catch (err: any) {
    self.postMessage({ success: false, error: err.message });
  }
};

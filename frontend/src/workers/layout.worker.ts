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

function computeNodeDimensions(node: any): { width: number; height: number } {
  const w = Number(node.width || 0);
  const h = Number(node.height || 0);
  if (w > 0 && h > 0) {
    return { width: w, height: h };
  }

  const title = String(node.title || node.label || node.id || '');
  const subtitle = String(node.subtitle || '');
  const badge = String(node.badge || '');
  const hasIcon = Boolean(node.icon);

  const horizPad = 36 + (hasIcon ? 28 : 0) + (badge ? 30 : 0);
  const charsPerLine = 22;
  const lines = title ? Math.max(1, Math.ceil(title.length / charsPerLine)) : 1;

  const maxLineLen = title ? Math.max(...title.split('\n').map((l: string) => l.length)) : 0;
  const calcW = title ? Math.max(180, Math.min(360, maxLineLen * 9.5 + horizPad)) : 200;
  const calcH = Math.max(72, 36 + lines * 20 + (subtitle ? 18 : 0));

  return { width: Math.max(w, calcW), height: Math.max(h, calcH) };
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
        panelHeaders[node.id] = topPad + 15.0;
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
          'org.eclipse.elk.layered.spacing.nodeNodeBetweenLayers': String(gap + 15),
          'org.eclipse.elk.spacing.edgeNode': '20',
          'org.eclipse.elk.layered.nodePlacement.strategy': 'BALANCED',
          'org.eclipse.elk.edgeRouting': 'ORTHOGONAL',
          'org.eclipse.elk.portConstraints': 'FIXED_SIDE',
          'org.eclipse.elk.padding': `[top=${topPad},left=${padLeft},bottom=${padBottom},right=${padRight}]`
        };

      } else {
        const { width: W, height: H } = computeNodeDimensions(node);
        node.width = W;
        node.height = H;
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
        'org.eclipse.elk.spacing.nodeNode': '70',
        'org.eclipse.elk.layered.spacing.nodeNodeBetweenLayers': '80',
        'org.eclipse.elk.spacing.edgeNode': '25',
        'org.eclipse.elk.spacing.edgeEdge': '15',
        'org.eclipse.elk.layered.nodePlacement.strategy': 'BALANCED',
        'org.eclipse.elk.cycleBreaking.strategy': 'GREEDY',
        'org.eclipse.elk.edgeRouting': 'ORTHOGONAL',
        'org.eclipse.elk.hierarchyHandling': 'INCLUDE_CHILDREN',
        'org.eclipse.elk.portConstraints': 'FIXED_SIDE',
        'org.eclipse.elk.padding': `[top=${topRootPad},left=50,bottom=50,right=50]`
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

      // Post-process manually positioned panel footers and container bounds (bottom-up depth order)
      const getPanelDepth = (id: string): number => {
        let depth = 0;
        let curr = nodesMap.get(id);
        while (curr && curr.parent) {
          depth++;
          curr = nodesMap.get(curr.parent);
        }
        return depth;
      };

      const panelElements = elements.filter((node: any) => node.type === 'panel' || node.type === 'group');
      panelElements.sort((a: any, b: any) => getPanelDepth(b.id) - getPanelDepth(a.id));

      panelElements.forEach((node: any) => {
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
          resultPanel.width = Math.max(resultPanel.width || 200, maxRight + padRight);
          resultPanel.height = Math.max(resultPanel.height || 100, maxBottom + padBottom);
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
      });

      // Post-process hero summary nodes to position them top-centered and shift other graph nodes down
      const heroNodes = elements.filter((n: any) =>
        n.type === 'hero' || n.type === 'hero_card' || n.variant === 'hero' || n.variant === 'hero_card' || (n.id && n.id.startsWith('hero'))
      );
      if (heroNodes.length > 0) {
        let totalHeroH = 0;
        heroNodes.forEach((h: any) => {
          totalHeroH += (h.height || 120.0) + 30.0;
        });

        // Shift top-level non-hero nodes down
        flatResultNodes.forEach((n: any) => {
          if (!nodesMap.get(n.id)?.parent && !heroNodes.some((hn: any) => hn.id === n.id) && n.y !== undefined) {
            n.y += totalHeroH;
          }
        });

        // Center hero nodes across main graph bounding box
        const otherNodes = flatResultNodes.filter((n: any) =>
          !nodesMap.get(n.id)?.parent && !heroNodes.some((hn: any) => hn.id === n.id) && n.x !== undefined
        );
        let graphCenterX = 1000.0;
        if (otherNodes.length > 0) {
          const minX = Math.min(...otherNodes.map((n: any) => n.x || 0));
          const maxR = Math.max(...otherNodes.map((n: any) => (n.x || 0) + (n.width || 0)));
          graphCenterX = (minX + maxR) / 2.0;
        }

        let currHeroY = 130.0;
        heroNodes.forEach((hero: any) => {
          const resHero = resultMap.get(hero.id);
          if (resHero) {
            const hw = hero.width || 1400.0;
            resHero.x = graphCenterX - (hw / 2.0);
            resHero.y = currHeroY;
            resHero.width = hw;
            resHero.height = hero.height || 120.0;
            currHeroY += (hero.height || 120.0) + 20.0;
          }
        });
      }

      self.postMessage({ success: true, graph: layoutResult.data });
    } else {
      console.error("WORKER: Layout failed, layoutResult error:", layoutResult?.error);
      self.postMessage({ success: false, error: layoutResult?.error?.message || 'GWT layout failed' });
    }
  } catch (err: any) {
    self.postMessage({ success: false, error: err.message });
  }
};

const ELK = require('elkjs');
const fs = require('fs');

const elk = new ELK();

// Read spec v2 JSON
const spec = JSON.parse(fs.readFileSync('assets/default-spec-v2.json', 'utf8'));

// Flatten elements (simplified from specCompiler)
const flatElements = [];
function flattenElement(el, parentId = null) {
  const cloned = { ...el, parent: el.parent || parentId };
  flatElements.push(cloned);
  
  // Sizing
  if (cloned.type === 'card') {
    cloned.width = 260;
    cloned.height = 110;
  } else if (cloned.type === 'input') {
    cloned.width = 220;
    cloned.height = 42;
  } else if (cloned.type === 'diamond') {
    cloned.width = 200;
    cloned.height = 200;
  }
  
  if (el.children) {
    el.children.forEach(child => flattenElement(child, el.id));
  }
  if (el.footer) {
    flattenElement({
      id: el.footer.id || `${el.id}_footer`,
      type: el.footer.type || 'card',
      title: el.footer.title || '',
      body: el.footer.body || '',
      _role: 'footer'
    }, el.id);
  }
}
spec.elements.forEach(el => flattenElement(el));

// Build ELK graph (from layout.worker.ts)
const panelHeaders = {};
flatElements.forEach((node) => {
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

const elkNodes = {};
flatElements.forEach((node) => {
  const nid = node.id;
  if (nid.endsWith('_footer') || node._role === 'footer') {
    return;
  }
  const ntype = node.type;
  const elkNode = { id: nid, children: [], edges: [] };

  if (ntype === 'panel' || ntype === 'group') {
    const direction = node.layout?.direction || 'row';
    const gap = node.layout?.gap ?? 20;
    const topPad = panelHeaders[nid] || 40.0;
    let padLeft = 20, padBottom = 20, padRight = 20;
    
    elkNode.layoutOptions = {
      'elk.algorithm': 'layered',
      'elk.direction': direction === 'column' ? 'DOWN' : 'RIGHT',
      'elk.spacing.nodeNode': String(gap),
      'elk.layered.spacing.nodeNodeBetweenLayers': String(gap),
      'elk.spacing.edgeNode': '20',
      'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
      'elk.edgeRouting': 'ORTHOGONAL',
      'org.eclipse.elk.portConstraints': 'FIXED_SIDE',
      'elk.padding': `[top=${topPad},left=${padLeft},bottom=${padBottom},right=${padRight}]`
    };
  } else {
    const W = node.width || 200;
    const H = node.height || 80;
    elkNode.width = W;
    elkNode.height = H;
    
    // Crucial: Set portConstraints on leaf nodes too!
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

const elkRoot = {
  id: 'root',
  layoutOptions: {
    'elk.algorithm': 'layered',
    'elk.direction': 'RIGHT',
    'elk.spacing.nodeNode': '80',
    'elk.layered.spacing.nodeNodeBetweenLayers': '90',
    'elk.spacing.edgeNode': '30',
    'elk.spacing.edgeEdge': '15',
    'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
    'elk.cycleBreaking.strategy': 'GREEDY',
    'elk.edgeRouting': 'ORTHOGONAL',
    'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
    'org.eclipse.elk.portConstraints': 'FIXED_SIDE',
    'elk.padding': '[top=80,left=50,bottom=50,right=50]'
  },
  children: [],
  edges: []
};

flatElements.forEach((node) => {
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

function getTopParent(id) {
  let current = id;
  while (flatElements.find(el => el.id === current)?.parent) {
    current = flatElements.find(el => el.id === current).parent;
  }
  return current;
}

let edgeCounter = 0;
spec.connections.forEach((conn, i) => {
  const srcId = conn.from;
  const tgtId = conn.to;
  if (!elkNodes[srcId] || !elkNodes[tgtId]) return;

  const src = getTopParent(srcId);
  const tgt = getTopParent(tgtId);
  
  const exitPort = conn.exitPort || conn.fromPort || 'bottom';
  const entryPort = conn.entryPort || conn.toPort || 'top';
  const srcPortId = `${srcId}-port-${exitPort}`;
  const tgtPortId = `${tgtId}-port-${entryPort}`;

  if (src !== tgt) {
    edgeCounter++;
    const edge = {
      id: `edge-${srcId}-${tgtId}-${i}`,
      sources: [srcPortId],
      targets: [tgtPortId]
    };
    elkRoot.edges.push(edge);
  } else {
    const edge = {
      id: `edge-${srcId}-${tgtId}-${i}`,
      sources: [srcPortId],
      targets: [tgtPortId]
    };
    if (elkNodes[src]) {
      elkNodes[src].edges.push(edge);
    } else {
      elkRoot.edges.push(edge);
    }
  }
});

elk.layout(elkRoot).then(result => {
  console.log("SUCCESS");
  console.log("EDGES:");
  
  const printEdges = (node) => {
    if (node.edges) {
      node.edges.forEach(e => {
        console.log(`Edge: ${e.id}, Sections:`, JSON.stringify(e.sections, null, 2));
      });
    }
    if (node.children) {
      node.children.forEach(printEdges);
    }
  };
  printEdges(result);
  
}).catch(err => {
  console.error("ERROR", err);
});

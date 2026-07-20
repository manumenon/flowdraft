import { MarkerType } from '@xyflow/react';
import type { FlowSpec, ElementSpec, CanvasConfig } from '../types/spec';

export const THEMES: Record<string, Record<string, string>> = {
  dark: {
    bg: '#000000',
    white: '#f4f0ee',
    muted: '#cfc7c5',
    frame: '#5c6265',
    core_fill: '#04171e',
    core_stroke: '#1d8be8',
    green: '#22c86f',
    green_fill: '#02160a',
    purple: '#bd54d3',
    purple_fill: '#120814',
    cyan: '#7ee3d6',
    blue_fill: '#081626',
    highlight: '#124238',
    amber: '#f4b64e',
    pink: '#ff7ab6',
    archive_fill: '#080711',
    source_fill: '#02160a',
    pack_fill: '#04180d',
  },
  light: {
    bg: '#ffffff',
    white: '#111827',
    muted: '#4b5563',
    frame: '#6b7280',
    core_fill: '#dbeafe',
    core_stroke: '#0284c7',
    green: '#15803d',
    green_fill: '#dcfce7',
    purple: '#7c3aed',
    purple_fill: '#ede9fe',
    cyan: '#0891b2',
    blue_fill: '#dbeafe',
    highlight: '#99f6e4',
    amber: '#b45309',
    pink: '#be185d',
    archive_fill: '#ede9fe',
    source_fill: '#dcfce7',
    pack_fill: '#d1fae5',
  },
  white: {
    bg: '#ffffff',
    white: '#000000',
    muted: '#27272a',
    frame: '#09090b',
    core_fill: '#ffffff',
    core_stroke: '#09090b',
    green: '#09090b',
    green_fill: '#ffffff',
    purple: '#09090b',
    purple_fill: '#ffffff',
    cyan: '#09090b',
    blue_fill: '#ffffff',
    highlight: '#f4f4f5',
    amber: '#09090b',
    pink: '#09090b',
    archive_fill: '#ffffff',
    source_fill: '#ffffff',
    pack_fill: '#ffffff',
  },
};

export function adjustColor(color?: string | null, theme: string = 'dark'): string {
  if (!color) return '';
  if (theme === 'light' || theme === 'white') {
    const mappings: Record<string, string> = {
      '#000000': '#ffffff',
      '#f4f0ee': '#111827',
      '#cfc7c5': '#4b5563',
      '#5c6265': '#6b7280',
      '#04171e': '#dbeafe',
      '#1d8be8': '#0284c7',
      '#22c86f': '#15803d',
      '#02160a': '#dcfce7',
      '#bd54d3': '#7c3aed',
      '#120814': '#ede9fe',
      '#7ee3d6': '#0891b2',
      '#081626': '#dbeafe',
      '#124238': '#99f6e4',
      '#f4b64e': '#b45309',
      '#ff7ab6': '#be185d',
      '#080711': '#ede9fe',
      '#04180d': '#d1fae5',
      '#04200f': '#dcfce7',
      '#17091d': '#ede9fe',
      '#052515': '#dcfce7',
    };
    const colorLower = color.toLowerCase();
    return mappings[colorLower] || color;
  }
  return color;
}

export interface CompiledFlow {
  canvas: CanvasConfig;
  theme: string;
  themeColors: Record<string, string>;
  signature: string;
  title?: FlowSpec['title'];
  flatElements: ElementSpec[];
  rfNodes: any[];
  rfEdges: any[];
}

export function compileSpec(spec: FlowSpec, activeTheme?: string): CompiledFlow {
  const theme = activeTheme || (typeof spec.theme === 'string' ? spec.theme : 'dark');
  const themeColors = THEMES[theme] || THEMES.dark;

  // 1. Process Canvas configurations
  const rawCanvas = (spec.canvas || {}) as any;
  const canvas: CanvasConfig = {
    width: rawCanvas.width || 1920,
    height: rawCanvas.height || 1440,
    fps: rawCanvas.fps || 30,
    duration: rawCanvas.duration || 3,
    frames: rawCanvas.frames || 90,
    mode: rawCanvas.mode || 'dynamic',
  };

  const signature = spec.signature || '';
  const title = spec.title;

  // 2. Flatten elements (extracting nested children and footers)
  const flatElements: ElementSpec[] = [];
  const existingIds = new Set<string>();

  const flattenElement = (
    el: ElementSpec,
    parentId: string | null = null
  ) => {
    const clonedEl = { ...el, parent: el.parent || parentId };
    
    if (existingIds.has(clonedEl.id)) {
      console.warn(`Duplicate element ID: ${clonedEl.id}`);
      return;
    }
    existingIds.add(clonedEl.id);

    // Apply color remapping if style exists
    if (clonedEl.style) {
      const resolvedStyle = { ...clonedEl.style };
      if (resolvedStyle.color) {
        resolvedStyle.color = adjustColor(resolvedStyle.color, theme);
      }
      if (resolvedStyle.strokeColor) {
        resolvedStyle.strokeColor = adjustColor(resolvedStyle.strokeColor, theme);
      }
      clonedEl.style = resolvedStyle;
    }

    // Estimate sizes for leaf nodes
    if (clonedEl.type === 'card') {
      const bodyText = clonedEl.body || '';
      const lineCount = bodyText.split('\n').length;
      clonedEl.width = 240;
      clonedEl.height = Math.max(110, 80 + lineCount * 18);
    } else if (clonedEl.type === 'input') {
      clonedEl.width = 180;
      clonedEl.height = 42;
    } else if (clonedEl.type === 'diamond') {
      clonedEl.width = 180;
      clonedEl.height = 180;
    } else if (clonedEl.type === 'label') {
      clonedEl.width = 150;
      clonedEl.height = 36;
    } else if (clonedEl.type === 'group') {
      clonedEl.width = 220;
      clonedEl.height = 220;
    }

    flatElements.push(clonedEl);

    // Process nested children
    if (el.children && Array.isArray(el.children)) {
      el.children.forEach((child) => {
        flattenElement(child, el.id);
      });
    }

    // Process footer shorthand if it exists and type is panel
    if (el.type === 'panel' && el.footer) {
      const footerRaw = el.footer;
      const footerId = footerRaw.id || `${el.id}_footer`;
      const footerElem: ElementSpec = {
        id: footerId,
        type: (footerRaw.type as any) || 'label',
        title: footerRaw.title || footerRaw.body || '',
        style: footerRaw.style || {},
        _role: 'footer',
      };
      flattenElement(footerElem, el.id);
    }
  };

  if (Array.isArray(spec.elements)) {
    spec.elements.forEach((el) => flattenElement(el));
  }

  // 3. Compile to React Flow Nodes
  const rfNodes = flatElements.map((el) => {
    // If it's a panel, we don't set fixed width/height initially; let ELK compute it,
    // or keep a default style min-width/height.
    const style: Record<string, any> = {};
    if (el.width) style.width = el.width;
    if (el.height) style.height = el.height;

    return {
      id: el.id,
      type: el.type,
      position: { x: el.x || 0, y: el.y || 0 },
      parentId: el.parent || undefined,
      extent: el.parent ? 'parent' : undefined,
      style,
      data: {
        title: el.title,
        body: el.body,
        icon: el.icon,
        style: el.style,
        layout: el.layout,
        badge: el.badge,
        subtitle: el.subtitle,
        role: el._role,
      },
    };
  });

  // 4. Compile connections to React Flow Edges with parallel counts and source coloring
  const rawConnections = spec.connections || [];
  const edgeGroups: Record<string, number[]> = {};

  // Count connections sharing the same exit/entry ports
  const sourcePortGroups: Record<string, number[]> = {};
  const targetPortGroups: Record<string, number[]> = {};
  
  // Group connections arriving at the same target node + entryPort for target corridors
  const targetCorridorGroups: Record<string, number[]> = {};

  rawConnections.forEach((conn, idx) => {
    const exitPort = conn.exitPort || conn.fromPort || 'bottom';
    const entryPort = conn.entryPort || conn.toPort || 'top';
    const sourceKey = `${conn.from}-${exitPort}`;
    const targetKey = `${conn.to}-${entryPort}`;

    if (!sourcePortGroups[sourceKey]) {
      sourcePortGroups[sourceKey] = [];
    }
    sourcePortGroups[sourceKey].push(idx);

    if (!targetPortGroups[targetKey]) {
      targetPortGroups[targetKey] = [];
    }
    targetPortGroups[targetKey].push(idx);

    const corridorKey = `${conn.to}-${entryPort}`;
    if (!targetCorridorGroups[corridorKey]) {
      targetCorridorGroups[corridorKey] = [];
    }
    targetCorridorGroups[corridorKey].push(idx);
  });

  rawConnections.forEach((conn, idx) => {
    const u = conn.from;
    const v = conn.to;
    const key = u < v ? `${u}->${v}` : `${v}->${u}`;
    if (!edgeGroups[key]) {
      edgeGroups[key] = [];
    }
    edgeGroups[key].push(idx);
  });

  // Muted, desaturated palettes that blend with the Obsidian dark / clean light themes
  const SOURCE_PALETTE_DARK = [
    '#6b93c0', // steel blue
    '#6bae7c', // sage green
    '#c4a05a', // warm gold
    '#c07272', // dusty rose
    '#9b84c0', // lavender
    '#5ea8a8', // muted teal
    '#c07aa0', // mauve
    '#c08f5e', // burnt sand
    '#5eaca0', // seafoam
    '#8a82b8', // soft violet
    '#b8a84e', // olive gold
    '#7c8ac0', // slate indigo
  ];

  const SOURCE_PALETTE_LIGHT = [
    '#4472a8', // medium blue
    '#3a8a54', // forest green
    '#a07830', // dark gold
    '#a04848', // brick red
    '#7a5aa0', // muted purple
    '#2a8888', // deep teal
    '#a0507a', // plum
    '#a07040', // sienna
    '#2a8a7a', // dark seafoam
    '#6a62a0', // dark violet
    '#8a8030', // dark olive
    '#4a5a98', // navy
  ];

  // Collect unique source nodes in order of first appearance to assign colors consistently
  const uniqueSources: string[] = [];
  rawConnections.forEach((conn) => {
    if (!uniqueSources.includes(conn.from)) {
      uniqueSources.push(conn.from);
    }
  });

  const isDark = theme === 'dark';
  const palette = isDark ? SOURCE_PALETTE_DARK : SOURCE_PALETTE_LIGHT;
  const sourceColorMap: Record<string, string> = {};
  uniqueSources.forEach((srcId, index) => {
    sourceColorMap[srcId] = palette[index % palette.length];
  });

  const shouldAutoColor = uniqueSources.length >= 3;

  const rfEdges = rawConnections.map((conn, idx) => {
    const u = conn.from;
    const v = conn.to;
    const key = u < v ? `${u}->${v}` : `${v}->${u}`;
    const parallelIndex = edgeGroups[key].indexOf(idx);
    const parallelCount = edgeGroups[key].length;

    const exitPort = conn.exitPort || conn.fromPort || 'bottom';
    const entryPort = conn.entryPort || conn.toPort || 'top';
    const sourceKey = `${conn.from}-${exitPort}`;
    const targetKey = `${conn.to}-${entryPort}`;

    const sourceIndex = sourcePortGroups[sourceKey].indexOf(idx);
    const sourceCount = sourcePortGroups[sourceKey].length;
    const targetIndex = targetPortGroups[targetKey].indexOf(idx);
    const targetCount = targetPortGroups[targetKey].length;

    const corridorKey = `${conn.to}-${entryPort}`;
    const corridorIndex = targetCorridorGroups[corridorKey].indexOf(idx);
    const corridorCount = targetCorridorGroups[corridorKey].length;

    // Resolve color (conn.color override -> auto-assigned source color -> default theme color)
    const autoColor = shouldAutoColor ? sourceColorMap[conn.from] : undefined;
    let edgeColor = conn.color || autoColor || themeColors.muted;
    edgeColor = adjustColor(edgeColor, theme);

    return {
      id: `edge-${conn.from}-${conn.to}-${idx}`,
      source: conn.from,
      target: conn.to,
      sourceHandle: exitPort,
      targetHandle: entryPort,
      type: 'routed',
      zIndex: 10,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: edgeColor,
        width: 18,
        height: 18,
      },
      data: {
        color: edgeColor,
        style: conn.style || 'solid',
        label: conn.label,
        parallelIndex,
        parallelCount,
        sourceIndex,
        sourceCount,
        targetIndex,
        targetCount,
        corridorIndex,
        corridorCount,
        sourceNodeColor: autoColor,
      },
    };
  });

  return {
    canvas,
    theme,
    themeColors,
    signature,
    title,
    flatElements,
    rfNodes,
    rfEdges,
  };
}

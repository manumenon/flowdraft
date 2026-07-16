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

  // 4. Compile connections to React Flow Edges with parallel counts
  const rawConnections = spec.connections || [];
  const edgeGroups: Record<string, number[]> = {};

  rawConnections.forEach((conn, idx) => {
    const u = conn.from;
    const v = conn.to;
    const key = u < v ? `${u}->${v}` : `${v}->${u}`;
    if (!edgeGroups[key]) {
      edgeGroups[key] = [];
    }
    edgeGroups[key].push(idx);
  });

  const rfEdges = rawConnections.map((conn, idx) => {
    const u = conn.from;
    const v = conn.to;
    const key = u < v ? `${u}->${v}` : `${v}->${u}`;
    const parallelIndex = edgeGroups[key].indexOf(idx);
    const parallelCount = edgeGroups[key].length;

    // Resolve color
    let edgeColor = conn.color || themeColors.muted;
    edgeColor = adjustColor(edgeColor, theme);

    return {
      id: `edge-${conn.from}-${conn.to}-${idx}`,
      source: conn.from,
      target: conn.to,
      sourceHandle: conn.exitPort || conn.fromPort || 'bottom',
      targetHandle: conn.entryPort || conn.toPort || 'top',
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

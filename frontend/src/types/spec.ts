export type ElementType = 'card' | 'diamond' | 'panel' | 'input' | 'label' | 'group';
export type PortType = 'top' | 'bottom' | 'left' | 'right';
export type ConnectionStyle = 'solid' | 'dashed' | 'dotted';
export type AnnotationPosition =
  | 'top'
  | 'bottom'
  | 'left'
  | 'right'
  | 'midpoint'
  | 'top-left'
  | 'top-right'
  | 'bottom-left'
  | 'bottom-right'
  | 'top-label'
  | 'center';

export interface PaddingConfig {
  left?: number;
  right?: number;
  top?: number;
  bottom?: number;
}

export interface StyleConfig {
  strokeColor?: string;
  strokeWidth?: number;
  cornerRadius?: number;
  colorPreset?: string;
  color?: string;
  bold?: boolean;
  borderless?: boolean;
  transparent?: boolean;
  padding?: number | PaddingConfig;
  [key: string]: any;
}

export interface LayoutConfig {
  direction?: 'row' | 'column';
  gap?: number;
  max_cols?: number;
  grid_cols?: number;
  padding?: number | PaddingConfig;
}

export interface ElementSpec {
  id: string;
  type: ElementType;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  title?: string;
  body?: string;
  icon?: string | null;
  style?: StyleConfig;
  layout?: LayoutConfig;
  parent?: string | null;
  out_of_flow?: boolean;
  children?: ElementSpec[];
  footer?: Partial<ElementSpec> & { _role?: string };
  badge?: string;
  subtitle?: string;
  _role?: string;
  [key: string]: any; // Allow custom keys
}

export interface ConnectionSpec {
  from: string;
  to: string;
  exitPort?: PortType;
  entryPort?: PortType;
  fromPort?: PortType; // alias
  toPort?: PortType; // alias
  label?: string;
  style?: ConnectionStyle;
  color?: string;
}

export interface AnnotationSpec {
  text: string;
  attachTo?: string;
  from?: string;
  to?: string;
  position?: AnnotationPosition;
}

export interface CanvasConfig {
  width: number;
  height: number;
  fps?: number;
  duration?: number;
  frames?: number;
  mode?: 'dynamic' | 'absolute' | 'graph';
}

export interface TitleConfig {
  prefix?: string;
  highlight?: string;
  subtitle?: string;
}

export interface FlowSpec {
  canvas?: CanvasConfig;
  theme?: string | Record<string, any>;
  hand?: boolean;
  signature?: string;
  title?: TitleConfig;
  elements: ElementSpec[];
  connections?: ConnectionSpec[];
  annotations?: AnnotationSpec[];
  [key: string]: any;
}

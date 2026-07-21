# FlowDraft Frontend Application Architecture

The FlowDraft frontend is a modern React 18 single page application built with Vite and TypeScript, featuring real-time node-graph editing and GSAP path animation.

---

## 1. Component Structure & Hierarchy

```
frontend/src/
├── App.tsx                    # Main Application Container & Route Dispatcher
├── main.tsx                   # React DOM Root Mount
├── index.css                  # Design System Tokens & Base CSS Rules
├── components/
│   ├── Canvas.tsx             # Interactive XYFlow (React Flow) Diagram Surface
│   ├── PropertyEditor.tsx     # Node/Edge Property & Spec Editor Panel
│   ├── ProjectSidebar.tsx     # Diagram Project File Manager
│   ├── CommandPalette.tsx     # Keyboard-driven Command Palette (Ctrl+K)
│   ├── ExportPanel.tsx        # Video / GIF Export Progress & Trigger Modal
│   ├── AuthModal.tsx          # Login & Registration Dialog
│   ├── nodes/                 # Custom React Flow Node Renderers (Cards, Inputs, Panels)
│   └── edges/                 # Custom React Flow Animated Flow Path Connections
├── hooks/                     # Custom React Hooks (Auth, Diagram Sync, Keyboard Shortcuts)
├── types/                     # TypeScript Spec Definitions
├── utils/                     # Flow Spec Parsers & Serialization Utilities
└── workers/
    └── layout.worker.ts       # Web Worker running ELKjs Off-Thread Layout Engine
```

---

## 2. Off-Thread Layout Web Worker (`layout.worker.ts`)

To maintain 60 FPS UI interaction even with complex diagrams containing hundreds of nodes, layout hierarchy calculations are offloaded to a dedicated Web Worker running **ELKjs**.

### Workflow
1. When nodes or connections are edited in `Canvas.tsx`, a message containing the unpositioned graph nodes is dispatched to `layout.worker.ts`.
2. The Web Worker executes ELKjs layered layout routines asynchronously off the main thread.
3. Upon completion, calculated X/Y coordinates and routed edge bends are posted back to the main thread.
4. `Canvas.tsx` updates React Flow state smoothly without causing UI thread jank.

---

## 3. GSAP Animation & Frame-Control Clock

FlowDraft uses **GreenSock Animation Platform (GSAP)** with `MotionPathPlugin` to animate telemetry pulses along path connections.

### Interactive Mode (Normal UI)
- GSAP's global ticker drives smooth requestAnimationFrame pulses along connection SVGs.

### Headless Capture Mode (`/render-box`)
When loaded under the `/render-box` route by the Playwright Render Worker:
- `Canvas.tsx` detects the route and exposes `window.__CLOCK_CONTROLLER__`:
  ```javascript
  window.__CLOCK_CONTROLLER__ = {
    freeze: () => { /* Pause GSAP ticker & auto-render loop */ },
    seek: (timeMs) => { /* Seek GSAP timeline to exact millisecond offset */ }
  };
  ```
- Sets `window.__LAYOUT_COMPLETE__ = true` as soon as ELKjs finishes node positioning.
- This allows the Playwright worker daemon to pause time, step through frames at exact millisecond increments, take PNG screenshots, and compile stutter-free media.

---

## 4. Building & Running

### Development Mode
```bash
cd frontend
npm install
npm run dev
```
Serves the Vite app at `http://localhost:3000`.

### Production Build & Containerization
```bash
npm run build
```
Generates optimized static bundles in `frontend/dist/`. The provided `Dockerfile` serves the build using Nginx.

# FlowDraft Render Engine Troubleshooting Guide

This guide details the internal mechanisms of FlowDraft's rendering pipelines, focusing on layout synchronization, headless browser execution, timeline clock interception, and troubleshooting procedures for layout overlapping or rendering failures.

---

## 1. Web Worker Layout Engine Synchronization

### Problem Context
The ELKjs layout engine calculates coordinates to align cards, panels, and ports without collisions. However, ELKjs is compiled via GWT (Google Web Toolkit) and is packaged as a Web Worker (`elk-worker.min.js`). Web Workers execute asynchronously inside browsers by communicating via `postMessage` and `onmessage` event listeners.

In a normal browser environment, this asynchronous model is fine. However, in our headless Playwright rendering loop, we must capture frames at exact clock intervals. If layout runs asynchronously, the renderer cannot know exactly when the layout calculation completes, leading to race conditions where screenshots are taken before nodes settle, causing blank screens or misplaced components.

### Solution: Synchronous Message Interception
To solve this, FlowDraft's worker hook (`frontend/src/workers/layout.worker.ts`) implements a double-interception mechanism over the GWT worker's message dispatcher. This turns the asynchronous postMessage pipeline into a synchronous, call-stack block.

```
Main Thread                 layout.worker.ts                   GWT Engine (elk-worker)
    │                              │                                     │
    │ 1. Script Loaded             │                                     │
    ├─────────────────────────────►│                                     │
    │                              │ 2. Intercept self.postMessage       │
    │                              ├────────────────────────┐            │
    │                              │◄───────────────────────┘            │
    │                              │                                     │
    │                              │ 3. Import 'elk-worker.min.js'       │
    │                              ├────────────────────────────────────►│
    │                              │                                     │ GWT does:
    │                              │                                     │ postMessage({id: -1})
    │                              │◄────────────────────────────────────┤
    │                              │                                     │
    │                              │ 4. Capture self.onmessage           │
    │                              │    (gwtDispatcher)                  │
    │                              ├──────────────────────┐              │
    │                              │◄─────────────────────┘              │
    │                              │                                     │
    │                              │ 5. Restore self.postMessage         │
    │                              │    & Send 'ready' to Main           │
    ├◄─────────────────────────────┤                                     │
    │                              │                                     │
    │ 6. Send layout request data  │                                     │
    ├─────────────────────────────►│                                     │
    │                              │ 7. Map elements to ELK graph data   │
    │                              ├──────────────────────┐              │
    │                              │◄─────────────────────┘              │
    │                              │                                     │
    │                              │ 8. Intercept self.postMessage again │
    │                              ├──────────────────────┐              │
    │                              │◄─────────────────────┘              │
    │                              │                                     │
    │                              │ 9. Execute gwtDispatcher(graph)     │
    │                              │    (Runs synchronously)             │
    │                              ├────────────────────────────────────►│
    │                              │                                     │ GWT computes and calls
    │                              │                                     │ postMessage(msg)
    │                              │◄────────────────────────────────────┤
    │                              │                                     │
    │                              │ 10. Capture result in layoutResult  │
    │                              ├──────────────────────┐              │
    │                              │◄─────────────────────┘              │
    │                              │                                     │
    │                              │ 11. Restore original postMessage    │
    │                              ├──────────────────────┐              │
    │                              │◄─────────────────────┘              │
    │                              │                                     │
    │ 12. Return completed graph   │                                     │
    ├◄─────────────────────────────┤                                     │
```

#### Step 1: Initial Hook Registration & Dispatcher Capture
1. When the web worker script loads, the worker stores the original global `self.postMessage` in a local reference: `const originalPostMessage = self.postMessage;`.
2. It overwrites `self.postMessage` with a temporary interceptor.
3. The GWT engine script `elk-worker.min.js` is imported. During its load sequence, it binds its internal handler to `self.onmessage` and sends an initialization check `postMessage({ id: -1 })`.
4. Our interceptor intercepts this `{ id: -1 }` message, copies the newly created handler from `self.onmessage` into a local variable (`const gwtDispatcher = (self as any).onmessage`), restores `self.postMessage = originalPostMessage`, and notifies the main thread that the layout engine is ready.
5. The worker initializes the algorithms list by calling `gwtDispatcher` synchronously: `gwtDispatcher({ data: { id: -1, cmd: 'register', ... } })`.

#### Step 2: Synchronous Computation on Request
1. When the main thread calls `worker.postMessage({ elements, connections })`, the worker's `onmessage` handler triggers.
2. It translates the React Flow nodes and edges into an ELK-compatible nested graph structure (`elkRoot`).
3. To perform layout calculation synchronously, it overrides `self.postMessage` a second time to capture GWT's output into a local variable:
   ```typescript
   let layoutResult: any = null;
   (self as any).postMessage = (msg: any) => {
     layoutResult = msg;
   };
   ```
4. It calls `gwtDispatcher` directly:
   ```typescript
   gwtDispatcher({
     data: { id: 42, cmd: 'layout', graph: elkRoot }
   });
   ```
   Because `gwtDispatcher` is a synchronous GWT javascript function executing on the same thread call stack, it completes the layout calculations and invokes the overwritten `self.postMessage` *before* returning execution back to our handler.
5. The calculation output is written immediately to `layoutResult`.
6. Finally, the worker restores `self.postMessage = originalPostMessage` and posts the mapped nodes coordinates back to the main thread. This completely bypasses the browser's asynchronous event loop.

---

## 2. Headless Playwright Capture Environment

The headless worker daemon (`backend/app/worker.py`) executes in a headless Linux/Windows environment to record frame captures.

### Execution Loop & Requirements
- **Playwright Launcher**: The worker uses `playwright.async_api.async_playwright` to spawn an instance of headless Chromium:
  ```python
  browser = await p.chromium.launch(headless=True)
  ```
- **Viewport Config**: The browser page viewport is sized exactly to the spec's canvas bounds. The width and height are forced to a minimum of 100px to prevent rendering exceptions:
  ```python
  width = max(100, canvas_spec.get("width", 1920))
  height = max(100, canvas_spec.get("height", 1080))
  page = await browser.new_page(viewport={"width": width, "height": height})
  ```
- **Network Synchronization**: The page loads the render box viewer with the base64 spec payload. It waits for the browser network stack to go idle (`wait_until="networkidle"`) and verifies that `window.__LAYOUT_COMPLETE__` is true (indicating the synchronous ELKjs calculations finished and components have mounted):
  ```python
  await page.goto(url, wait_until="networkidle")
  await page.wait_for_function(
      "typeof window.__LAYOUT_COMPLETE__ === 'undefined' || window.__LAYOUT_COMPLETE__ === true",
      timeout=15000
  )
  ```

---

## 3. Timeline Clock Control Mechanism

### Deterministic Rendering Challenge
If the browser runs animations normally (real-time ticks), capturing screenshots will fail to produce smooth videos. Depending on machine load, CPU spikes will skip frames, leading to stuttering, variable frame rates, and missing animation steps in the compiled MP4.

### GSAP Clock Freeze & Seek
To fix this, FlowDraft freezes the GSAP global ticker and advances time manually on a frame-by-frame basis, capturing a PNG screenshot at each step.

1. **Freezing the Timeline**:
   The worker executes JS inside the browser to freeze the timeline:
   ```javascript
   if (window.__CLOCK_CONTROLLER__) {
       window.__CLOCK_CONTROLLER__.freeze();
   }
   ```
   In the react frontend (`frontend/src/hooks/useClockHook.ts`), this is implemented by calling:
   - `gsap.ticker.sleep()`: Stops GSAP's real-time clock loops.
   - `gsap.updateRoot(0)` & `gsap.globalTimeline.time(0)`: Resets all active animation frames to time zero.
   - Recursively seeks all children timelines and tweens to `time(0)`.

2. **Frame-by-Frame Seek Loop**:
   The worker loops from frame `0` to the total target frame count. For each frame, it calculates the target seek time:
   ```python
   delta_ms = 1000.0 / fps
   seek_ms = i * delta_ms
   ```
   It triggers the clock seek and waits for browser reflow/repaint:
   - **Seek**: Calls `window.__CLOCK_CONTROLLER__.seek(seek_ms)`. In React, this runs `gsap.updateRoot(currentTime)` which recalculates interpolation values for all components.
   - **Settle**: Evaluates `() => new Promise(requestAnimationFrame)` to ensure the browser repaints the layout changes before taking the screenshot.
   - **Capture**: Call `await page.screenshot(type="png")` to capture the frame.

3. **FFmpeg Compilation**:
   The captured PNG bytes are piped sequentially into an FFmpeg subprocess.
   - **MP4 Codec**: Pipes images using `image2pipe` and encodes them to H.264 video with `yuv420p` pixel format (ensuring HTML5 compatibility):
     ```bash
     ffmpeg -y -framerate 30 -f image2pipe -i - -c:v libx264 -pix_fmt yuv420p -crf 18 -preset slow -movflags +faststart -an -vf scale="scale=trunc(iw/2)*2:trunc(ih/2)*2" output.mp4
     ```
   - **Optimized GIF Codec**: Performs a two-pass palette extraction to avoid grainy colors, splitting the input video stream to generate a 256-color palette before writing the GIF:
     ```bash
     ffmpeg -y -framerate 30 -f image2pipe -i - -filter_complex "[0:v]split[x][y];[x]palettegen[p];[y][p]paletteuse=dither=none" output.gif
     ```

---

## 4. Troubleshooting Guide & Remediation Steps

### A. Blank Video or Static Canvas (Animations Missing)
- **Symptoms**: Compiled MP4 or GIF displays a static representation of the diagram with no motion or pulses.
- **Root Cause**:
  1. The browser script failed to load `useClockHook` or `__CLOCK_CONTROLLER__` was not registered on `window`.
  2. A javascript syntax error occurred on page load, stopping GSAP initialization.
- **Verification**: Check worker logs. If the worker logs `Clock controller is not frozen`, it means `window.__CLOCK_CONTROLLER__` was missing.
- **Remediation**:
  - Verify that the frontend application is serving `/render-box` correctly.
  - Inspect the HTML head of `/render-box` locally using browser developer tools and check if the `window.__CLOCK_CONTROLLER__` object is reachable.
  - Ensure the spec's `canvas.duration` and `canvas.fps` are greater than 0.

### B. Element Overlapping or Collisions
- **Symptoms**: Cards overlap, labels collide with connections, or panel container bounds clip nested children.
- **Root Cause**:
  1. The GWT layout worker failed to load, causing the frontend to fall back to random absolute positions.
  2. The custom layout padding configurations inside `layout.worker.ts` were bypassed.
- **Verification**: Search frontend worker logs for `WORKER: GWT execution completed`. If not present, or if it logs `GWT layout failed`, the layout calculation failed.
- **Remediation**:
  - Check that `elkjs` version constraints match.
  - Review custom layout options on panels. Ensure padding formats match:
    ```json
    "layout": { "padding": { "top": 40, "left": 20, "bottom": 20, "right": 20 } }
    ```
  - Verify cyclic connection logic. If connections create feedback loops, ensure they are flagged using the custom helper `isFeedback(srcId, tgtId)` inside the layout worker to let ELK break cycles correctly.

### C. Playwright Timeout Failures
- **Symptoms**: Jobs fail with `Playwright TimeoutException: Timeout 15000ms exceeded`.
- **Root Cause**:
  1. The frontend application is offline, or `FRONTEND_URL` in the worker environment is pointing to the wrong host.
  2. The custom layout worker crashed during graph construction, preventing `window.__LAYOUT_COMPLETE__` from becoming true.
- **Verification**: Run `curl -I <FRONTEND_URL>` from inside the worker container. Check the worker exception trace to see if the timeout occurred during page load or layout wait.
- **Remediation**:
  - Double check Docker network linkages. In `docker-compose.yml`, the worker uses `http://frontend:3000` to resolve the frontend container.
  - Increase the layout timeout parameter in `render_frames` if layout contains hundreds of nodes.

### D. FFmpeg Compilation Errors
- **Symptoms**: Worker logs `RuntimeError: FFmpeg failed (exit code 1): ...`.
- **Root Cause**:
  1. The `ffmpeg` system binary is missing or not configured in system environment `PATH`.
  2. One of the screenshots captured was corrupt or empty, causing FFmpeg to reject the pipe input stream.
- **Remediation**:
  - Run `ffmpeg -version` in the worker shell. In the Docker container, the binary is provisioned via Alpine or Debian packages.
  - Check system memory. High-resolution canvas rendering (e.g. 4K specs) combined with high frame counts can cause worker OOMs during frame capture. Reduce `canvas.width` and `canvas.height` or configure lower FPS (e.g. 24fps).

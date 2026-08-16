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

import { buildElkGraph, postProcessLayoutResult } from './layoutCore';

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

self.onmessage = async (event: MessageEvent) => {
  console.log("WORKER: Received layout request event!");
  const { elements, connections, title, layoutDirection, layoutAlgorithm } = event.data;

  try {
    const elkRoot = buildElkGraph({ elements, connections, title, layoutDirection, layoutAlgorithm });

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
      const finalGraph = postProcessLayoutResult(layoutResult.data, elements, layoutDirection);
      self.postMessage({ success: true, graph: finalGraph });
    } else {
      console.error("WORKER: Layout failed, layoutResult error:", layoutResult?.error);
      self.postMessage({ success: false, error: layoutResult?.error?.message || 'GWT layout failed' });
    }
  } catch (err: any) {
    self.postMessage({ success: false, error: err.message });
  }
};

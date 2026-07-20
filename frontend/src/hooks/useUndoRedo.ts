import { useState, useCallback } from 'react';
import type { FlowSpec } from '../types/spec';

export function useUndoRedo(initialPresent: FlowSpec) {
  const [present, setPresent] = useState<FlowSpec>(initialPresent);
  const [past, setPast] = useState<FlowSpec[]>([]);
  const [future, setFuture] = useState<FlowSpec[]>([]);

  // Update present and push past state
  const setSpec = useCallback((newSpecOrUpdater: FlowSpec | ((prev: FlowSpec) => FlowSpec), skipHistory = false) => {
    setPresent((prevPresent) => {
      let nextPresent: FlowSpec;
      if (typeof newSpecOrUpdater === 'function') {
        nextPresent = newSpecOrUpdater(prevPresent);
      } else {
        nextPresent = newSpecOrUpdater;
      }

      // Check if actually changed to avoid redundant history states
      const prevStr = JSON.stringify(prevPresent);
      const nextStr = JSON.stringify(nextPresent);
      if (prevStr === nextStr) {
        return prevPresent;
      }

      if (!skipHistory) {
        setPast((prevPast) => [...prevPast, prevPresent]);
        setFuture([]); // Clear future stack
      }

      return nextPresent;
    });
  }, []);

  const undo = useCallback(() => {
    setPast((prevPast) => {
      if (prevPast.length === 0) return prevPast;
      const newPast = [...prevPast];
      const previous = newPast.pop()!;
      
      setPresent((currentPresent) => {
        setFuture((prevFuture) => [...prevFuture, currentPresent]);
        return previous;
      });
      
      return newPast;
    });
  }, []);

  const redo = useCallback(() => {
    setFuture((prevFuture) => {
      if (prevFuture.length === 0) return prevFuture;
      const newFuture = [...prevFuture];
      const next = newFuture.pop()!;
      
      setPresent((currentPresent) => {
        setPast((prevPast) => [...prevPast, currentPresent]);
        return next;
      });
      
      return newFuture;
    });
  }, []);

  const resetHistory = useCallback((newSpec: FlowSpec) => {
    setPast([]);
    setFuture([]);
    setPresent(newSpec);
  }, []);

  return {
    state: present,
    setState: setSpec,
    undo,
    redo,
    resetHistory,
    canUndo: past.length > 0,
    canRedo: future.length > 0,
    past,
    future
  };
}

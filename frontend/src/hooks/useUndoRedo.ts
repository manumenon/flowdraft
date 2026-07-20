import { useReducer, useCallback } from 'react';
import type { FlowSpec } from '../types/spec';

interface HistoryState {
  past: FlowSpec[];
  present: FlowSpec;
  future: FlowSpec[];
}

type HistoryAction =
  | { type: 'SET_STATE'; payload: FlowSpec | ((prev: FlowSpec) => FlowSpec); skipHistory?: boolean }
  | { type: 'UNDO' }
  | { type: 'REDO' }
  | { type: 'RESET'; payload: FlowSpec };

function historyReducer(state: HistoryState, action: HistoryAction): HistoryState {
  switch (action.type) {
    case 'SET_STATE': {
      const nextPresent = typeof action.payload === 'function' ? action.payload(state.present) : action.payload;
      const prevStr = JSON.stringify(state.present);
      const nextStr = JSON.stringify(nextPresent);
      if (prevStr === nextStr) {
        return state;
      }
      return {
        past: action.skipHistory ? state.past : [...state.past, state.present],
        present: nextPresent,
        future: action.skipHistory ? state.future : [],
      };
    }
    case 'UNDO': {
      if (state.past.length === 0) return state;
      const previous = state.past[state.past.length - 1];
      const newPast = state.past.slice(0, -1);
      return {
        past: newPast,
        present: previous,
        future: [...state.future, state.present],
      };
    }
    case 'REDO': {
      if (state.future.length === 0) return state;
      const next = state.future[state.future.length - 1];
      const newFuture = state.future.slice(0, -1);
      return {
        past: [...state.past, state.present],
        present: next,
        future: newFuture,
      };
    }
    case 'RESET': {
      return {
        past: [],
        present: action.payload,
        future: [],
      };
    }
    default:
      return state;
  }
}

export function useUndoRedo(initialPresent: FlowSpec) {
  const [state, dispatch] = useReducer(historyReducer, {
    past: [],
    present: initialPresent,
    future: [],
  });

  const setSpec = useCallback((newSpecOrUpdater: FlowSpec | ((prev: FlowSpec) => FlowSpec), skipHistory = false) => {
    dispatch({ type: 'SET_STATE', payload: newSpecOrUpdater, skipHistory });
  }, []);

  const undo = useCallback(() => {
    dispatch({ type: 'UNDO' });
  }, []);

  const redo = useCallback(() => {
    dispatch({ type: 'REDO' });
  }, []);

  const resetHistory = useCallback((newSpec: FlowSpec) => {
    dispatch({ type: 'RESET', payload: newSpec });
  }, []);

  return {
    state: state.present,
    setState: setSpec,
    undo,
    redo,
    resetHistory,
    canUndo: state.past.length > 0,
    canRedo: state.future.length > 0,
    past: state.past,
    future: state.future,
  };
}

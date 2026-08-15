import type { QualityNode, QualityCheckResult } from './types';

/**
 * Cheap sanity check: every positioned node has a unique id (Set size vs
 * array length). Ported from layout_quality.py's check_excalidraw_unique_ids,
 * adapted to layoutCore.ts's node shape (there is no Excalidraw-element
 * concept on the frontend, so this checks the flattened layout nodes
 * directly instead of a separate export-element list).
 */
export function checkUniqueNodeIds(nodes: QualityNode[]): QualityCheckResult {
  const ids = nodes.map((n) => n.id);
  const uniqueIds = new Set(ids);

  const seen = new Set<string>();
  const duplicates = new Set<string>();
  ids.forEach((id) => {
    if (seen.has(id)) duplicates.add(id);
    seen.add(id);
  });

  return {
    name: 'unique_node_ids',
    ok: uniqueIds.size === ids.length,
    total: ids.length,
    uniqueCount: uniqueIds.size,
    duplicates: Array.from(duplicates).sort(),
  };
}

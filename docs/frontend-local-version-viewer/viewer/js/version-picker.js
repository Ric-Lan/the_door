// Pure helper: given a snapshot object, return the preferred ref string
// used in /api/diff query params (and any other endpoint that accepts
// label/tag/SHA via _resolve_snapshot_id).
//
// Priority: git_tags[0] > label > version_id (UUID fallback).
//
// Keep version_id as a final fallback so unlabeled snapshots still resolve.
export function pickRef(snapshot) {
  if (snapshot.git_tags && snapshot.git_tags.length > 0) return snapshot.git_tags[0];
  if (snapshot.label) return snapshot.label;
  return snapshot.version_id;
}

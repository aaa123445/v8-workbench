// One-time, memory-only handoff from the newly created personal key panel.
let pendingKey = "";
export function handoffConnectionKey(key) {
  pendingKey = key;
}
export function takeConnectionKey() {
  const key = pendingKey;
  pendingKey = "";
  return key;
}

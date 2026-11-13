// Overlay lifetimes can overlap or end out of order during route/resource updates.
const locks = new Set();
let previousOverflow = "";
export function lockBodyScroll() {
  const owner = Symbol("overlay");
  if (!locks.size) previousOverflow = document.body.style.overflow;
  locks.add(owner);
  document.body.style.overflow = "hidden";
  return () => {
    if (!locks.delete(owner)) return;
    if (!locks.size) document.body.style.overflow = previousOverflow;
  };
}

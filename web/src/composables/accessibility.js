export function focusMain() {
  const main = document.getElementById("main");
  main?.focus({ preventScroll: true });
  main?.scrollIntoView({ block: "start" });
}
export function trapFocus(event, root) {
  if (event.key !== "Tab" || !root) return;
  const elements = [
    ...root.querySelectorAll(
      "a[href],button:not(:disabled),input,select,textarea",
    ),
  ].filter(
    (el) =>
      el.getClientRects().length &&
      getComputedStyle(el).visibility !== "hidden",
  );
  if (!elements.length) return;
  const first = elements[0],
    last = elements.at(-1);
  if (!root.contains(document.activeElement)) {
    event.preventDefault();
    first.focus();
  } else if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

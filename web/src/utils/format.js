export function plainText(value = "") {
  return String(value)
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/<[^>]*>/g, "")
    .replace(/(?:^|\n)\s{0,3}#{1,6}\s+/g, " ")
    .replace(/[`*_~>|]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}
export function formatDate(ts) {
  if (!ts) return "时间未记录";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(ts * 1000));
}
export function relativeDate(ts) {
  if (!ts) return "团队知识";
  const days = Math.floor((Date.now() - ts * 1000) / 86400000);
  if (days < 0) return formatDate(ts);
  if (days === 0) return "今天更新";
  if (days === 1) return "昨天更新";
  if (days < 7) return `${days} 天前更新`;
  return `${new Date(ts * 1000).getFullYear()}/${formatDate(ts)} 更新`;
}
export function categoryTone(id = "") {
  const roots = {
    technology: "blue",
    platforms: "violet",
    business: "teal",
    projects: "amber",
    standards: "rose",
    uncategorized: "blue",
  };
  if (roots[id]) return roots[id];
  let hash = 0;
  for (const c of id) hash = (hash * 31 + c.charCodeAt(0)) >>> 0;
  return ["blue", "violet", "amber", "teal", "rose"][hash % 5];
}

export const operations = {
  propose: "贡献提交",
  review: "贡献审核",
  rollback: "版本回滚",
  categories: "知识分类",
  library: "分类浏览",
  standards: "团队规范",
  search: "知识检索",
  read: "文档阅读",
  rules: "开发规范",
  domains: "知识领域",
  stats: "知识统计",
  recent: "最近更新",
  submit: "知识提交",
  submit_batch: "批量提交",
  delete: "删除知识",
  sync: "语雀同步",
  rebuild: "重建索引",
};
export const clients = {
  web: "网页",
  mcp: "MCP",
  cli: "CLI",
  api: "API / 其他客户端",
};
export const outcomes = {
  success: "成功",
  partial: "部分成功",
  failed: "失败",
};
export const formatTime = (timestamp) =>
  new Date(timestamp * 1000).toLocaleString("zh-CN", { hour12: false });
export const formatDuration = (value) =>
  value >= 1000
    ? `${(value / 1000).toFixed(2)} s`
    : `${Number(value).toFixed(1)} ms`;
export const formatSnapshot = (value) =>
  value && Object.keys(value).length === 1 && typeof value.preview === "string"
    ? value.preview
    : JSON.stringify(value, null, 2);

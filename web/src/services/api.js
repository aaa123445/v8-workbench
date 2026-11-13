export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}
export async function api(
  path,
  {
    method = "GET",
    body,
    signal,
    key = localStorage.getItem("v8wb_key") || "",
  } = {},
) {
  let response;
  try {
    response = await fetch("/api/v1" + path, {
      method,
      signal,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "V8Workbench",
        "X-V8WB-Client": "web",
        ...(key ? { Authorization: `Bearer ${key}` } : {}),
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError("网络连接失败，请检查网络后重试。", 0);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail || data;
    const messages = {
      401: "登录已失效或 API Key 无效，请重新登录或配置 Key。",
      403: "当前 Key 没有此操作的权限。",
      429: "请求额度已用尽，请稍后重试。",
    };
    throw new ApiError(
      (response.status !== 401 && detail.message) ||
        messages[response.status] ||
        detail.message ||
        detail.error ||
        `请求失败（${response.status}）`,
      response.status,
    );
  }
  return data;
}
export const post = (path, body = {}, options = {}) =>
  api(path, { ...options, method: "POST", body });

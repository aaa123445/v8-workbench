/* V8 客开工作台前端。
 *
 * 设计取舍：
 * - 零构建、零依赖。一个 CDN 都不引，服务器上不装 node，丢进静态目录就能跑。
 * - 逻辑上跟 CLI 完全一致：同样的 REST 接口，同样的错误处理。
 * - 状态只在内存 + localStorage（只存 key），不做路由库，hash 路由够了。
 */

const S = {
  key: localStorage.getItem('v8wb_key') || '',
  view: 'search',
  query: '',
  domain: '',
  results: [],
  doc: null,
  loading: false,
  stats: null,
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') n.className = v;
    else if (k === 'html') n.innerHTML = v;
    else if (k.startsWith('on')) n.addEventListener(k.slice(2).toLowerCase(), v);
    else if (v !== null && v !== undefined && v !== false) n.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    n.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return n;
};
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function toast(msg, kind = '') {
  const t = $('#toast');
  t.textContent = msg;
  t.className = 'toast show ' + kind;
  clearTimeout(t._h);
  t._h = setTimeout(() => { t.className = 'toast ' + kind; }, 3200);
}

async function api(path, payload, method = 'POST') {
  const opt = { method, headers: { 'Content-Type': 'application/json' } };
  if (S.key) opt.headers.Authorization = 'Bearer ' + S.key;
  if (payload !== undefined && method !== 'GET') opt.body = JSON.stringify(payload);
  let r;
  try {
    r = await fetch('/api/v1' + path, opt);
  } catch (e) {
    throw new Error('网络错误：' + e.message);
  }
  if (r.status === 401) throw new Error('API Key 无效或未设置，请在右上角填入');
  if (r.status === 403) throw new Error('权限不足，需要更高权限的 Key');
  if (r.status === 429) throw new Error('调用额度超限，请稍后再试');
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = data.detail || data;
    throw new Error(d.message || d.error || `请求失败 ${r.status}`);
  }
  return data;
}

/* ---------------- Markdown ---------------- */
/* 不引库，只处理语雀文档里实际出现的语法。够用比全量更重要。 */
function md(src) {
  const lines = String(src || '').split('\n');
  const out = [];
  let inCode = false, codeBuf = [], listType = null;

  const flushList = () => { if (listType) { out.push(`</${listType}>`); listType = null; } };

  for (let i = 0; i < lines.length; i++) {
    let ln = lines[i];

    if (/^```/.test(ln)) {
      if (inCode) {
        out.push('<pre><code>' + esc(codeBuf.join('\n')) + '</code></pre>');
        codeBuf = []; inCode = false;
      } else { flushList(); inCode = true; }
      continue;
    }
    if (inCode) { codeBuf.push(ln); continue; }

    if (!ln.trim()) { flushList(); continue; }

    // 表格
    if (/\|/.test(ln) && /^\s*\|/.test(ln) && lines[i + 1] && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      flushList();
      const cells = (s) => s.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
      const head = cells(ln);
      let body = '<table><thead><tr>' + head.map((c) => `<th>${inline(c)}</th>`).join('') + '</tr></thead><tbody>';
      i += 2;
      while (i < lines.length && /^\s*\|/.test(lines[i])) {
        body += '<tr>' + cells(lines[i]).map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>';
        i++;
      }
      i--;
      out.push(body + '</tbody></table>');
      continue;
    }

    const h = ln.match(/^(#{1,6})\s+(.*)$/);
    if (h) { flushList(); out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`); continue; }

    if (/^\s*[-*+]\s+/.test(ln)) {
      if (listType !== 'ul') { flushList(); out.push('<ul>'); listType = 'ul'; }
      out.push('<li>' + inline(ln.replace(/^\s*[-*+]\s+/, '')) + '</li>');
      continue;
    }
    if (/^\s*\d+\.\s+/.test(ln)) {
      if (listType !== 'ol') { flushList(); out.push('<ol>'); listType = 'ol'; }
      out.push('<li>' + inline(ln.replace(/^\s*\d+\.\s+/, '')) + '</li>');
      continue;
    }
    if (/^>\s?/.test(ln)) { flushList(); out.push('<blockquote>' + inline(ln.replace(/^>\s?/, '')) + '</blockquote>'); continue; }
    if (/^(---|\*\*\*|___)\s*$/.test(ln)) { flushList(); out.push('<hr>'); continue; }

    flushList();
    out.push('<p>' + inline(ln) + '</p>');
  }
  if (inCode && codeBuf.length) out.push('<pre><code>' + esc(codeBuf.join('\n')) + '</code></pre>');
  flushList();
  return out.join('\n');
}

function inline(s) {
  let t = esc(s);
  t = t.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img alt="$1" src="$2">');
  t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
  t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  t = t.replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>');
  return t;
}

/* ---------------- 视图 ---------------- */
function renderSidebar() {
  const items = [
    ['search', '⌕', '知识检索'],
    ['rules', '☰', '开发规范'],
    ['contribute', '＋', '经验沉淀'],
    ['overview', '▦', '知识总览'],
    ['admin', '⚙', '管理'],
  ];
  return el('aside', { class: 'sidebar' },
    el('div', { class: 'brand' },
      el('h1', {}, el('span', { class: 'dot' }), el('span', {}, 'V8 客开工作台')),
      el('div', { class: 'sub' }, '致远 V8 Workbench'),
    ),
    el('nav', { class: 'nav' },
      ...items.map(([k, ico, label]) =>
        el('button', {
          class: S.view === k ? 'active' : '',
          onclick: () => { S.view = k; render(); if (k === 'overview') loadStats(); }
        }, el('span', { class: 'ico' }, ico), el('span', {}, label))
      )
    ),
    el('div', { class: 'sidebar-foot' },
      el('a', { href: '/docs', target: '_blank' }, 'API 文档'),
      ' · v0.1.0'
    )
  );
}

function renderTopbar() {
  const input = el('input', {
    type: 'password',
    placeholder: '粘贴 API Key',
    value: S.key,
    onchange: async (e) => {
      S.key = e.target.value.trim();
      localStorage.setItem('v8wb_key', S.key);
      if (S.key) {
        try { await api('/stats', undefined, 'GET'); toast('Key 校验通过', 'ok'); render(); }
        catch (err) { toast(err.message, 'err'); }
      }
    },
  });
  return el('div', { class: 'topbar' },
    el('div', { class: 'keybar' },
      el('span', { class: 'status' }, S.key ? '🔑' : '⚠', S.key ? '已配置 Key' : '未配置 Key'),
      input,
    ),
    el('div', { class: 'spacer' }),
    el('button', { class: 'btn sm', onclick: () => { S.key = ''; localStorage.removeItem('v8wb_key'); render(); } }, '清除')
  );
}

/* ---------------- 检索 ---------------- */
function viewSearch() {
  const doSearch = async () => {
    const q = S.query.trim();
    if (!q) return;
    S.loading = true; render();
    try {
      const d = await api('/search', { query: q, limit: 20, domain: S.domain });
      S.results = d.results || [];
      S.hint = d.hint || '';
    } catch (e) { toast(e.message, 'err'); S.results = []; }
    S.loading = false; render();
  };

  const input = el('input', {
    placeholder: '用平台术语检索，如：组织同步 中间表 / SPI扩展 登录 / @seeyon/global',
    value: S.query,
    oninput: (e) => { S.query = e.target.value; },
    onkeydown: (e) => { if (e.key === 'Enter') doSearch(); },
  });

  const domains = ['', '开发规范', '扩展能力', '集成平台', '开发文档', 'UDC平台', 'BPM平台', '业务组件', '移动端开发', '门户平台'];

  const body = S.results.length
    ? S.results.map((r) => el('div', {
        class: 'card clickable',
        onclick: () => openDoc(r.id),
      },
        el('h3', {}, r.title,
          r.version_hint ? el('span', { class: 'tag' }, '版本 ' + r.version_hint) : null,
        ),
        r.path ? el('div', { class: 'path' }, r.path) : null,
        el('div', { class: 'meta' },
          ...(r.matched_terms || []).slice(0, 5).map((t) => el('span', { class: 'tag acc' }, t)),
          ...(r.reasons || []).map((t) => el('span', { class: 'tag ok' }, t)),
          el('span', { class: 'score' }, r.score.toFixed(1)),
        ),
      ))
    : el('div', { class: 'empty' },
        el('div', { class: 'big' }, '⌕'),
        S.query ? (S.loading ? '检索中…' : '无结果，换个更短的术语试试') : '输入关键词开始检索'
      );

  return el('div', {},
    el('div', { class: 'page-title' }, '知识检索'),
    el('div', { class: 'page-desc' }, '231 篇语雀 V8 客开文档 + 团队沉淀经验。用平台术语检索命中率最高。'),
    el('div', { class: 'searchbox' }, input,
      el('button', { class: 'btn primary', onclick: doSearch, disabled: S.loading },
        S.loading ? '检索中' : '检索')),
    el('div', { class: 'chips' },
      ...domains.map((d) => el('button', {
        class: 'chip' + (S.domain === d ? ' on' : ''),
        onclick: () => { S.domain = d; if (S.query) doSearch(); else render(); },
      }, d || '全部')),
    ),
    S.hint ? el('div', { class: 'page-desc', html: esc(S.hint) }) : null,
    el('div', {}, body),
  );
}

async function openDoc(id) {
  S.loading = true; render();
  try {
    const d = await api('/read', { id, max_chars: 200000 });
    S.doc = d;
    S.view = 'doc';
  } catch (e) { toast(e.message, 'err'); }
  S.loading = false; render();
}

function viewDoc() {
  const d = S.doc;
  if (!d) return el('div', { class: 'empty' }, '文档未加载');

  return el('div', {},
    el('button', { class: 'btn sm', onclick: () => { S.view = 'search'; render(); }, style: 'margin-bottom:16px' }, '← 返回检索'),
    el('div', { class: 'reader-head' },
      el('h2', {}, d.title),
      el('div', { class: 'meta' },
        d.path ? el('span', { class: 'mono' }, d.path) : null,
        d.version_hint ? el('span', { class: 'tag warn' }, '适用 ' + d.version_hint) : null,
        el('span', { class: 'tag' }, d.source === 'yuque' ? '语雀' : d.source === 'agent' ? 'Agent 沉淀' : d.source),
        d.url ? el('a', { href: d.url, target: '_blank', class: 'tag acc' }, '查看原文') : null,
      ),
    ),
    el('div', { class: 'prose', html: md(d.content) }),
  );
}

/* ---------------- 规范 ---------------- */
function viewRules() {
  const profiles = [
    ['spi', '后端 SPI 扩展'], ['udc', 'UDC 应用/组件'], ['bpm', 'BPM 流程扩展'],
    ['frontend', '前端扩展'], ['integration', '集成平台'], ['data', '数据库/迁移'],
    ['docs', '交付文档'], ['general', '通用客开'],
  ];
  const state = { picked: 'spi', data: null, loading: false };

  const host = el('div', {});

  const load = async (key) => {
    state.picked = key; state.loading = true; paint();
    try { state.data = await api('/rules', { task: key, include_docs: false }); }
    catch (e) { toast(e.message, 'err'); }
    state.loading = false; paint();
  };

  const paint = () => {
    host.innerHTML = '';
    host.append(
      el('div', { class: 'chips' },
        ...profiles.map(([k, label]) => el('button', {
          class: 'chip' + (state.picked === k ? ' on' : ''),
          onclick: () => load(k),
        }, label)),
      ),
    );
    if (state.loading) { host.append(el('div', { class: 'empty' }, el('span', { class: 'loading' }))); return; }
    const d = state.data;
    if (!d) return;

    const block = (title, items, icon) => items && items.length
      ? el('div', { class: 'card' },
          el('h3', {}, icon + ' ' + title),
          el('div', { html: items.map((x) => `<div style="padding:6px 0;border-bottom:1px solid var(--border)">${esc(x)}</div>`).join('') }),
        )
      : null;

    host.append(
      el('div', { class: 'card' },
        el('h3', {}, d.name),
        el('div', { class: 'path' }, '任务画像：' + d.profile),
        el('div', { class: 'meta' },
          el('span', { class: 'tag ok' }, '必读规范 ' + (d.must_read_titles || []).length + ' 篇'),
          el('span', { class: 'tag acc' }, '自查项 ' + (d.checklist || []).length + ' 条'),
        ),
      ),
      block('提交前自查', d.checklist, '☑'),
      block('常见坑', d.pitfalls, '⚠'),
      (() => {
        const idx = d.documents_index || [];
        if (!idx.length) return null;
        return el('div', { class: 'card' },
          el('h3', {}, '📚 必读文档'),
          el('div', {}, ...idx.map((x) => el('div', {
            style: 'padding:7px 0;border-bottom:1px solid var(--border);cursor:pointer;display:flex;justify-content:space-between;gap:10px',
            onclick: () => openDoc(x.id),
          },
            el('span', {}, x.title),
            el('span', { class: 'mono', style: 'color:var(--fg-3)' }, x.chars + ' 字 →'),
          ))),
        );
      })(),
    );
  };

  load('spi');

  return el('div', {},
    el('div', { class: 'page-title' }, '开发规范'),
    el('div', { class: 'page-desc' }, '按任务类型把散落的规范文档编排成可执行清单。动手前先选任务类型。'),
    host,
  );
}

/* ---------------- 沉淀 ---------------- */
function viewContribute() {
  const f = { title: '', content: '', project: '', tags: '', summary: '' };
  const status = el('div', { class: 'hint' });

  const submit = async () => {
    if (!f.title.trim() || f.content.trim().length < 20) {
      toast('标题必填，内容至少 20 字', 'err'); return;
    }
    status.textContent = '提交中…';
    try {
      const d = await api('/knowledge', {
        title: f.title, content: f.content, project: f.project,
        tags: f.tags.split(',').map((s) => s.trim()).filter(Boolean),
        summary: f.summary, source: 'manual',
      });
      const map = { created: '已新增', updated: '已更新', unchanged: '内容无变化，跳过' };
      toast((map[d.action] || d.action) + '：' + d.title, 'ok');
      status.textContent = 'doc_id: ' + d.id;
      f.title = ''; f.content = ''; f.summary = '';
      render();
    } catch (e) { toast(e.message, 'err'); status.textContent = ''; }
  };

  return el('div', {},
    el('div', { class: 'page-title' }, '经验沉淀'),
    el('div', { class: 'page-desc' }, '把文档里没写、靠试错才搞明白的平台行为沉淀进来。判断标准：半年后别人搜到能不能直接用。'),
    el('div', { class: 'card' },
      el('div', { class: 'field' },
        el('label', {}, '标题 ', el('span', { class: 'req' }, '*')),
        el('input', {
          placeholder: '含关键词，如：UDC 自定义页面白屏 平台上下文未注入',
          value: f.title, oninput: (e) => { f.title = e.target.value; },
        }),
        el('div', { class: 'hint' }, '以后别人会用这些词检索它，标题里要带上'),
      ),
      el('div', { class: 'row' },
        el('div', { class: 'field' },
          el('label', {}, '项目 / 客户'),
          el('input', { placeholder: '脱敏后填写', value: f.project, oninput: (e) => { f.project = e.target.value; } }),
        ),
        el('div', { class: 'field' },
          el('label', {}, '标签'),
          el('input', { placeholder: '逗号分隔，如 UDC,前端', value: f.tags, oninput: (e) => { f.tags = e.target.value; } }),
        ),
      ),
      el('div', { class: 'field' },
        el('label', {}, '内容 ', el('span', { class: 'req' }, '*')),
        el('textarea', {
          placeholder: '## 场景\n什么需求下会遇到\n\n## 现象\n报错信息 / 异常表现\n\n## 根因\n为什么\n\n## 解法\n具体怎么改，带关键代码\n\n## 适用版本\n在哪个 V8 版本验证过',
          value: f.content, oninput: (e) => { f.content = e.target.value; },
        }),
        el('div', { class: 'hint' }, '支持 Markdown。一条知识要能脱离上下文独立看懂。'),
      ),
      el('button', { class: 'btn primary', onclick: submit }, '提交入库'),
      status,
    ),
  );
}

/* ---------------- 总览 ---------------- */
async function loadStats() {
  try { S.stats = await api('/stats', undefined, 'GET'); render(); }
  catch (e) { /* 未配 key 时静默 */ }
}

function viewOverview() {
  const d = S.stats;
  if (!d) return el('div', { class: 'empty' }, el('span', { class: 'loading' }));
  const dom = Object.entries(d.by_domain || {});
  const src = Object.entries(d.by_source || {});
  return el('div', {},
    el('div', { class: 'page-title' }, '知识总览'),
    el('div', { class: 'page-desc' }, '当前知识库规模与分布。缺口在哪，一眼能看出来。'),
    el('div', { class: 'grid2', style: 'margin-bottom:20px' },
      el('div', { class: 'stat' }, el('div', { class: 'n' }, d.documents), el('div', { class: 'l' }, '文档总数')),
      el('div', { class: 'stat' }, el('div', { class: 'n' }, d.terms), el('div', { class: 'l' }, '索引词条')),
      el('div', { class: 'stat' }, el('div', { class: 'n' }, d.avg_body_len), el('div', { class: 'l' }, '平均长度')),
      el('div', { class: 'stat' }, el('div', { class: 'n' }, src.find(([k]) => k === 'agent')?.[1] || 0), el('div', { class: 'l' }, 'Agent 沉淀')),
    ),
    el('div', { class: 'card' },
      el('h3', {}, '按知识域'),
      el('table', { class: 'data' },
        el('tbody', {}, ...dom.map(([k, v]) => el('tr', {},
          el('td', {}, k), el('td', { class: 'mono', style: 'text-align:right' }, v))))),
    ),
    el('div', { class: 'card' },
      el('h3', {}, '按来源'),
      el('table', { class: 'data' },
        el('tbody', {}, ...src.map(([k, v]) => el('tr', {},
          el('td', {}, { yuque: '语雀同步', agent: 'Agent 沉淀', manual: '管理员上传', upload: '上传', 'corpus-import': '语料导入' }[k] || k),
          el('td', { class: 'mono', style: 'text-align:right' }, v))))),
    ),
  );
}

/* ---------------- 管理 ---------------- */
function viewAdmin() {
  const host = el('div', {});
  const keysBox = el('div', {}, el('div', { class: 'empty' }, el('span', { class: 'loading' })));
  const newKey = el('div', {});
  const st = { name: '', role: 'writer' };

  const loadKeys = async () => {
    try {
      const d = await api('/admin/keys', undefined, 'GET');
      keysBox.innerHTML = '';
      keysBox.append(el('table', { class: 'data' },
        el('thead', {}, el('tr', {},
          el('th', {}, '前缀'), el('th', {}, '名称'), el('th', {}, '角色'),
          el('th', {}, '今日用量'), el('th', {}, '状态'), el('th', {}, ''))),
        el('tbody', {}, ...(d.keys || []).map((k) => el('tr', {},
          el('td', { class: 'mono' }, k.key_prefix),
          el('td', {}, k.name),
          el('td', {}, el('span', { class: 'tag' }, k.role)),
          el('td', { class: 'mono' }, k.used_today + ' / ' + k.daily_limit),
          el('td', {}, k.enabled ? el('span', { class: 'tag ok' }, '启用') : el('span', { class: 'tag' }, '已吊销')),
          el('td', {}, k.enabled ? el('button', {
            class: 'btn sm danger',
            onclick: async () => {
              if (!confirm('确认吊销 ' + k.key_prefix + '？')) return;
              try { await api('/admin/keys/' + k.key_prefix, undefined, 'DELETE'); toast('已吊销', 'ok'); loadKeys(); }
              catch (e) { toast(e.message, 'err'); }
            },
          }, '吊销') : null),
        ))),
      ));
    } catch (e) {
      keysBox.innerHTML = '';
      keysBox.append(el('div', { class: 'empty' }, '需要管理员 Key：' + e.message));
    }
  };

  const create = async () => {
    if (!st.name.trim()) { toast('请填写名称', 'err'); return; }
    try {
      const d = await api('/admin/keys', { name: st.name, role: st.role });
      newKey.innerHTML = '';
      newKey.append(el('div', { class: 'card', style: 'border-color:var(--ok)' },
        el('h3', {}, '✅ 新 Key 已创建（只显示这一次）'),
        el('div', { class: 'mono', style: 'word-break:break-all;padding:10px;background:var(--bg-3);border-radius:6px;margin:8px 0;font-size:12.5px' }, d.key),
        el('div', { class: 'hint' }, '立即复制保存。关闭后无法再次查看。'),
      ));
      st.name = ''; render(); loadKeys();
    } catch (e) { toast(e.message, 'err'); }
  };

  const sync = async () => {
    const btn = $('#syncbtn');
    if (btn) { btn.disabled = true; btn.textContent = '同步中…'; }
    try {
      const d = await api('/admin/sync/yuque', {});
      toast(`同步完成：新增 ${d.created} 更新 ${d.updated} 失败 ${d.failed}`, 'ok');
      loadKeys();
    } catch (e) { toast(e.message, 'err'); }
    if (btn) { btn.disabled = false; btn.textContent = '同步语雀'; }
  };

  loadKeys();

  return el('div', {},
    el('div', { class: 'page-title' }, '管理'),
    el('div', { class: 'page-desc' }, 'Key 管理与知识同步。需要管理员权限。'),
    el('div', { class: 'card' },
      el('h3', {}, '🔑 API Key'),
      keysBox,
      el('div', { style: 'margin-top:16px;display:flex;gap:8px;flex-wrap:wrap' },
        el('input', {
          placeholder: '名称，如 local-agent', value: st.name,
          oninput: (e) => { st.name = e.target.value; },
          style: 'flex:1;min-width:160px;background:var(--bg-3);border:1px solid var(--border-2);color:var(--fg);padding:7px 11px;border-radius:7px;font-size:13px;outline:none',
        }),
        el('select', {
          onchange: (e) => { st.role = e.target.value; },
          style: 'background:var(--bg-3);border:1px solid var(--border-2);color:var(--fg);padding:7px 11px;border-radius:7px;font-size:13px;outline:none',
        },
          el('option', { value: 'writer' }, 'writer'),
          el('option', { value: 'reader' }, 'reader'),
          el('option', { value: 'admin' }, 'admin'),
        ),
        el('button', { class: 'btn primary', onclick: create }, '创建'),
      ),
      newKey,
    ),
    el('div', { class: 'card' },
      el('h3', {}, '🔄 语雀同步'),
      el('div', { class: 'page-desc' }, '增量拉取语雀知识库更新。首次全量约 1-3 分钟。'),
      el('button', { class: 'btn', id: 'syncbtn', onclick: sync }, '同步语雀'),
    ),
  );
}

/* ---------------- 渲染 ---------------- */
function render() {
  const app = $('#app');
  const main = el('main', { class: 'main' },
    renderTopbar(),
    el('div', { class: 'content' },
      S.view === 'search' ? viewSearch()
        : S.view === 'doc' ? viewDoc()
        : S.view === 'rules' ? viewRules()
        : S.view === 'contribute' ? viewContribute()
        : S.view === 'overview' ? viewOverview()
        : viewAdmin()
    ),
  );
  app.innerHTML = '';
  app.append(el('div', { class: 'app' }, renderSidebar(), main));
}

// 启动
render();
if (S.key) loadStats();

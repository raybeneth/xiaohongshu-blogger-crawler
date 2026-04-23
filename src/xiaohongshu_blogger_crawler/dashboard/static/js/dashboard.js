// ---- auth: intercept 401 and redirect to login ----
const _origFetch = window.fetch;
window.fetch = async function(...args) {
  const resp = await _origFetch(...args);
  if (resp.status === 401) {
    window.location.href = '/login';
    return resp;
  }
  return resp;
};

// ---- logout ----
async function doLogout() {
  if (!confirm('确认退出登录？')) return;
  try {
    await fetch('/api/logout', { method: 'POST' });
  } catch (_) {}
  window.location.href = '/login';
}

// ---- page switching ----
function switchPage(el) {
  document.querySelectorAll('.menu-item').forEach(m => m.classList.remove('active'));
  el.classList.add('active');

  const page = el.dataset.page;
  document.querySelectorAll('.page').forEach(p => (p.style.display = 'none'));
  const target = document.getElementById('page-' + page);
  if (target) target.style.display = '';

  if (page === 'subscription-list') loadSubscriptions();
  if (page === 'script-exec') loadScriptPage();
  if (page === 'sys-config') loadSysConfigs();
  if (page === 'clean-monitor') loadCleanTasks();
}

// ---- helpers ----
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

const STATUS_MAP = {
  1:  { label: '待注册',       cls: 'badge-wait' },
  2:  { label: '待初始化',     cls: 'badge-wait' },
  3:  { label: '初始化中',     cls: 'badge-init' },
  4:  { label: '订阅中',       cls: 'badge-running' },
  10: { label: '初始化异常终止', cls: 'badge-failed' },
  11: { label: '订阅终止',     cls: 'badge-stopped' },
  12: { label: '订阅到期',     cls: 'badge-expired' },
};

const XHS_REG_MAP = {
  0:   { label: '等待注册', cls: 'badge-wait' },
  1:   { label: '注册成功', cls: 'badge-running' },
  999: { label: '异常',     cls: 'badge-failed' },
};

function statusBadge(val, map) {
  const info = map[val] || { label: '未知(' + val + ')', cls: 'badge-stopped' };
  return `<span class="badge ${info.cls}">${info.label}</span>`;
}

function fmtTime(iso) {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('zh-CN');
}

function versionsLabel(v) {
  return v === 0 ? '年费版本' : '报告版本';
}

function stateLabel(v) {
  return v === 1 ? '<span class="badge badge-running">有效</span>' : '<span class="badge badge-stopped">无效</span>';
}

// ---- load data ----
async function loadSubscriptions() {
  const wrap = document.getElementById('table-wrap');
  wrap.innerHTML = '<div class="loading">加载中...</div>';
  try {
    const resp = await fetch('/api/subscriptions');
    const list = await resp.json();
    if (!list.length) {
      wrap.innerHTML = '<div class="empty">暂无订阅数据</div>';
      return;
    }
    let html = `<div class="table-scroll"><table class="task-table">
      <thead><tr>
        <th>合约标识</th>
        <th>品牌ID</th>
        <th>订阅状态</th>
        <th>合约开始</th>
        <th>合约结束</th>
        <th>数据起始</th>
        <th>数据结束</th>
        <th>小红书注册</th>
        <th class="col-sticky-right">操作</th>
      </tr></thead><tbody>`;

    list.forEach(s => {
      html += `<tr>
        <td>${esc(s.contract_code)}</td>
        <td>${s.brand_id}</td>
        <td>${statusBadge(s.status, STATUS_MAP)}</td>
        <td>${fmtTime(s.contract_start_time)}</td>
        <td>${fmtTime(s.contract_end_time)}</td>
        <td>${fmtTime(s.data_start_time)}</td>
        <td>${fmtTime(s.data_end_time)}</td>
        <td>${statusBadge(s.xhs_register_status, XHS_REG_MAP)}</td>
        <td class="col-sticky-right">${s.status === 1
          ? `<button class="btn btn-primary" onclick="advanceStatus(${s.id}, this)">注册合约</button>`
          : s.status === 2 ? (
            s.xhs_register_status === 0
            ? `<button class="btn btn-primary disabled">等待注册</button>`
            : `<button class="btn btn-primary" onclick="advanceStatus(${s.id}, this)">开启同步</button>`
          )
          : s.status === 3
          ? `<button class="btn btn-primary disabled">初始化中</button>`
          : ''
          }</td>
      </tr>`;
    });
    html += '</tbody></table></div>';
    wrap.innerHTML = html;
  } catch (e) {
    wrap.innerHTML = '<div class="msg msg-err">加载失败：' + esc(String(e)) + '</div>';
  }
}

// ---- advance status ----
async function advanceStatus(id, btn) {
  if (!confirm('确认将该订阅推进到下一步？')) return;
  btn.disabled = true;
  btn.textContent = '处理中...';
  try {
    const resp = await fetch(`/api/subscriptions/${id}/advance`, { method: 'POST' });
    const result = await resp.json();
    if (!result.ok) {
      alert(result.msg || '操作失败');
      return;
    }
    await loadSubscriptions();
  } catch (e) {
    alert('请求失败：' + e);
  } finally {
    btn.disabled = false;
    btn.textContent = '下一步';
  }
}

// ---- contract modal ----
function openContractModal() {
  document.getElementById('contract-form').reset();
  document.getElementById('contract-modal').style.display = 'flex';
}

function closeContractModal() {
  document.getElementById('contract-modal').style.display = 'none';
}

async function submitContract() {
  const form = document.getElementById('contract-form');
  if (!form.reportValidity()) return;

  const fd = new FormData(form);
  const data = {};
  for (const [k, v] of fd.entries()) {
    data[k] = v;
  }

  const btn = document.getElementById('btn-submit-contract');
  btn.disabled = true;
  btn.textContent = '提交中...';
  try {
    const resp = await fetch('/api/contracts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const result = await resp.json();
    if (!result.ok) {
      alert('提交失败：' + (result.msg || '未知错误'));
      return;
    }
    closeContractModal();
    await loadSubscriptions();
  } catch (e) {
    alert('请求失败：' + e);
  } finally {
    btn.disabled = false;
    btn.textContent = '提交';
  }
}

// ---- script execution page ----
let _scriptPageInited = false;
let _brandList = [];

async function loadScriptPage() {
  const sel = document.getElementById('script-brand-select');
  try {
    const resp = await fetch('/api/subscriptions');
    _brandList = await resp.json();
    sel.innerHTML = '<option value="">-- 请选择品牌 --</option>';
    _brandList.forEach(s => {
      const name = s.brand_name || s.contract_code || '未知';
      sel.innerHTML += `<option value="${s.brand_id}">${esc(name)} (${s.brand_id})</option>`;
    });
  } catch (e) {
    sel.innerHTML = '<option value="">加载失败</option>';
  }

  if (!_scriptPageInited) {
    _scriptPageInited = true;
    document.getElementById('script-sql').addEventListener('input', onSqlInput);
    renderTplButtons();
  }
}

// ---- script templates ----
const SCRIPT_TEMPLATES = [
  {
    name: '查询表结构',
    sql: 'SHOW CREATE TABLE #{tableName};',
  },
  {
    name: '查询前100行',
    sql: 'SELECT * FROM #{tableName} LIMIT 100;',
  },
  {
    name: '统计表行数',
    sql: 'SELECT COUNT(*) AS total FROM #{tableName};',
  },
  {
    name: '统计表字段行数（去重）',
    sql: 'SELECT COUNT(DISTINCT #{columnName}) AS total FROM #{tableName};',
  },
  {
    name: '按日期查询',
    sql: "SELECT * FROM #{tableName}\nWHERE #{dateColumn} >= '#{startDate}'\n  AND #{dateColumn} < '#{endDate}'\nLIMIT 200;",
  },
  {
    name: '分组聚合统计',
    sql: "SELECT #{groupColumn}, COUNT(*) AS cnt\nFROM #{tableName}\nGROUP BY #{groupColumn}\nORDER BY cnt DESC\nLIMIT 50;",
  }
];

function renderTplButtons() {
  const wrap = document.getElementById('tpl-btns');
  wrap.innerHTML = SCRIPT_TEMPLATES.map((t, i) =>
    `<button class="btn btn-tpl" onclick="applyTemplate(${i})">${esc(t.name)}</button>`
  ).join('');
}

function applyTemplate(index) {
  const tpl = SCRIPT_TEMPLATES[index];
  if (!tpl) return;
  const textarea = document.getElementById('script-sql');
  textarea.value = tpl.sql;
  textarea.dispatchEvent(new Event('input'));
}

function onSqlInput() {
  const sql = document.getElementById('script-sql').value;
  const matches = [...new Set((sql.match(/#\{(\w+)\}/g) || []).map(m => m.slice(2, -1)))];
  const section = document.getElementById('placeholder-section');
  const list = document.getElementById('placeholder-list');

  if (!matches.length) {
    section.style.display = 'none';
    list.innerHTML = '';
    return;
  }

  section.style.display = '';
  // preserve existing values
  const existing = {};
  list.querySelectorAll('input[data-ph]').forEach(inp => {
    existing[inp.dataset.ph] = inp.value;
  });

  list.innerHTML = matches.map(name => `
    <div class="form-group">
      <label><code>#{${esc(name)}}</code></label>
      <input data-ph="${esc(name)}" value="${esc(existing[name] || '')}">
    </div>
  `).join('');
}

async function submitScript() {
  const brandId = document.getElementById('script-brand-select').value;
  if (!brandId) { alert('请先选择品牌'); return; }

  let sql = document.getElementById('script-sql').value.trim();
  if (!sql) { alert('请输入 SQL 脚本'); return; }

  // collect placeholder values
  const inputs = document.querySelectorAll('#placeholder-list input[data-ph]');
  const replacements = {};
  let missing = [];
  inputs.forEach(inp => {
    if (!inp.value.trim()) {
      missing.push(inp.dataset.ph);
    }
    replacements[inp.dataset.ph] = inp.value.trim();
  });

  if (missing.length) {
    alert('以下占位符尚未填写：\n' + missing.map(n => '#{' + n + '}').join('\n'));
    return;
  }

  // replace placeholders in sql
  for (const [name, val] of Object.entries(replacements)) {
    sql = sql.replaceAll(`#{${name}}`, val);
  }

  // find brand doris info
  const brand = _brandList.find(b => String(b.brand_id) === String(brandId));
  if (!brand || !brand.doris_url) {
    alert('该品牌缺少 Doris 数据源配置，请先完善品牌信息');
    return;
  }

  await _doExecuteScript(brandId, sql, brand);
}

async function _doExecuteScript(brandId, sql, brand, privilegedPassword) {
  const btn = document.getElementById('btn-exec-script');
  btn.disabled = true;
  btn.textContent = '执行中...';
  const resultDiv = document.getElementById('script-result');
  resultDiv.innerHTML = '<div class="loading">执行中，请稍候...</div>';

  const payload = {
    brand_id: brandId,
    sql,
    doris_url: brand.doris_url,
    doris_account: brand.doris_account,
    doris_password: brand.doris_password,
  };
  if (privilegedPassword) {
    payload.privileged_password = privilegedPassword;
  }

  try {
    const resp = await fetch('/api/scripts/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await resp.json();
    if (!result.ok) {
      if (result.need_privilege) {
        // 弹出高权限密码输入框
        resultDiv.innerHTML = '';
        const pwd = prompt('检测到高危语句，请输入高权限密码：');
        if (pwd) {
          await _doExecuteScript(brandId, sql, brand, pwd);
        } else {
          resultDiv.innerHTML = '<div class="msg msg-err">已取消执行</div>';
        }
        return;
      }
      let html = `<div class="result-error"><div class="msg msg-err">${esc(result.msg)}</div>`;
      if (result.traceback) {
        html += `<pre class="traceback">${esc(result.traceback)}</pre>`;
      }
      html += '</div>';
      resultDiv.innerHTML = html;
    } else {
      resultDiv.innerHTML = renderScriptResults(result.results);
    }
  } catch (e) {
    resultDiv.innerHTML = `<div class="msg msg-err">请求失败：${esc(String(e))}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '提交执行';
  }
}

function renderScriptResults(results) {
  if (!results || !results.length) return '<div class="msg msg-ok">执行成功，无返回数据</div>';
  let html = '';
  results.forEach(r => {
    html += `<div class="result-block">`;
    html += `<div class="result-header">语句 #${r.index}  <code>${esc(r.sql)}</code></div>`;
    if (r.columns) {
      html += `<div class="result-meta">${r.row_count} 行</div>`;
      html += '<div class="table-scroll"><table class="task-table result-table"><thead><tr>';
      r.columns.forEach(c => { html += `<th>${esc(c)}</th>`; });
      html += '</tr></thead><tbody>';
      r.rows.forEach(row => {
        html += '<tr>';
        row.forEach(cell => { html += `<td>${esc(cell)}</td>`; });
        html += '</tr>';
      });
      html += '</tbody></table></div>';
    } else {
      html += `<div class="msg msg-ok">影响行数：${r.affected_rows}</div>`;
    }
    html += '</div>';
  });
  return html;
}

// ---- parquet parser ----
async function handleParquetFile(input) {
  const file = input.files[0];
  if (!file) return;

  const nameSpan = document.getElementById('parquet-file-name');
  const metaDiv = document.getElementById('parquet-meta');
  const resultDiv = document.getElementById('parquet-result');

  if (file.size > 30 * 1024 * 1024) {
    alert('文件大小超过 30MB 限制');
    input.value = '';
    return;
  }

  nameSpan.textContent = file.name + ' (' + (file.size / 1024 / 1024).toFixed(2) + ' MB)';
  metaDiv.innerHTML = '';
  resultDiv.innerHTML = '<div class="loading">解析中...</div>';

  const formData = new FormData();
  formData.append('file', file);

  try {
    const resp = await fetch('/api/parquet/parse', { method: 'POST', body: formData });
    const result = await resp.json();
    if (!result.ok) {
      let html = `<div class="msg msg-err">${esc(result.msg)}</div>`;
      if (result.traceback) html += `<pre class="traceback">${esc(result.traceback)}</pre>`;
      resultDiv.innerHTML = html;
      return;
    }

    metaDiv.innerHTML = `<span class="hint">共 ${result.total_rows} 行，${result.columns.length} 列` +
      (result.returned_rows < result.total_rows ? `，显示前 ${result.returned_rows} 行` : '') + '</span>';

    let html = '<div class="table-scroll"><table class="task-table"><thead><tr>';
    result.columns.forEach(c => { html += `<th>${esc(c)}</th>`; });
    html += '</tr></thead><tbody>';
    result.rows.forEach(row => {
      html += '<tr>';
      row.forEach(cell => { html += `<td>${esc(cell)}</td>`; });
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    resultDiv.innerHTML = html;
  } catch (e) {
    resultDiv.innerHTML = `<div class="msg msg-err">请求失败：${esc(String(e))}</div>`;
  }

  // reset input so same file can be re-selected
  input.value = '';
}

// ---- clean task monitor ----
const CLEAN_STATUS_MAP = {
  0: { label: '待执行',           cls: 'badge-wait' },
  1: { label: '执行中',           cls: 'badge-init' },
  2: { label: '成功',             cls: 'badge-running' },
  3: { label: '失败',             cls: 'badge-failed' },
  9: { label: '等待依赖服务执行', cls: 'badge-stopped' },
};

async function loadCleanTasks() {
  const wrap = document.getElementById('clean-task-table-wrap');
  wrap.innerHTML = '<div class="loading">加载中...</div>';
  try {
    const resp = await fetch('/api/clean_tasks');
    const list = await resp.json();
    if (!list.length) {
      wrap.innerHTML = '<div class="empty">暂无清洗任务数据</div>';
      return;
    }
    let html = `<div class="table-scroll"><table class="task-table">
      <thead><tr>
        <th>ID</th>
        <th>品牌名称</th>
        <th>品牌ID</th>
        <th>公司ID</th>
        <th>任务标识</th>
        <th>执行状态</th>
        <th>执行进度</th>
        <th>失败原因</th>
        <th>更新时间</th>
        <th class="col-sticky-right">操作</th>
      </tr></thead><tbody>`;

    list.forEach(t => {
      const statusInfo = CLEAN_STATUS_MAP[t.status] || { label: '未知(' + t.status + ')', cls: 'badge-stopped' };
      const failCause = t.fail_cause
        ? `<span class="fail-cause-cell" title="${esc(t.fail_cause)}">${esc(t.fail_cause.length > 60 ? t.fail_cause.substring(0, 60) + '...' : t.fail_cause)}</span>`
        : '-';
      html += `<tr>
        <td>${t.id}</td>
        <td>${esc(t.brand_name || '-')}</td>
        <td>${t.brand_id}</td>
        <td>${t.group_id}</td>
        <td><code>${esc(t.code)}</code></td>
        <td><span class="badge ${statusInfo.cls}">${statusInfo.label}</span></td>
        <td>${fmtTime(t.progress)}</td>
        <td>${failCause}</td>
        <td>${fmtTime(t.update_time)}</td>
        <td class="col-sticky-right">${t.status === 3
          ? `<button class="btn btn-primary" onclick="retryCleanTask(${t.id}, this)">重试</button>`
          : ''}</td>
      </tr>`;
    });
    html += '</tbody></table></div>';
    wrap.innerHTML = html;
  } catch (e) {
    wrap.innerHTML = '<div class="msg msg-err">加载失败：' + esc(String(e)) + '</div>';
  }
}

async function retryCleanTask(id, btn) {
  if (!confirm('确认将该任务重置为待执行？')) return;
  btn.disabled = true;
  btn.textContent = '处理中...';
  try {
    const resp = await fetch(`/api/clean_tasks/${id}/retry`, { method: 'POST' });
    const result = await resp.json();
    if (!result.ok) {
      alert(result.msg || '操作失败');
      return;
    }
    await loadCleanTasks();
  } catch (e) {
    alert('请求失败：' + e);
  } finally {
    btn.disabled = false;
    btn.textContent = '重试';
  }
}

// ---- sys config page ----
const CONFIG_TYPE_MAP = {
  0: '系统基础配置',
  1: '运维系统配置',
  2: '业务必须配置',
  3: '非必须配置',
};

async function loadSysConfigs() {
  const wrap = document.getElementById('sys-config-table-wrap');
  wrap.innerHTML = '<div class="loading">加载中...</div>';
  try {
    const resp = await fetch('/api/sys_configs');
    const list = await resp.json();
    if (!list.length) {
      wrap.innerHTML = '<div class="empty">暂无配置数据</div>';
      return;
    }
    let html = `<div class="table-scroll"><table class="task-table">
      <thead><tr>
        <th>ID</th>
        <th>编码</th>
        <th>配置值</th>
        <th>类型</th>
        <th>说明</th>
        <th>更新时间</th>
        <th class="col-sticky-right">操作</th>
      </tr></thead><tbody>`;

    list.forEach(c => {
      const valPreview = c.value && c.value.length > 80 ? c.value.substring(0, 80) + '...' : (c.value || '');
      html += `<tr>
        <td>${c.id}</td>
        <td><code>${esc(c.code)}</code></td>
        <td class="config-val-cell" title="${esc(c.value)}">${esc(valPreview)}</td>
        <td>${esc(CONFIG_TYPE_MAP[c.type] || c.type)}</td>
        <td>${esc(c.remark || '-')}</td>
        <td>${fmtTime(c.update_time)}</td>
        <td class="col-sticky-right">
          <button class="btn btn-primary" onclick='editSysConfig(${JSON.stringify(c).replace(/'/g,"&#39;")})'>编辑</button>
          <button class="btn btn-danger" onclick="deleteSysConfig(${c.id})">删除</button>
        </td>
      </tr>`;
    });
    html += '</tbody></table></div>';
    wrap.innerHTML = html;
  } catch (e) {
    wrap.innerHTML = '<div class="msg msg-err">加载失败：' + esc(String(e)) + '</div>';
  }
}

function openSysConfigModal(data) {
  const form = document.getElementById('sys-config-form');
  form.reset();
  form.elements['id'].value = '';

  if (data) {
    document.getElementById('sys-config-modal-title').textContent = '编辑配置';
    form.elements['id'].value = data.id;
    form.elements['code'].value = data.code;
    form.elements['value'].value = data.value;
    form.elements['type'].value = data.type;
    form.elements['remark'].value = data.remark || '';
  } else {
    document.getElementById('sys-config-modal-title').textContent = '新增配置';
  }
  document.getElementById('sys-config-modal').style.display = 'flex';
}

function closeSysConfigModal() {
  document.getElementById('sys-config-modal').style.display = 'none';
}

function editSysConfig(data) {
  openSysConfigModal(data);
}

async function deleteSysConfig(id) {
  if (!confirm('确认删除该配置项？')) return;
  try {
    const resp = await fetch(`/api/sys_configs/${id}`, { method: 'DELETE' });
    const result = await resp.json();
    if (!result.ok) {
      alert(result.msg || '删除失败');
      return;
    }
    await loadSysConfigs();
  } catch (e) {
    alert('请求失败：' + e);
  }
}

async function submitSysConfig() {
  const form = document.getElementById('sys-config-form');
  if (!form.reportValidity()) return;

  const fd = new FormData(form);
  const data = {};
  for (const [k, v] of fd.entries()) data[k] = v;

  const configId = data.id;
  delete data.id;
  const isEdit = !!configId;

  const btn = document.getElementById('btn-submit-sys-config');
  btn.disabled = true;
  btn.textContent = '保存中...';
  try {
    const url = isEdit ? `/api/sys_configs/${configId}` : '/api/sys_configs';
    const method = isEdit ? 'PUT' : 'POST';
    const resp = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const result = await resp.json();
    if (!result.ok) {
      alert('保存失败：' + (result.msg || '未知错误'));
      return;
    }
    closeSysConfigModal();
    await loadSysConfigs();
  } catch (e) {
    alert('请求失败：' + e);
  } finally {
    btn.disabled = false;
    btn.textContent = '保存';
  }
}

// ---- initial load ----
document.addEventListener('DOMContentLoaded', () => {
  loadSubscriptions();
});

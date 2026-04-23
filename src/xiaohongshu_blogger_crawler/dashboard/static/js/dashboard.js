// ---- page switching ----
function switchPage(el) {
  document.querySelectorAll('.menu-item').forEach(m => m.classList.remove('active'));
  el.classList.add('active');

  const page = el.dataset.page;
  document.querySelectorAll('.page').forEach(p => (p.style.display = 'none'));
  const target = document.getElementById('page-' + page);
  if (target) target.style.display = '';

  if (page === 'subscription-list') loadSubscriptions();
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
  1:  { label: '待激活',       cls: 'badge-wait' },
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
        <th>ID</th>
        <th>数据状态</th>
        <th>合约标识</th>
        <th>集团ID</th>
        <th>品牌ID</th>
        <th>顾问</th>
        <th>合约版本</th>
        <th>订阅状态</th>
        <th>合约开始</th>
        <th>合约结束</th>
        <th>数据起始</th>
        <th>数据结束</th>
        <th>抽样比例</th>
        <th>小红书注册</th>
        <th>创建时间</th>
        <th>更新时间</th>
      </tr></thead><tbody>`;

    list.forEach(s => {
      html += `<tr>
        <td>${s.id}</td>
        <td>${stateLabel(s.state)}</td>
        <td>${esc(s.contract_code)}</td>
        <td>${s.group_id}</td>
        <td>${s.brand_id}</td>
        <td>${esc(s.counselor || '-')}</td>
        <td>${versionsLabel(s.versions)}</td>
        <td>${statusBadge(s.status, STATUS_MAP)}</td>
        <td>${fmtTime(s.contract_start_time)}</td>
        <td>${fmtTime(s.contract_end_time)}</td>
        <td>${fmtTime(s.data_start_time)}</td>
        <td>${fmtTime(s.data_end_time)}</td>
        <td>${s.sampling_proportion}%</td>
        <td>${statusBadge(s.xhs_register_status, XHS_REG_MAP)}</td>
        <td>${fmtTime(s.create_time)}</td>
        <td>${fmtTime(s.update_time)}</td>
      </tr>`;
    });
    html += '</tbody></table></div>';
    wrap.innerHTML = html;
  } catch (e) {
    wrap.innerHTML = '<div class="msg msg-err">加载失败：' + esc(String(e)) + '</div>';
  }
}

// ---- initial load ----
document.addEventListener('DOMContentLoaded', () => {
  loadSubscriptions();
});

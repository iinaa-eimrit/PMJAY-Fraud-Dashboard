'use strict';

/* ── State ────────────────────────────────────────────────────────────────── */
const state = {
    currentStatus:      '',
    currentPenaltyType: '',
    currentSearch:      '',
    currentPage:        1,
    pageSize:           25,
    totalPages:         1,
    loading:            false,
    activePenaltyId:    null,
};

/* ── DOM shortcuts ────────────────────────────────────────────────────────── */
const $ = id => document.getElementById(id);
const tableBody   = $('pen-table-body');
const pageInfo    = $('pen-page-info');
const pageControls = $('pen-page-controls');

/* ── CSRF ─────────────────────────────────────────────────────────────────── */
function getCsrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
}

/* ── URL builder ──────────────────────────────────────────────────────────── */
function url(template, id) {
    return template.replace('{id}', id);
}

/* ── API helper ───────────────────────────────────────────────────────────── */
async function apiFetch(endpoint, options = {}) {
    const res = await fetch(endpoint, {
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        ...options,
    });
    const data = await res.json();
    return { ok: res.ok, status: res.status, data };
}

/* ── Summary cards ────────────────────────────────────────────────────────── */
async function loadSummary() {
    const { ok, data } = await apiFetch(window.PEN_CONFIG.urls.summary);
    if (!ok) return;
    $('stat-active').textContent        = data.active;
    $('stat-reminder-sent').textContent = data.reminder_sent;
    $('stat-non-compliant').textContent = data.non_compliant;
    $('stat-paid').textContent          = data.paid;
    $('stat-closed').textContent        = data.closed;
}

/* ── Load penalty cases table ─────────────────────────────────────────────── */
async function loadCases() {
    if (state.loading) return;
    state.loading = true;
    tableBody.innerHTML = `<tr class="pen-loading-row"><td colspan="8">
        <i class="fas fa-spinner fa-spin"></i> Loading…</td></tr>`;

    const params = new URLSearchParams({
        page:      state.currentPage,
        page_size: state.pageSize,
    });
    if (state.currentStatus)      params.set('status', state.currentStatus);
    if (state.currentPenaltyType) params.set('penalty_type', state.currentPenaltyType);
    if (state.currentSearch)      params.set('search', state.currentSearch);

    const { ok, data } = await apiFetch(`${window.PEN_CONFIG.urls.cases}?${params}`);
    state.loading = false;

    if (!ok) {
        tableBody.innerHTML = `<tr><td colspan="8" class="pen-empty">
            Failed to load penalties.</td></tr>`;
        return;
    }

    if (!data.penalties || data.penalties.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="8" class="pen-empty">
            No penalty cases found.</td></tr>`;
        renderPagination(data);
        return;
    }

    tableBody.innerHTML = data.penalties.map(renderRow).join('');
    renderPagination(data);
}

/* ── Row renderer ─────────────────────────────────────────────────────────── */
function renderRow(p) {
    const a = p.actions;

    const amountHtml = p.penalty_amount
        ? `<span class="pen-amount">₹ ${Number(p.penalty_amount).toLocaleString('en-IN')}</span>`
        : `<span class="pen-na">N/A</span>`;

    const suspHtml = p.suspension_label
        ? `<span class="pen-susp">${p.suspension_label}</span>`
        : `<span class="pen-na">—</span>`;

    const typeClass = p.penalty_type === 'PENALTY' ? 'pen-badge-penalty' : 'pen-badge-suspension';

    const statusClass = {
        ACTIVE:          'pen-status-active',
        REMINDER_SENT:   'pen-status-reminder',
        NON_COMPLIANT:   'pen-status-nc',
        PAID:            'pen-status-paid',
        CLOSED:          'pen-status-closed',
    }[p.status] || '';

    return `
        <tr data-penalty-id="${p.id}">
          <td>
            <div class="pen-hospital-name">${p.hospital_name}</div>
            <div class="pen-hospital-id">${p.hospital_id}</div>
          </td>
          <td>
            <div>${p.district_name || '—'}</div>
            <div class="pen-state">${p.state_name || '—'}</div>
          </td>
          <td><span class="pen-type-badge ${typeClass}">${p.penalty_type_display}</span></td>
          <td>${amountHtml}</td>
          <td>${suspHtml}</td>
          <td>
            <div>${p.imposed_at_fmt}</div>
            <div class="pen-imposed-by">by ${p.created_by}</div>
          </td>
          <td><span class="pen-status-badge ${statusClass}">${p.status_display}</span></td>
          <td>
            <div class="pen-action-group">
              <button class="pen-action-btn pen-btn-reminder"
                ${a.can_send_reminder ? '' : 'disabled'}
                data-action="reminder" data-id="${p.id}"
                title="Send non-compliance reminder">
                <i class="fas fa-bell"></i> Remind
              </button>
              <button class="pen-action-btn pen-btn-paid"
                ${a.can_mark_paid ? '' : 'disabled'}
                data-action="paid" data-id="${p.id}"
                title="Mark penalty as paid">
                <i class="fas fa-rupee-sign"></i> Mark Paid
              </button>
              <button class="pen-action-btn pen-btn-nc"
                ${a.can_mark_non_compliant ? '' : 'disabled'}
                data-action="nc" data-id="${p.id}"
                title="Mark as non-compliant">
                <i class="fas fa-times-circle"></i> Non-Compliant
              </button>
              <button class="pen-action-btn pen-btn-audit"
                data-action="audit" data-id="${p.id}"
                title="View audit trail">
                <i class="fas fa-history"></i>
              </button>
            </div>
          </td>
        </tr>`;
}

/* ── Pagination ───────────────────────────────────────────────────────────── */
function renderPagination(data) {
    const { page, total_pages, total, page_size } = data;
    state.currentPage = page;
    state.totalPages  = total_pages;

    const start = total === 0 ? 0 : (page - 1) * page_size + 1;
    const end   = Math.min(page * page_size, total);
    pageInfo.textContent = total === 0
        ? 'No results'
        : `Showing ${start}–${end} of ${total} cases`;

    const buttons = [];
    if (data.has_previous) {
        buttons.push(`<button class="pen-page-btn" data-page="${page - 1}">‹ Prev</button>`);
    }
    // Show a few page numbers
    for (let p = Math.max(1, page - 2); p <= Math.min(total_pages, page + 2); p++) {
        buttons.push(
            `<button class="pen-page-btn ${p === page ? 'active' : ''}" data-page="${p}">${p}</button>`
        );
    }
    if (data.has_next) {
        buttons.push(`<button class="pen-page-btn" data-page="${page + 1}">Next ›</button>`);
    }
    pageControls.innerHTML = buttons.join('');
}

/* ── Action delegation on table ───────────────────────────────────────────── */
tableBody.addEventListener('click', e => {
    const btn = e.target.closest('[data-action]');
    if (!btn || btn.disabled) return;
    const action = btn.dataset.action;
    const id     = Number(btn.dataset.id);
    const row    = btn.closest('tr');
    const name   = row?.querySelector('.pen-hospital-name')?.textContent || '';

    if (action === 'reminder')   handleReminder(id, name);
    if (action === 'paid')       openPaidModal(id, name);
    if (action === 'nc')         openNcModal(id, name);
    if (action === 'audit')      openAuditModal(id, name);
});

/* ── Reminder (direct action, no modal needed) ────────────────────────────── */
async function handleReminder(penaltyId, name) {
    const btn = document.querySelector(`[data-action="reminder"][data-id="${penaltyId}"]`);
    const origHtml = btn ? btn.innerHTML : '';
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>'; }

    const { ok, data } = await apiFetch(
        url(window.PEN_CONFIG.urls.reminder, penaltyId),
        { method: 'POST', body: JSON.stringify({}) }
    );

    if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
    if (!ok) { showToast(data.error || 'Failed to send reminder.', 'error'); return; }
    refreshRow(data.penalty);
    showToast(`Reminder sent to "${name}".`);
    await loadSummary();
}

/* ── Mark Paid modal ──────────────────────────────────────────────────────── */
function openPaidModal(penaltyId, name) {
    state.activePenaltyId = penaltyId;
    $('pen-paid-modal-desc').textContent =
        `Confirm that the penalty amount for "${name}" has been received.`;
    $('pen-paid-notes').value = '';
    openModal('pen-paid-modal', 'pen-paid-modal-backdrop');
}

$('pen-paid-confirm').addEventListener('click', async () => {
    if (!state.activePenaltyId) return;
    const confirmBtn = $('pen-paid-confirm');
    const origHtml = confirmBtn.innerHTML;
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Confirming…';

    const notes = $('pen-paid-notes').value.trim();
    const { ok, data } = await apiFetch(
        url(window.PEN_CONFIG.urls.markPaid, state.activePenaltyId),
        { method: 'POST', body: JSON.stringify({ notes }) }
    );
    
    confirmBtn.disabled = false;
    confirmBtn.innerHTML = origHtml;
    closeModal('pen-paid-modal', 'pen-paid-modal-backdrop');
    if (!ok) { showToast(data.error || 'Failed to mark as paid.', 'error'); return; }
    refreshRow(data.penalty);
    showToast('Penalty marked as paid successfully.');
    state.activePenaltyId = null;
    await loadSummary();
});

/* ── Non-Compliant modal ──────────────────────────────────────────────────── */
function openNcModal(penaltyId, name) {
    state.activePenaltyId = penaltyId;
    $('pen-nc-modal-desc').textContent =
        `Mark the penalty case for "${name}" as non-compliant.`;
    $('pen-nc-notes').value = '';
    openModal('pen-nc-modal', 'pen-nc-modal-backdrop');
}

$('pen-nc-confirm').addEventListener('click', async () => {
    if (!state.activePenaltyId) return;
    const confirmBtn = $('pen-nc-confirm');
    const origHtml = confirmBtn.innerHTML;
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Confirming…';

    const notes = $('pen-nc-notes').value.trim();
    const { ok, data } = await apiFetch(
        url(window.PEN_CONFIG.urls.nonCompliant, state.activePenaltyId),
        { method: 'POST', body: JSON.stringify({ notes }) }
    );
    
    confirmBtn.disabled = false;
    confirmBtn.innerHTML = origHtml;

    closeModal('pen-nc-modal', 'pen-nc-modal-backdrop');
    if (!ok) { showToast(data.error || 'Failed to mark as non-compliant.', 'error'); return; }
    refreshRow(data.penalty);
    showToast('Case marked as non-compliant.', 'info');
    state.activePenaltyId = null;
    await loadSummary();
});

/* ── Audit modal ──────────────────────────────────────────────────────────── */
async function openAuditModal(penaltyId, name) {
    $('pen-audit-modal-subtitle').textContent = name;
    $('pen-audit-modal-body').innerHTML =
        '<p><i class="fas fa-spinner fa-spin"></i> Loading…</p>';
    openModal('pen-audit-modal', 'pen-audit-modal-backdrop');

    const { ok, data } = await apiFetch(
        url(window.PEN_CONFIG.urls.auditLog, penaltyId)
    );
    if (!ok) {
        $('pen-audit-modal-body').innerHTML = '<p>Failed to load audit log.</p>';
        return;
    }

    const iconMap = {
        IMPOSED:              'fa-gavel',
        REMINDER_SENT:        'fa-bell',
        MARKED_PAID:          'fa-check-circle',
        MARKED_NON_COMPLIANT: 'fa-times-circle',
        CLOSED:               'fa-archive',
        EMAIL_FAILED:         'fa-envelope-open',
    };

    const rows = data.logs.map(log => `
        <div class="sc-audit-entry">
          <div class="sc-audit-icon"><i class="fas ${iconMap[log.action] || 'fa-dot-circle'}"></i></div>
          <div class="sc-audit-content">
            <div class="sc-audit-action">${log.action_display}</div>
            <div class="sc-audit-meta">${log.performed_by} · ${log.performed_at_fmt}</div>
            ${log.notes ? `<div class="sc-audit-notes">${log.notes}</div>` : ''}
          </div>
        </div>`).join('');

    $('pen-audit-modal-body').innerHTML = rows || '<p>No audit entries yet.</p>';
}

/* ── Refresh a single row after an action ─────────────────────────────────── */
function refreshRow(penalty) {
    const existing = document.querySelector(`tr[data-penalty-id="${penalty.id}"]`);
    if (existing) existing.outerHTML = renderRow(penalty);
}

/* ── Toast notification ───────────────────────────────────────────────────── */
function showToast(message, type = 'success') {
    const existing = document.getElementById('pen-toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.id = 'pen-toast';
    toast.className = `pen-toast pen-toast-${type}`;
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    const icons = { success: 'fa-check-circle', error: 'fa-times-circle', info: 'fa-info-circle' };
    toast.innerHTML = `<i class="fas ${icons[type] || 'fa-check-circle'}" aria-hidden="true"></i> ${message}`;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('pen-toast-visible'));
    setTimeout(() => {
        toast.classList.remove('pen-toast-visible');
        toast.addEventListener('transitionend', () => toast.remove(), { once: true });
    }, 3800);
}

/* ── Generic modal open/close ─────────────────────────────────────────────── */
function openModal(modalId, backdropId) {
    $(backdropId).classList.add('open');
    $(modalId).classList.add('open');
}
function closeModal(modalId, backdropId) {
    $(backdropId).classList.remove('open');
    $(modalId).classList.remove('open');
}

// Close button wiring
document.querySelectorAll('[data-close]').forEach(btn => {
    btn.addEventListener('click', () => {
        const target = btn.dataset.close;
        const parts  = target.split('-modal');
        closeModal(target, `${parts[0]}-modal-backdrop`);
    });
});

// Backdrop click closes
['pen-audit-modal-backdrop', 'pen-paid-modal-backdrop', 'pen-nc-modal-backdrop'].forEach(id => {
    $(id).addEventListener('click', () => {
        closeModal(id.replace('-backdrop', ''), id);
    });
});

/* ── Filter tabs ──────────────────────────────────────────────────────────── */
document.querySelectorAll('.pen-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.pen-tab').forEach(t => {
            t.classList.remove('active');
            t.setAttribute('aria-selected', 'false');
        });
        tab.classList.add('active');
        tab.setAttribute('aria-selected', 'true');
        state.currentStatus = tab.dataset.status;
        state.currentPage   = 1;
        loadCases();
    });
});

/* ── Stat card filter shortcuts ───────────────────────────────────────────── */
document.querySelectorAll('.pen-stat-card.clickable').forEach(card => {
    card.addEventListener('click', () => {
        const filterStatus = card.dataset.filterStatus;
        document.querySelectorAll('.pen-tab').forEach(t => {
            const isActive = t.dataset.status === filterStatus;
            t.classList.toggle('active', isActive);
            t.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });
        state.currentStatus = filterStatus;
        state.currentPage   = 1;
        loadCases();
    });
});

/* ── Type filter ──────────────────────────────────────────────────────────── */
$('pen-type-filter').addEventListener('change', function () {
    state.currentPenaltyType = this.value;
    state.currentPage        = 1;
    loadCases();
});

/* ── Search ───────────────────────────────────────────────────────────────── */
let _searchTimer;
$('pen-search-input').addEventListener('input', function () {
    clearTimeout(_searchTimer);
    _searchTimer = setTimeout(() => {
        state.currentSearch = this.value.trim();
        state.currentPage   = 1;
        loadCases();
    }, 350);
});

/* ── Pagination click delegation ──────────────────────────────────────────── */
$('pen-page-controls').addEventListener('click', e => {
    const btn = e.target.closest('[data-page]');
    if (!btn) return;
    state.currentPage = Number(btn.dataset.page);
    loadCases();
});

/* ── Excel export ─────────────────────────────────────────────────────────── */
$('pen-export-btn').addEventListener('click', () => {
    const params = new URLSearchParams();
    if (state.currentStatus)      params.set('status', state.currentStatus);
    if (state.currentPenaltyType) params.set('penalty_type', state.currentPenaltyType);
    if (state.currentSearch)      params.set('search', state.currentSearch);
    window.location.href = `${window.PEN_CONFIG.urls.export}?${params}`;
});

/* ── Initial load ─────────────────────────────────────────────────────────── */
loadSummary();
loadCases();
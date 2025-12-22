'use strict';

/* ── State ────────────────────────────────────────────────────────────────── */
const state = {
    currentStatus: '',
    currentSearch: '',
    currentPage:   1,
    pageSize:      25,
    totalPages:    1,
    loading:       false,
    activeNoticeId: null,  // for the close modal
};

/* ── DOM shortcuts ────────────────────────────────────────────────────────── */
const $ = id => document.getElementById(id);
const tableBody     = $('sc-table-body');
const pageInfo      = $('sc-page-info');
const pageControls  = $('sc-page-controls');

/* ── CSRF helper ──────────────────────────────────────────────────────────── */
function getCsrf() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
}

/* ── URL builder ──────────────────────────────────────────────────────────── */
function url(template, id) {
    return template.replace('{id}', id);
}

/* ── API helpers ──────────────────────────────────────────────────────────── */
async function apiFetch(endpoint, options = {}) {
    const res = await fetch(endpoint, {
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrf(),
        },
        ...options,
    });
    const data = await res.json();
    return { ok: res.ok, status: res.status, data };
}

/* ── Summary cards ────────────────────────────────────────────────────────── */
async function loadSummary() {
    const { ok, data } = await apiFetch(window.SC_CONFIG.urls.summary);
    if (!ok) return;

    $('stat-issued-today').textContent  = data.issued_today;
    $('stat-r1-pending').textContent    = data.reminder_1_pending;
    $('stat-r2-pending').textContent    = data.reminder_2_pending;
    $('stat-overdue').textContent       = data.overdue;
    $('stat-expired').textContent       = data.expired;
    $('stat-closed').textContent        = data.closed;

    // Phase 3: drive attention indicators every time counts refresh
    updateAttentionIndicators(data);
}

/* ── Phase 3: Attention indicators ───────────────────────────────────────────
   Called after every loadSummary(). Shows:
     • A dismissible red banner above the filter bar when expired/overdue notices exist
     • A red dot on the "Expired" filter tab (cleared when the tab is clicked)
     • A pulsing ring on the Expired stat card
   ─────────────────────────────────────────────────────────────────────────── */

// Tracks whether the officer dismissed the banner this session.
// Resets to false when the count drops to zero (all resolved).
let _bannerDismissed = false;

function updateAttentionIndicators(data) {
    const expiredCount = data.expired  || 0;
    const overdueCount = data.overdue  || 0;
    const needsAction  = expiredCount + overdueCount;

    // ── Red banner above the filter bar ──────────────────────────────────
    let banner = $('sc-attention-banner');
    if (!banner) {
        banner = document.createElement('div');
        banner.id        = 'sc-attention-banner';
        banner.className = 'sc-attention-banner';
        banner.setAttribute('role', 'alert');
        const filterBar = document.querySelector('.sc-filter-bar');
        if (filterBar) filterBar.parentNode.insertBefore(banner, filterBar);
    }

    if (needsAction > 0 && !_bannerDismissed) {
        const parts = [];
        if (expiredCount > 0) parts.push(`${expiredCount} expired`);
        if (overdueCount > 0) parts.push(`${overdueCount} overdue (Reminder 2 sent, no response)`);

        banner.style.display = 'flex';
        banner.innerHTML = `
            <i class="fas fa-exclamation-triangle" aria-hidden="true"></i>
            <span class="sc-banner-text">
                <strong>${needsAction} notice${needsAction > 1 ? 's' : ''} need${needsAction === 1 ? 's' : ''} attention</strong>
                — ${parts.join(' and ')}.
                <span class="sc-banner-link">View expired →</span>
            </span>
            <button class="sc-banner-dismiss" aria-label="Dismiss" title="Dismiss">✕</button>`;

        // Clicking the text area navigates to Expired tab and clears red dot
        banner.querySelector('.sc-banner-text').addEventListener('click', () => {
            document.querySelectorAll('.sc-tab').forEach(t => {
                const active = t.dataset.status === 'EXPIRED';
                t.classList.toggle('active', active);
                t.setAttribute('aria-selected', active ? 'true' : 'false');
                if (active) t.classList.remove('has-items'); // clear dot on navigation
            });
            state.currentStatus = 'EXPIRED';
            state.currentPage   = 1;
            loadNotices();
        });

        // ✕ dismiss button — hides banner without navigating
        banner.querySelector('.sc-banner-dismiss').addEventListener('click', (e) => {
            e.stopPropagation();
            _bannerDismissed = true;
            banner.style.display = 'none';
        });

    } else if (needsAction === 0) {
        // All resolved — reset so banner can reappear if new notices expire
        _bannerDismissed = false;
        banner.style.display = 'none';
    } else {
        // Counts exist but banner was dismissed — keep it hidden
        banner.style.display = 'none';
    }

    // ── Red dot on Expired filter tab ─────────────────────────────────────
    // Only ADD the dot here; REMOVAL is handled by the tab click handler
    // (see filter tabs section below) so clicking the tab clears it.
    const expiredTab = document.querySelector('.sc-tab[data-status="EXPIRED"]');
    if (expiredTab) {
        if (expiredCount > 0 && !expiredTab.classList.contains('active')) {
            expiredTab.classList.add('has-items');
        } else if (expiredCount === 0) {
            expiredTab.classList.remove('has-items');
        }
    }

    // ── Pulsing ring on Expired stat card ─────────────────────────────────
    const expiredCard = document.querySelector('.sc-stat-card[data-filter-status="EXPIRED"]');
    if (expiredCard) expiredCard.classList.toggle('has-expired', expiredCount > 0);
}

/* ── Table loading ────────────────────────────────────────────────────────── */
async function loadNotices() {
    if (state.loading) return;
    state.loading = true;

    tableBody.innerHTML = `
        <tr class="sc-loading-row">
            <td colspan="9">
                <i class="fas fa-spinner fa-spin"></i> Loading notices…
            </td>
        </tr>`;

    const params = new URLSearchParams({
        page:      state.currentPage,
        page_size: state.pageSize,
    });
    if (state.currentStatus) params.set('status', state.currentStatus);
    if (state.currentSearch)  params.set('search', state.currentSearch);

    const { ok, data } = await apiFetch(`${window.SC_CONFIG.urls.notices}?${params}`);
    state.loading = false;

    if (!ok) {
        tableBody.innerHTML = `<tr class="sc-empty-row"><td colspan="9">Failed to load notices.</td></tr>`;
        return;
    }

    state.totalPages = data.total_pages;
    renderTable(data.notices, data.total, data.page, data.total_pages);
    renderPagination(data);
}

/* ── Table rendering ──────────────────────────────────────────────────────── */
function renderTable(notices, total, page, totalPages) {
    if (!notices.length) {
        tableBody.innerHTML = `
            <tr class="sc-empty-row">
                <td colspan="9">
                    <i class="fas fa-inbox"></i> No notices found.
                </td>
            </tr>`;
        return;
    }
    tableBody.innerHTML = notices.map(renderRow).join('');
}

/* ── Phase 3: Status badge with "Needs Attention" for expired rows ───────────
   Separated from renderRow so it can be read and tested independently.
   ─────────────────────────────────────────────────────────────────────────── */
function renderStatusBadge(n) {
    const badge = `<span class="sc-badge sc-badge-${n.status}">${escapeHtml(n.status_display)}</span>`;
    if (n.status === 'EXPIRED') {
        return badge + `
            <span class="sc-needs-attention"
                  title="Expired — no hospital response received">
                <i class="fas fa-exclamation" aria-hidden="true"></i> Needs Attention
            </span>`;
    }
    return badge;
}

function renderRow(n) {
    const actions = n.actions;

    // ── Deadline cell ─────────────────────────────────────────────────────
    let deadlineHtml = '<span class="sc-deadline sc-deadline-na">—</span>';

    if (n.status === 'ISSUED' && actions.days_until_reminder_1 !== null) {
        const d = actions.days_until_reminder_1;
        if (d > 2) {
            deadlineHtml = `<span class="sc-deadline sc-deadline-future">Rem. 1 in ${d}d</span>`;
        } else if (d >= 0) {
            deadlineHtml = `<span class="sc-deadline sc-deadline-soon">Rem. 1 in ${d}d ⚠</span>`;
        } else {
            deadlineHtml = `<span class="sc-deadline sc-deadline-overdue">Rem. 1 overdue ${Math.abs(d)}d !</span>`;
        }
    } else if (n.status === 'REMINDER_1_SENT' && actions.days_until_reminder_2 !== null) {
        const d = actions.days_until_reminder_2;
        if (d > 2) {
            deadlineHtml = `<span class="sc-deadline sc-deadline-future">Rem. 2 in ${d}d</span>`;
        } else if (d >= 0) {
            deadlineHtml = `<span class="sc-deadline sc-deadline-soon">Rem. 2 in ${d}d ⚠</span>`;
        } else {
            deadlineHtml = `<span class="sc-deadline sc-deadline-overdue">Rem. 2 overdue ${Math.abs(d)}d !</span>`;
        }
    } else if (n.status === 'REMINDER_2_SENT' && actions.days_until_expiry !== null) {
        const d = actions.days_until_expiry;
        if (d > 0) {
            deadlineHtml = `<span class="sc-deadline sc-deadline-future">Expires in ${d}d</span>`;
        } else {
            deadlineHtml = `<span class="sc-deadline sc-deadline-overdue">Expiry overdue ${Math.abs(d)}d !</span>`;
        }
    } else if (n.status === 'CLOSED' || n.status === 'EXPIRED') {
        deadlineHtml = `<span class="sc-deadline sc-deadline-done">${n.status === 'CLOSED' ? 'Closed' : 'Expired'}</span>`;
    }

    // ── Reminder cells ────────────────────────────────────────────────────
    const r1Cell = n.reminder_1_at_fmt
        ? `<span title="${n.reminder_1_at}">${n.reminder_1_at_fmt}</span>`
        : `<span class="sc-deadline sc-deadline-na">—</span>`;

    const r2Cell = n.reminder_2_at_fmt
        ? `<span title="${n.reminder_2_at}">${n.reminder_2_at_fmt}</span>`
        : `<span class="sc-deadline sc-deadline-na">—</span>`;

    // ── Action buttons ────────────────────────────────────────────────────
    const devTip = window.SC_CONFIG.bypass_timing ? ' (timing bypassed)' : '';

    const r1Btn = `<button
        class="sc-action-btn sc-btn-r1"
        data-action="reminder-1"
        data-id="${n.id}"
        ${actions.can_send_reminder_1 ? '' : 'disabled'}
        title="Send Reminder 1${devTip}">
        Rem. 1
    </button>`;

    const r2Btn = `<button
        class="sc-action-btn sc-btn-r2"
        data-action="reminder-2"
        data-id="${n.id}"
        ${actions.can_send_reminder_2 ? '' : 'disabled'}
        title="Send Reminder 2${devTip}">
        Rem. 2
    </button>`;

    const expireBtn = `<button
        class="sc-action-btn sc-btn-expire"
        data-action="expire"
        data-id="${n.id}"
        ${actions.can_mark_expired ? '' : 'disabled'}
        title="Mark as Expired${devTip}">
        Expire
    </button>`;

    const closeBtn = `<button
        class="sc-action-btn sc-btn-close-notice"
        data-action="close"
        data-id="${n.id}"
        data-name="${escapeHtml(n.hospital_name)}"
        ${actions.can_close ? '' : 'disabled'}
        title="Close notice">
        Close
    </button>`;

    const historyBtn = `<button
        class="sc-action-btn sc-btn-history"
        data-action="history"
        data-id="${n.id}"
        data-name="${escapeHtml(n.hospital_name)}"
        data-hospital-id="${escapeHtml(n.hospital_id)}"
        title="View audit trail">
        <i class="fas fa-history"></i>
    </button>`;

    return `
    <tr data-notice-id="${n.id}"${n.status === 'EXPIRED' ? ' class="sc-row-expired"' : ''}>
        <td>
            <div class="sc-hospital-name">${escapeHtml(n.hospital_name)}</div>
            <div class="sc-hospital-id">${escapeHtml(n.hospital_id)}</div>
        </td>
        <td>${escapeHtml(n.district_name || '—')}</td>
        <td>${n.analytics_start_date}<br><small style="color:#aaa">to ${n.analytics_end_date}</small></td>
        <td><span title="${n.issued_at}">${n.issued_at_fmt}</span></td>
        <td>${renderStatusBadge(n)}</td>
        <td>${r1Cell}</td>
        <td>${r2Cell}</td>
        <td>${deadlineHtml}</td>
        <td>
            <div class="sc-action-group">
                ${r1Btn}${r2Btn}${expireBtn}${closeBtn}${historyBtn}
            </div>
        </td>
    </tr>`;
}

/* ── Pagination rendering ─────────────────────────────────────────────────── */
function renderPagination(data) {
    const start = ((data.page - 1) * data.page_size) + 1;
    const end   = Math.min(start + data.page_size - 1, data.total);
    pageInfo.textContent = `Showing ${start}–${end} of ${data.total} notices`;

    pageControls.innerHTML = '';

    const mkBtn = (label, page, disabled, active) => {
        const btn = document.createElement('button');
        btn.className = `sc-page-btn${active ? ' active' : ''}`;
        btn.disabled  = disabled;
        btn.innerHTML = label;
        btn.addEventListener('click', () => {
            state.currentPage = page;
            loadNotices();
        });
        return btn;
    };

    pageControls.appendChild(mkBtn('« Prev', data.page - 1, !data.has_previous, false));

    // Show a window of pages
    const maxPages = 5;
    let from = Math.max(1, data.page - Math.floor(maxPages / 2));
    let to   = Math.min(data.total_pages, from + maxPages - 1);
    if (to - from < maxPages - 1) from = Math.max(1, to - maxPages + 1);

    for (let p = from; p <= to; p++) {
        pageControls.appendChild(mkBtn(p, p, false, p === data.page));
    }

    pageControls.appendChild(mkBtn('Next »', data.page + 1, !data.has_next, false));
}

/* ── Action dispatch ──────────────────────────────────────────────────────── */
tableBody.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-action]');
    if (!btn || btn.disabled) return;

    const action     = btn.dataset.action;
    const noticeId   = btn.dataset.id;
    const noticeName = btn.dataset.name || '';

    if (action === 'history') {
        openAuditModal(noticeId, noticeName, btn.dataset.hospitalId);
        return;
    }

    if (action === 'close') {
        openCloseModal(noticeId, noticeName);
        return;
    }

    // reminder-1, reminder-2, expire — direct action with spinner
    const actionLabels = {
        'reminder-1': 'Reminder 1 sent.',
        'reminder-2': 'Reminder 2 sent.',
        'expire':     'Notice marked as expired.',
    };

    const origHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    await performAction(action, noticeId, btn, origHtml, actionLabels[action]);
});

async function performAction(action, noticeId, btn = null, origHtml = '', successMsg = 'Action completed.') {
    const urlMap = {
        'reminder-1': window.SC_CONFIG.urls.reminder1,
        'reminder-2': window.SC_CONFIG.urls.reminder2,
        'expire':     window.SC_CONFIG.urls.expire,
        'close':      window.SC_CONFIG.urls.close,
    };

    const endpoint = url(urlMap[action], noticeId);
    const { ok, data } = await apiFetch(endpoint, { method: 'POST', body: '{}' });

    if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }

    if (!ok) {
        showToast(data.error || 'An error occurred.', 'error');
        return;
    }

    showToast(successMsg);

    // Refresh only this row
    const updatedRow = renderRow(data.notice);
    const existingRow = document.querySelector(`tr[data-notice-id="${noticeId}"]`);
    if (existingRow) {
        existingRow.outerHTML = updatedRow;
    }

    // Refresh summary counts (a status changed)
    await loadSummary();
}

/* ── Audit log modal ──────────────────────────────────────────────────────── */
function openAuditModal(noticeId, noticeName, hospitalId) {
    $('audit-modal-subtitle').textContent = `${hospitalId} — ${noticeName}`;
    $('audit-modal-body').innerHTML = `<p><i class="fas fa-spinner fa-spin"></i> Loading…</p>`;
    openModal('audit-modal', 'audit-modal-backdrop');

    apiFetch(url(window.SC_CONFIG.urls.auditLog, noticeId)).then(({ ok, data }) => {
        if (!ok || !data.logs) {
            $('audit-modal-body').innerHTML = '<p>Failed to load audit log.</p>';
            return;
        }
        if (!data.logs.length) {
            $('audit-modal-body').innerHTML = '<p>No audit entries found.</p>';
            return;
        }

        const iconMap = {
            'ISSUED':           'fa-paper-plane',
            'REMINDER_1_SENT':  'fa-bell',
            'REMINDER_2_SENT':  'fa-bell',
            'AUTO_EXPIRED':     'fa-clock',
            'EXPIRED':          'fa-times-circle',
            'CLOSED':           'fa-check-circle',
            'EMAIL_FAILED':     'fa-exclamation-triangle',
        };

        const items = data.logs.map(log => `
            <li class="sc-timeline-item">
                <div class="sc-timeline-dot action-${log.action}">
                    <i class="fas ${iconMap[log.action] || 'fa-circle'}"></i>
                </div>
                <div class="sc-timeline-content">
                    <div class="sc-timeline-action">${escapeHtml(log.action_display)}</div>
                    <div class="sc-timeline-meta">
                        by <strong>${escapeHtml(log.performed_by)}</strong>
                        on ${escapeHtml(log.performed_at_fmt)}
                    </div>
                    ${log.notes ? `<div class="sc-timeline-notes">${escapeHtml(log.notes)}</div>` : ''}
                </div>
            </li>`
        ).join('');

        $('audit-modal-body').innerHTML = `<ul class="sc-timeline">${items}</ul>`;
    });
}

/* ── Close notice modal ───────────────────────────────────────────────────── */
function openCloseModal(noticeId, noticeName) {
    state.activeNoticeId = noticeId;

    // Reset form to defaults every time the modal is opened
    $('close-modal-desc').textContent =
        `You are about to formally close the notice for "${noticeName}". `
        + `This action is irreversible.`;

    // Reset type selector to WARNING
    document.querySelectorAll('input[name="close_type"]').forEach(r => {
        r.checked = r.value === 'WARNING';
    });
    _onCloseTypeChange('WARNING');

    $('penalty-amount').value = '';
    $('penalty-custom-suspension').checked = false;
    $('penalty-suspension-until').value = '';
    $('penalty-suspension-date-wrap').hidden = true;
    $('suspension-until').value = '';
    $('close-notes').value = '';

    openModal('close-modal', 'close-modal-backdrop');
}

/* Show/hide the correct sub-panel based on selected close type */
function _onCloseTypeChange(type) {
    $('panel-penalty').hidden    = (type !== 'PENALTY');
    $('panel-suspension').hidden = (type !== 'SUSPENSION');

    // Update confirm button label
    const labels = {
        WARNING:    'Confirm — Close with Warning',
        PENALTY:    'Confirm — Close with Penalty',
        SUSPENSION: 'Confirm — Close with Suspension',
    };
    $('close-modal-confirm').innerHTML =
        `<i class="fas fa-check" aria-hidden="true"></i> ${labels[type] || 'Confirm Close'}`;
}

// Wire type radio buttons
document.querySelectorAll('input[name="close_type"]').forEach(radio => {
    radio.addEventListener('change', () => _onCloseTypeChange(radio.value));
});

// Wire penalty custom suspension checkbox
$('penalty-custom-suspension').addEventListener('change', function () {
    $('penalty-suspension-date-wrap').hidden = !this.checked;
    if (!this.checked) $('penalty-suspension-until').value = '';
});

$('close-modal-confirm').addEventListener('click', async () => {
    if (!state.activeNoticeId) return;

    const closeType = document.querySelector('input[name="close_type"]:checked')?.value || 'WARNING';
    const notes     = $('close-notes').value.trim();

    // ── Collect & validate type-specific inputs ───────────────────────────
    let penaltyAmount   = null;
    let suspensionUntil = null;

    if (closeType === 'PENALTY') {
        const rawAmount = $('penalty-amount').value.trim();
        if (!rawAmount || isNaN(rawAmount) || Number(rawAmount) <= 0) {
            showToast('Please enter a valid Penalty Amount (INR).', 'error');
            return;
        }
        penaltyAmount = rawAmount;

        if ($('penalty-custom-suspension').checked) {
            suspensionUntil = $('penalty-suspension-until').value || null;
            if (!suspensionUntil) {
                showToast('Please select a Suspension End Date, or uncheck the custom date option.', 'error');
                return;
            }
        }
    }

    if (closeType === 'SUSPENSION') {
        suspensionUntil = $('suspension-until').value || null;
        if (!suspensionUntil) {
            showToast('Please select a Suspension End Date.', 'error');
            return;
        }
    }
    const confirmBtn = $('close-modal-confirm');
    const origHtml = confirmBtn.innerHTML;
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Closing…';

    const payload = {
        close_type:       closeType,
        notes,
        penalty_amount:   penaltyAmount,
        suspension_until: suspensionUntil,
    };

    const { ok, data } = await apiFetch(
        url(window.SC_CONFIG.urls.close, state.activeNoticeId),
        { method: 'POST', body: JSON.stringify(payload) }
    );

    confirmBtn.disabled = false;
    confirmBtn.innerHTML = origHtml;

    closeModal('close-modal', 'close-modal-backdrop');

    if (!ok) {
        showToast(data.error || 'An error occurred while closing the notice.', 'error');
        return;
    }

    const toastMessages = {
        WARNING:    'Notice closed with Warning — confirmation email sent.',
        PENALTY:    'Notice closed with Penalty — order email sent.',
        SUSPENSION: 'Notice closed with Suspension — order email sent.',
    };
    showToast(toastMessages[closeType] || 'Notice closed successfully.');

    const updatedRow = renderRow(data.notice);
    const existingRow = document.querySelector(`tr[data-notice-id="${state.activeNoticeId}"]`);
    if (existingRow) existingRow.outerHTML = updatedRow;
    state.activeNoticeId = null;
    await loadSummary();
});


/* ── Toast notification ───────────────────────────────────────────────────── */
function showToast(message, type = 'success') {
    const existing = document.getElementById('sc-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'sc-toast';
    toast.className = `sc-toast sc-toast-${type}`;
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');

    const icon = type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle';
    toast.innerHTML = `<i class="fas ${icon}" aria-hidden="true"></i> ${message}`;
    document.body.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => toast.classList.add('sc-toast-visible'));

    // Auto-dismiss after 3.5 s
    setTimeout(() => {
        toast.classList.remove('sc-toast-visible');
        toast.addEventListener('transitionend', () => toast.remove(), { once: true });
    }, 3500);
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

// Close button handler (works for both modals)
document.querySelectorAll('[data-close]').forEach(btn => {
    btn.addEventListener('click', () => {
        const target = btn.dataset.close;
        // Derive backdrop id
        const backdropId = target.replace('-modal', '-modal-backdrop')
            .replace('audit-modal-backdrop', 'audit-modal-backdrop')
            .replace('close-modal-backdrop', 'close-modal-backdrop');
        const parts = target.split('-modal');
        closeModal(target, `${parts[0]}-modal-backdrop`);
    });
});

// Backdrop click closes
['audit-modal-backdrop', 'close-modal-backdrop'].forEach(id => {
    $(id).addEventListener('click', () => {
        const modalId = id.replace('-backdrop', '');
        closeModal(modalId, id);
    });
});

/* ── Filter tabs ──────────────────────────────────────────────────────────── */
document.querySelectorAll('.sc-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.sc-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        state.currentStatus = tab.dataset.status;
        state.currentPage   = 1;
        // Clear the red dot when the Expired tab is clicked
        if (tab.dataset.status === 'EXPIRED') {
            tab.classList.remove('has-items');
        }
        loadNotices();
    });
});

/* ── Summary card filter shortcut ────────────────────────────────────────── */
document.querySelectorAll('.sc-stat-card.clickable').forEach(card => {
    card.addEventListener('click', () => {
        const filterStatus = card.dataset.filterStatus;
        // Activate matching tab
        document.querySelectorAll('.sc-tab').forEach(t => {
            const match = t.dataset.status === filterStatus;
            t.classList.toggle('active', match);
        });
        document.querySelectorAll('.sc-stat-card').forEach(c => c.classList.remove('active-filter'));
        card.classList.add('active-filter');
        state.currentStatus = filterStatus;
        state.currentPage   = 1;
        loadNotices();
    });
});

/* ── Search — debounced ───────────────────────────────────────────────────── */
let searchTimer = null;
$('sc-search-input').addEventListener('input', (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
        state.currentSearch = e.target.value.trim();
        state.currentPage   = 1;
        loadNotices();
    }, 300);
});

/* ── HTML escape ─────────────────────────────────────────────────────────── */
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/* ── Init ────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    loadSummary();
    loadNotices();
});
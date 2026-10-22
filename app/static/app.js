const notice = (text, error = false) => {
  const box = document.querySelector('#notice');
  if (!box) return;
  box.textContent = text;
  box.hidden = false;
  box.classList.toggle('error', error);
  box.setAttribute('role', error ? 'alert' : 'status');
  box.scrollIntoView({ block: 'nearest' });
};

async function api(url, method = 'POST', body) {
  const csrfMeta = document.querySelector('meta[name=csrf-token]');
  const headers = csrfMeta ? { 'X-CSRF-Token': csrfMeta.content } : {};
  if (!(body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch(url, {
    method,
    headers,
    body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
  });
  const result = await response.json().catch(() => ({ detail: 'Invalid server response' }));
  if (!response.ok) {
    const errorMsg = result.error?.reason || result.detail || 'Request failed';
    const err = new Error(typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg));
    err.structured = result.error;
    throw err;
  }
  return result;
}

function action(form, handler) {
  if (!form) return;
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const buttons = form.querySelectorAll('button');
    buttons.forEach(b => (b.disabled = true));
    try {
      await handler(new FormData(form));
    } catch (error) {
      notice(error.message, true);
    } finally {
      buttons.forEach(b => (b.disabled = false));
    }
  });
}

// Multi-file batch and single upload handler
const uploadForm = document.querySelector('#upload-form');
if (uploadForm) {
  uploadForm.addEventListener('submit', async event => {
    event.preventDefault();
    const fileInput = document.querySelector('#file');
    const files = fileInput?.files ? Array.from(fileInput.files) : [];
    if (!files.length) {
      notice('Please choose at least one document to upload.', true);
      return;
    }

    const projectId = document.querySelector('#project')?.value;
    const autoRecord = document.querySelector('#auto_record')?.checked;
    const uploadBtn = document.querySelector('#upload-btn');
    if (uploadBtn) uploadBtn.disabled = true;

    const batchPanel = document.querySelector('#batch-panel');
    const batchItems = document.querySelector('#batch-items');
    const batchTitle = document.querySelector('#batch-title');
    const batchSubtitle = document.querySelector('#batch-subtitle');
    const batchProgress = document.querySelector('#batch-progress');
    const batchActions = document.querySelector('#batch-actions');

    if (batchPanel) {
      batchPanel.hidden = false;
      batchPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      batchItems.innerHTML = '';
      if (batchActions) batchActions.hidden = true;
      batchTitle.textContent = `Processing Batch (${files.length} document${files.length > 1 ? 's' : ''})`;
      batchSubtitle.textContent = 'Uploading and processing sequentially...';
      batchProgress.style.width = '0%';
    }

    // Render initial queued rows
    files.forEach((f, idx) => {
      const tr = document.createElement('tr');
      tr.id = `batch-row-${idx}`;
      tr.innerHTML = `
        <td><strong>${escapeHtml(f.name)}</strong><br><small class="muted">${(f.size / 1024).toFixed(1)} KB</small></td>
        <td id="batch-status-${idx}"><span class="badge-status badge-queued">Queued ⏳</span></td>
        <td id="batch-data-${idx}">—</td>
        <td id="batch-issues-${idx}" class="muted">Waiting in queue...</td>
        <td id="batch-action-${idx}">—</td>
      `;
      batchItems.appendChild(tr);
    });

    let recordedCount = 0;
    let reviewCount = 0;
    let failedCount = 0;
    let duplicateCount = 0;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const statusCell = document.querySelector(`#batch-status-${i}`);
      const dataCell = document.querySelector(`#batch-data-${i}`);
      const issuesCell = document.querySelector(`#batch-issues-${i}`);
      const actionCell = document.querySelector(`#batch-action-${i}`);

      if (statusCell) {
        statusCell.innerHTML = '<span class="badge-status badge-processing">Processing 🔄</span>';
      }

      const fd = new FormData();
      fd.append('file', file);
      fd.append('project_id', projectId);
      if (autoRecord) fd.append('auto_record', 'true');

      try {
        const res = await api('/api/v1/documents', 'POST', fd);
        const doc = res.document;
        const cand = doc.candidate || {};

        if (res.reused || res.duplicate) {
          duplicateCount++;
          if (statusCell) statusCell.innerHTML = '<span class="badge-status badge-duplicate">Duplicate</span>';
          if (dataCell) dataCell.textContent = cand.vendor ? `${cand.vendor} · ${cand.grand_total || ''} ${cand.currency || ''}` : 'Existing document';
          if (issuesCell) issuesCell.innerHTML = '<span class="muted">Identical document already submitted. No duplicate expense recorded.</span>';
          if (actionCell) actionCell.innerHTML = `<a href="/documents/${doc.id}">View ↗</a>`;
        } else if (res.auto_recorded || doc.state === 'RECORDED') {
          recordedCount++;
          if (statusCell) statusCell.innerHTML = '<span class="badge-status badge-recorded">Auto-Recorded ✅</span>';
          if (dataCell) dataCell.innerHTML = `<strong>${escapeHtml(cand.vendor || 'Vendor unknown')}</strong><br>${cand.grand_total || '0.00'} ${cand.currency || ''} · <small class="muted">${escapeHtml(cand.category_id || 'uncategorized')}</small>`;
          if (issuesCell) issuesCell.innerHTML = '<span class="success-text" style="color:#166534;">Verified valid. Automatically recorded to expenses & Sheets.</span>';
          if (actionCell) actionCell.innerHTML = `<a href="/documents/${doc.id}">View ↗</a>`;
        } else if (doc.state === 'NEEDS_REVIEW') {
          reviewCount++;
          if (statusCell) statusCell.innerHTML = '<span class="badge-status badge-review">Needs Review ⚠️</span>';
          if (dataCell) dataCell.innerHTML = `<strong>${escapeHtml(cand.vendor || '—')}</strong><br>${cand.grand_total || 'Total ?'} ${cand.currency || 'Currency ?'}`;
          const issueList = (res.issues || []).map(iss => iss.explanation || iss.code).join('; ') || 'Critical review condition triggered';
          if (issuesCell) issuesCell.innerHTML = `<span style="color:#92400e;">${escapeHtml(issueList)}</span>`;
          if (actionCell) actionCell.innerHTML = `<a href="/documents/${doc.id}" class="button" style="padding:4px 10px; font-size:12px;">Review ↗</a>`;
        } else if (doc.state === 'FAILED') {
          failedCount++;
          if (statusCell) statusCell.innerHTML = '<span class="badge-status badge-failed">Failed ❌</span>';
          const errReason = doc.human_error?.reason || doc.error_code || 'Document extraction failed';
          if (issuesCell) issuesCell.innerHTML = `<span style="color:#991b1b;">${escapeHtml(errReason)}</span>`;
          if (actionCell) actionCell.innerHTML = `<a href="/documents/${doc.id}">Details ↗</a>`;
        } else {
          if (statusCell) statusCell.innerHTML = `<span class="badge-status badge-queued">${escapeHtml(doc.state)}</span>`;
          if (actionCell) actionCell.innerHTML = `<a href="/documents/${doc.id}">View ↗</a>`;
        }
      } catch (err) {
        failedCount++;
        if (statusCell) statusCell.innerHTML = '<span class="badge-status badge-failed">Failed ❌</span>';
        if (issuesCell) issuesCell.innerHTML = `<span style="color:#991b1b;">${escapeHtml(err.message)}</span>`;
      }

      const percent = Math.round(((i + 1) / files.length) * 100);
      if (batchProgress) batchProgress.style.width = `${percent}%`;
    }

    if (uploadBtn) uploadBtn.disabled = false;
    if (batchTitle) batchTitle.textContent = `Batch Complete (${files.length} document${files.length > 1 ? 's' : ''})`;
    if (batchSubtitle) {
      batchSubtitle.innerHTML = `<strong>${recordedCount}</strong> Auto-Recorded · <strong>${reviewCount}</strong> Needs Review · <strong>${duplicateCount}</strong> Duplicate · <strong>${failedCount}</strong> Failed`;
    }
    if (batchActions) batchActions.hidden = false;

    notice(
      `Batch finished: ${recordedCount} recorded automatically, ${reviewCount} sent to review queue, ${failedCount} failed.`,
      failedCount > 0 && recordedCount === 0
    );
  });
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Review form handling
const review = document.querySelector('#review-form');
action(review, async data => {
  const candidate = JSON.parse(document.querySelector('#candidate-data').textContent);
  for (const key of ['vendor', 'date', 'document_number', 'grand_total', 'currency', 'subtotal', 'tax', 'discount', 'category_id']) {
    candidate[key] = data.get(key)?.trim() || null;
  }
  candidate.description = data.get('description');
  candidate.tax_mode = data.get('tax_mode');
  candidate.discount_explicit = data.has('discount_explicit');
  await api(`/api/v1/documents/${review.dataset.id}/fields`, 'PATCH', {
    version: Number(review.dataset.version),
    candidate,
  });
  location.reload();
});

document.querySelectorAll('[data-review-action]').forEach(button =>
  button.addEventListener('click', async () => {
    const holder = button.closest('[data-doc]');
    const type = button.dataset.reviewAction;
    button.disabled = true;
    try {
      notice(type === 'reextract' ? 'Starting a new extraction attempt…' : 'Saving your decision…');
      await api(
        `/api/v1/documents/${holder.dataset.doc}/${type}`,
        'POST',
        type === 'reextract'
          ? undefined
          : {
              version: Number(holder.dataset.version),
              justification: document.querySelector('#justification')?.value || '',
            }
      );
      location.reload();
    } catch (error) {
      notice(error.message, true);
    } finally {
      button.disabled = false;
    }
  })
);

// Delete Expense Handler
document.querySelectorAll('[data-delete-expense]').forEach(button => {
  button.addEventListener('click', async () => {
    const id = button.dataset.deleteExpense;
    if (!confirm('Are you sure you want to delete this expense record from the database?')) return;
    button.disabled = true;
    try {
      await api(`/api/v1/expenses/${id}`, 'DELETE');
      notice('Expense record deleted successfully.');
      const row = document.querySelector(`#expense-row-${id}`);
      if (row) row.remove();
      const countTag = document.querySelector('#expense-count-tag');
      if (countTag) {
        const rows = document.querySelectorAll('#expense-table-body tr');
        countTag.textContent = `${rows.length} records`;
      }
    } catch (err) {
      notice(err.message, true);
      button.disabled = false;
    }
  });
});

// Delete Document Handler
document.querySelectorAll('[data-delete-document]').forEach(button => {
  button.addEventListener('click', async () => {
    const id = button.dataset.deleteDocument;
    if (!confirm('Are you sure you want to permanently delete this document and all its records from the database?')) return;
    button.disabled = true;
    try {
      await api(`/api/v1/documents/${id}`, 'DELETE');
      notice('Document deleted successfully.');
      const row = document.querySelector(`#review-row-${id}`);
      if (row) {
        row.remove();
      } else {
        setTimeout(() => {
          location.href = '/review';
        }, 500);
      }
    } catch (err) {
      notice(err.message, true);
      button.disabled = false;
    }
  });
});

// Add New Category Handler
const newCategoryForm = document.querySelector('#new-category-form');
if (newCategoryForm) {
  newCategoryForm.addEventListener('submit', async event => {
    event.preventDefault();
    const btn = newCategoryForm.querySelector('button[type=submit]');
    if (btn) btn.disabled = true;
    const fd = new FormData(newCategoryForm);
    const name = fd.get('name')?.trim();
    const id = fd.get('id')?.trim() || undefined;
    const definition = fd.get('definition')?.trim();
    const active = fd.has('active');
    try {
      await api('/api/v1/categories', 'POST', { name, id, definition, active });
      notice('New category created successfully!');
      setTimeout(() => location.reload(), 600);
    } catch (err) {
      notice(err.message, true);
      if (btn) btn.disabled = false;
    }
  });
}

// Delete Category Handler
document.querySelectorAll('[data-delete-category]').forEach(button => {
  button.addEventListener('click', async () => {
    const id = button.dataset.deleteCategory;
    if (!confirm(`Are you sure you want to delete category "${id}"?`)) return;
    button.disabled = true;
    try {
      await api(`/api/v1/categories/${id}`, 'DELETE');
      notice(`Category "${id}" deleted.`);
      const card = document.querySelector(`#category-card-${id}`);
      if (card) card.remove();
    } catch (err) {
      notice(err.message, true);
      button.disabled = false;
    }
  });
});

// Existing Category Form Edit Handler
document.querySelectorAll('.category-form').forEach(form =>
  action(form, async data => {
    await api(`/api/v1/categories/${form.dataset.id}`, 'PATCH', {
      name: data.get('name'),
      definition: data.get('definition'),
      active: data.has('active'),
    });
    notice('Category saved. Its ID and historical records are preserved.');
  })
);

document.querySelector('#logout')?.addEventListener('click', async () => {
  await api('/logout');
  location.href = '/login';
});

// Chart initialization for Financial Analytics & Pipeline Tracing
function initFinanceCharts() {
  const chartScript = document.querySelector('#finance-chart-data');
  if (!chartScript || typeof Chart === 'undefined') return;

  try {
    const { summary, pipeline } = JSON.parse(chartScript.textContent);

    // 1. Spend Over Time Chart
    const timelineEl = document.querySelector('#chart-timeline');
    if (timelineEl && summary && summary.timeline) {
      const labels = summary.timeline.map(t => t.month);
      const values = summary.timeline.map(t => parseFloat(t.total) || 0);
      new Chart(timelineEl, {
        type: 'bar',
        data: {
          labels: labels.length ? labels : ['No Data'],
          datasets: [{
            label: 'Confirmed Spend',
            data: values.length ? values : [0],
            backgroundColor: '#1e6255',
            borderRadius: 6,
            hoverBackgroundColor: '#2d8474',
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => ` Spend: ${ctx.parsed.y.toFixed(2)}`,
              },
            },
          },
          scales: {
            y: {
              beginAtZero: true,
              grid: { color: '#e0e6df' },
              ticks: { color: '#677873' },
            },
            x: {
              grid: { display: false },
              ticks: { color: '#677873' },
            },
          },
        },
      });
    }

    // 2. Spend by Category Chart
    const catEl = document.querySelector('#chart-categories');
    if (catEl && summary && summary.categories) {
      const catLabels = summary.categories.map(c => c.category);
      const catValues = summary.categories.map(c => parseFloat(c.total) || 0);
      const colors = ['#1e6255', '#2563eb', '#0d9488', '#d97706', '#16a34a', '#8b5cf6', '#ec4899', '#64748b'];

new Chart(catEl, {
        type: 'doughnut',
        
        data: {
          labels: catLabels.length ? catLabels : ['Uncategorized'],
          datasets: [{
            data: catValues.length ? catValues : [0],
            backgroundColor: colors.slice(0, Math.max(1, catLabels.length)),
            borderWidth: 2,
            borderColor: '#ffffff',
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'right',
              labels: {
                boxWidth: 12,
                color: '#173c39',
                font: { size: 12 },
                generateLabels(chart) {
                  const data = chart.data;
                  if (data.labels.length && data.datasets.length) {
                    const total = data.datasets[0].data.reduce((a, b) => a + Number(b), 0);
                    return data.labels.map((label, i) => {
                      const val = Number(data.datasets[0].data[i]) || 0;
                      const pct = total > 0 ? Math.round((val / total) * 100) : 0;
                      return {
                        text: `${label}: ${val.toFixed(2)} (${pct}%)`,
                        fillStyle: data.datasets[0].backgroundColor[i],
                        hidden: isNaN(data.datasets[0].data[i]),
                        index: i,
                      };
                    });
                  }
                  return [];
                },
              },
            },
            tooltip: {
              callbacks: {
                label: (ctx) => ` ${ctx.label}: ${ctx.parsed.toFixed(2)}`,
              },
            },
          },
        },
      });
    }

    // 3. Document Pipeline Tracing Chart
    const pipelineEl = document.querySelector('#chart-pipeline');
    if (pipelineEl && pipeline) {
      new Chart(pipelineEl, {
        type: 'bar',
        data: {
          labels: ['Recorded ✅', 'Ready to Record ⏱', 'Needs Review ⚠️', 'Failed ❌', 'Duplicates 📑', 'Dismissed 🚫'],
          datasets: [{
            label: 'Document Count',
            data: [
              pipeline.recorded || 0,
              pipeline.ready || 0,
              pipeline.review || 0,
              pipeline.failed || 0,
              pipeline.duplicates || 0,
              pipeline.dismissed || 0,
            ],
            backgroundColor: ['#16a34a', '#2563eb', '#d97706', '#dc2626', '#f59e0b', '#64748b'],
            borderRadius: 6,
          }],
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
          },
          scales: {
            x: {
              beginAtZero: true,
              ticks: { stepSize: 1, color: '#677873' },
              grid: { color: '#e0e6df' },
            },
            y: {
              grid: { display: false },
              ticks: { color: '#173c39', font: { weight: '600' } },
            },
          },
        },
      });
    }
  } catch (e) {
    console.error('Failed to initialize charts:', e);
  }
}


// Interactive client-side table sorting
function initTableSorting() {
  const table = document.querySelector('#expense-table');
  if (!table) return;

  const headers = table.querySelectorAll('.sortable-th');
  let currentSort = { column: null, ascending: true };

  headers.forEach(th => {
    th.addEventListener('click', () => {
      const sortKey = th.dataset.sort;
      const isAscending = currentSort.column === sortKey ? !currentSort.ascending : false;
      currentSort = { column: sortKey, ascending: isAscending };

      // Update header indicators
      headers.forEach(h => {
        const ind = h.querySelector('.sort-indicator');
        if (ind) ind.textContent = '⇅';
      });
      const activeIndicator = th.querySelector('.sort-indicator');
      if (activeIndicator) activeIndicator.textContent = isAscending ? '▲' : '▼';

      const tbody = table.querySelector('#expense-table-body');
      const rows = Array.from(tbody.querySelectorAll('tr[id^="expense-row-"]'));

      rows.sort((a, b) => {
        let valA = a.dataset[camelCase(sortKey)] || '';
        let valB = b.dataset[camelCase(sortKey)] || '';

        if (sortKey === 'amount') {
          valA = parseFloat(valA) || 0;
          valB = parseFloat(valB) || 0;
          return isAscending ? valA - valB : valB - valA;
        }

        const comp = valA.localeCompare(valB);
        return isAscending ? comp : -comp;
      });

      rows.forEach(r => tbody.appendChild(r));
    });
  });
}

function camelCase(str) {
  return str.replace(/-([a-z])/g, g => g[1].toUpperCase());
}

function initReportingCurrency() {
  const selector = document.querySelector('#report-currency');
  if (!selector) return;
  selector.addEventListener('change', () => {
    const url = new URL(location.href);
    url.searchParams.set('report_currency', selector.value);
    location.href = url.toString();
  });

  const dataEl = document.querySelector('#finance-chart-data');
  if (!dataEl) return;
  const data = JSON.parse(dataEl.textContent);
  const target = data.reportCurrency || 'USD';
  const sources = data.sourceCurrencies || [];
  const values = data.expenses || [];
  const symbols = sources.filter(code => code !== target).join(',');
  const rateUrl = `/api/v1/exchange-rates?base=${encodeURIComponent(target)}&symbols=${encodeURIComponent(symbols)}`;
  fetch(rateUrl).then(response => {
    if (!response.ok) throw new Error('Rates unavailable');
    return response.json();
  }).then(result => {
    const rates = { [target]: 1, ...result.rates };
    const dateText = `Rates updated ${result.updated_at || result.date} · Source: ExchangeRate-API Open Access`;
    const rateDate = document.querySelector('#rate-date');
    if (rateDate) rateDate.textContent = dateText;
    const metricDate = document.querySelector('#report-rate-date');
    if (metricDate) metricDate.textContent = `Rates dated ${result.date}`;
    const ratePairs = document.querySelector('#exchange-rate-pairs');
    if (ratePairs) {
      ratePairs.replaceChildren();
      for (const source of sources.filter(code => code !== target)) {
        const sourcePerTarget = Number(rates[source]);
        const row = document.createElement('div');
        row.className = 'distribution';
        const label = document.createElement('span');
        label.textContent = `1 ${source} =`;
        const value = document.createElement('strong');
        value.textContent = Number.isFinite(sourcePerTarget) && sourcePerTarget > 0
          ? `${new Intl.NumberFormat(undefined, { maximumSignificantDigits: 8 }).format(1 / sourcePerTarget)} ${target}`
          : `Rate unavailable in ${target}`;
        row.append(label, value);
        ratePairs.append(row);
      }
      if (!sources.some(code => code !== target)) ratePairs.textContent = `1 ${target} = 1 ${target}`;
    }

    const converted = values.map(item => {
      const sourceUnitsPerTarget = Number(rates[item.currency]);
      return { ...item, converted: Number.isFinite(sourceUnitsPerTarget) && sourceUnitsPerTarget > 0
        ? Number(item.amount) / sourceUnitsPerTarget : null };
    });
    const fmt = amount => new Intl.NumberFormat(undefined, { style: 'currency', currency: target }).format(amount);
    const sum = rows => rows.reduce((total, item) => total + (item.converted ?? 0), 0);
    const total = sum(converted.filter(item => item.converted !== null));
    const totalEl = document.querySelector('#report-total');
    if (totalEl) totalEl.textContent = fmt(total);

    const sourceTotals = new Map();
    const sourceConverted = new Map();
    for (const item of converted) {
      sourceTotals.set(item.currency, (sourceTotals.get(item.currency) || 0) + Number(item.amount));
      if (item.converted !== null) sourceConverted.set(item.currency, (sourceConverted.get(item.currency) || 0) + item.converted);
      const cell = document.querySelector(`[data-convert-id="${CSS.escape(item.id)}"]`);
      if (cell) cell.textContent = item.converted === null ? `Conversion unavailable to ${target}` : `≈ ${fmt(item.converted)}`;
    }
    const details = document.querySelector('#source-currency-totals');
    if (details) {
      details.replaceChildren();
      for (const [code, amount] of sourceTotals) {
        const row = document.createElement('div');
        row.className = 'distribution';
        const label = document.createElement('span');
        label.textContent = `${code} source total`;
        const value = document.createElement('strong');
        const convertedAmount = sourceConverted.get(code);
        value.textContent = `${new Intl.NumberFormat(undefined, { style: 'currency', currency: code }).format(amount)}  →  ${convertedAmount === undefined ? 'rate unavailable' : fmt(convertedAmount)}`;
        row.append(label, value);
        details.append(row);
      }
      if (!sourceTotals.size) details.textContent = 'No confirmed expenses in this view.';
    }
    for (const [containerId, key] of [['converted-categories', 'category'], ['converted-timeline', 'month']]) {
      const aggregate = new Map();
      converted.forEach(item => {
        if (item.converted === null) return;
        aggregate.set(item[key], (aggregate.get(item[key]) || 0) + item.converted);
      });
      const container = document.querySelector(`#${containerId}`);
      if (!container) continue;
      container.replaceChildren();
      for (const [labelText, amount] of [...aggregate].sort(([a], [b]) => a.localeCompare(b))) {
        const row = document.createElement('div');
        row.className = 'distribution';
        const label = document.createElement('span');
        label.textContent = key === 'category' ? labelText.replaceAll('_', ' ') : labelText;
        const value = document.createElement('strong');
        value.textContent = fmt(amount);
        row.append(label, value);
        container.append(row);
      }
      if (!aggregate.size) container.textContent = 'No converted records available.';
    }

    const categoryTotals = new Map();
    const monthTotals = new Map();
    converted.forEach(item => {
      if (item.converted === null) return;
      categoryTotals.set(item.category, (categoryTotals.get(item.category) || 0) + item.converted);
      monthTotals.set(item.month, (monthTotals.get(item.month) || 0) + item.converted);
    });
    data.summary = {
      totals: { [target]: String(total) },
      categories: [...categoryTotals].map(([category, amount]) => ({ category, currency: target, total: String(amount) })),
      timeline: [...monthTotals].sort(([a], [b]) => a.localeCompare(b)).map(([month, amount]) => ({ month, currency: target, total: String(amount) })),
      count: values.length,
    };
    initFinanceCharts();
  }).catch(() => {
    const totalEl = document.querySelector('#report-total');
    if (totalEl) totalEl.textContent = 'Exchange rate unavailable';
    const dateEl = document.querySelector('#rate-date');
    if (dateEl) dateEl.textContent = 'Could not load a rate. Original currency amounts are still shown above.';
    const metricDate = document.querySelector('#report-rate-date');
    if (metricDate) metricDate.textContent = 'Try again later; no estimated rate was applied.';
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    initTableSorting();
    initReportingCurrency();
  });
} else {
  initTableSorting();
  initReportingCurrency();
}


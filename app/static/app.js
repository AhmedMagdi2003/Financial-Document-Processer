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

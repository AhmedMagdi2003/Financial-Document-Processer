const notice = (text, error = false) => {
  const box = document.querySelector('#notice');
  box.textContent = text; box.hidden = false; box.classList.toggle('error', error);
  box.setAttribute('role', error ? 'alert' : 'status'); box.scrollIntoView({block: 'nearest'});
};
async function api(url, method = 'POST', body) {
  const headers = {'X-CSRF-Token': document.querySelector('meta[name=csrf-token]').content};
  if (!(body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch(url, {method, headers,
    body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined});
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail));
  return result;
}
function action(form, handler) {
  if (!form) return;
  form.addEventListener('submit', async event => {
    event.preventDefault(); const buttons = form.querySelectorAll('button');
    buttons.forEach(b => b.disabled = true);
    try { await handler(new FormData(form)); }
    catch (error) { notice(error.message, true); }
    finally { buttons.forEach(b => b.disabled = false); }
  });
}
action(document.querySelector('#upload-form'), async data => {
  notice('Inspecting and processing your document. This may take a moment…');
  const result = await api('/api/v1/documents', 'POST', data);
  location.href = '/documents/' + result.document.id;
});
action(document.querySelector('#content-form'), async data => {
  notice('Preparing three drafts from your source facts…');
  const result = await api('/api/v1/content', 'POST', {source: data.get('source')});
  location.href = '/content/' + result.id;
});
const review = document.querySelector('#review-form');
action(review, async data => {
  const candidate = JSON.parse(document.querySelector('#candidate-data').textContent);
  for (const key of ['vendor', 'date', 'document_number', 'grand_total', 'currency', 'subtotal', 'tax', 'discount', 'category_id']) {
    candidate[key] = data.get(key).trim() || null;
  }
  candidate.description = data.get('description'); candidate.tax_mode = data.get('tax_mode');
  candidate.discount_explicit = data.has('discount_explicit');
  await api(`/api/v1/documents/${review.dataset.id}/fields`, 'PATCH', {version: Number(review.dataset.version), candidate});
  location.reload();
});
document.querySelectorAll('[data-review-action]').forEach(button => button.addEventListener('click', async () => {
  const holder = button.closest('[data-doc]'), type = button.dataset.reviewAction;
  button.disabled = true;
  try {
    notice(type === 'reextract' ? 'Starting a new extraction attempt…' : 'Saving your decision…');
    await api(`/api/v1/documents/${holder.dataset.doc}/${type}`, 'POST', type === 'reextract' ? undefined : {
      version: Number(holder.dataset.version), justification: document.querySelector('#justification').value});
    location.reload();
  } catch (error) { notice(error.message, true); } finally { button.disabled = false; }
}));
const draftForm = document.querySelector('#draft-form');
let dirty = false;
draftForm?.addEventListener('input', () => { dirty = true; });
action(draftForm, async data => {
  await api(`/api/v1/content/${draftForm.dataset.id}`, 'PUT', {revision: Number(draftForm.dataset.revision),
    drafts: {linkedin: data.get('linkedin'), newsletter: data.get('newsletter'), website: data.get('website')},
    channels: data.getAll('channels')});
  location.reload();
});
async function publish(retry) {
  if (dirty) { notice('Save your edits as a new revision before approving or retrying.', true); return; }
  const buttons = draftForm.querySelectorAll('button'); buttons.forEach(b => b.disabled = true);
  try {
    notice('Sending the approved revision to the selected test destinations…');
    const result = await api(`/api/v1/content/${draftForm.dataset.id}/${retry ? 'retry' : 'approve-and-publish'}`, 'POST', {
      revision: Number(draftForm.dataset.revision), digest: draftForm.dataset.digest});
    notice(result.map(p => `${p.channel}: ${p.status}${p.error ? ' · ' + p.error : ''}`).join('\n'), result.some(p => p.status === 'failed'));
    // Reload shows durable per-channel results; the live status message is read first.
    setTimeout(() => location.reload(), 1600);
  } catch (error) { notice(error.message, true); } finally { buttons.forEach(b => b.disabled = false); }
}
document.querySelector('#approve-publish')?.addEventListener('click', () => publish(false));
document.querySelector('#retry-publish')?.addEventListener('click', () => publish(true));
const rejectForm = document.querySelector('#reject-form');
action(rejectForm, async data => {
  await api(`/api/v1/content/${rejectForm.dataset.id}/reject`, 'POST', {
    revision: Number(rejectForm.dataset.revision), justification: data.get('justification')});
  location.reload();
});
document.querySelectorAll('.category-form').forEach(form => action(form, async data => {
  await api(`/api/v1/categories/${form.dataset.id}`, 'PATCH', {name: data.get('name'), definition: data.get('definition'), active: data.has('active')});
  notice('Category saved. Its ID and historical records are preserved.');
}));
document.querySelector('#logout')?.addEventListener('click', async () => { await api('/logout'); location.href = '/login'; });

action(document.querySelector('#create-project'), async data => {
  const project = await api('/api/v1/projects', 'POST', {
    id: data.get('id').trim(), name: data.get('name').trim(),
  });
  location.href = `/?project=${encodeURIComponent(project.id)}`;
});
document.querySelectorAll('.project-form').forEach(form => action(form, async data => {
  await api(`/api/v1/projects/${encodeURIComponent(form.dataset.id)}`, 'PATCH', {
    name: data.get('name').trim(),
  });
  notice('Project name saved. The project ID and existing expenses are preserved.');
}));

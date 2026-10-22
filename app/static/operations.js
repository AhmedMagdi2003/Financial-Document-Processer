(() => {
  const stage = document.getElementById('ops-stage');
  const status = document.getElementById('ops-status');
  if (!stage || !status) return;
  const events = Array.from(document.querySelectorAll('.ops-event'));
  function filterEvents() {
    let visible = 0;
    for (const event of events) {
      event.hidden = Boolean((stage.value && event.dataset.stage !== stage.value) ||
        (status.value && event.dataset.status !== status.value));
      if (!event.hidden) visible += 1;
    }
    document.getElementById('ops-event-count').textContent = `${visible} of ${events.length} events`;
    document.getElementById('ops-no-events').hidden = visible > 0 || events.length === 0;
  }
  stage.addEventListener('change', filterEvents);
  status.addEventListener('change', filterEvents);
})();

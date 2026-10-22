(() => {
  const stage = document.getElementById('ops-stage');
  const status = document.getElementById('ops-status');
  const tabs = document.querySelectorAll('[data-ops-tab]');
  const events = Array.from(document.querySelectorAll('.ops-event'));
  let currentTab = 'all';

  function filterEvents() {
    let visible = 0;
    for (const event of events) {
      const matchStage = !stage || !stage.value || event.dataset.stage === stage.value;
      const matchStatus = !status || !status.value || event.dataset.status === status.value;

      let matchTab = true;
      if (currentTab === 'failed') {
        matchTab = event.dataset.failed === 'true';
      } else if (currentTab === 'model') {
        matchTab = event.dataset.stage === 'model';
      } else if (currentTab === 'human') {
        matchTab = event.dataset.stage === 'human';
      } else if (currentTab === 'integration') {
        matchTab = event.dataset.stage === 'integration';
      }

      const isVisible = matchStage && matchStatus && matchTab;
      event.hidden = !isVisible;
      if (isVisible) visible += 1;
    }

    const countEl = document.getElementById('ops-event-count');
    if (countEl) countEl.textContent = `${visible} of ${events.length} events`;
    const noEventsEl = document.getElementById('ops-no-events');
    if (noEventsEl) noEventsEl.hidden = visible > 0 || events.length === 0;
  }

  if (stage) stage.addEventListener('change', filterEvents);
  if (status) status.addEventListener('change', filterEvents);

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => {
        t.style.background = '#fff';
        t.style.color = t.dataset.opsTab === 'failed' ? '#b91c1c' : '#334155';
        t.classList.remove('active');
      });
      tab.classList.add('active');
      tab.style.background = tab.dataset.opsTab === 'failed' ? '#ef4444' : '#1e6255';
      tab.style.color = '#fff';
      currentTab = tab.dataset.opsTab;
      filterEvents();
    });
  });
})();

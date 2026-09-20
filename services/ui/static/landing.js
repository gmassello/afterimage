const landingDemo = document.querySelector('[data-landing-demo]');

if (landingDemo) {
  landingDemo.classList.add('landing-demo-ready');
  const tabs = [...landingDemo.querySelectorAll('[data-landing-tab]')];
  const panels = [...landingDemo.querySelectorAll('[data-landing-panel]')];
  const controls = [...landingDemo.querySelectorAll('[data-landing-action]')];
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const stepDelay = 1200;
  let timers = [];

  const stopPlayback = () => {
    timers.forEach(clearTimeout);
    timers = [];
    landingDemo.classList.remove('landing-demo-playing');
  };

  const playPanel = (panel) => {
    stopPlayback();
    const steps = [...panel.querySelectorAll('.landing-rail-step')];
    const outcome = panel.querySelector('.landing-outcome');
    steps.forEach((step) => step.classList.toggle('landing-step-visible', reducedMotion.matches));
    outcome.classList.toggle('landing-step-visible', reducedMotion.matches);
    if (reducedMotion.matches) return;
    landingDemo.classList.add('landing-demo-playing');
    steps.forEach((step, index) => {
      timers.push(setTimeout(() => step.classList.add('landing-step-visible'), stepDelay * (index + 1)));
    });
    timers.push(setTimeout(() => {
      outcome.classList.add('landing-step-visible');
      landingDemo.classList.remove('landing-demo-playing');
    }, stepDelay * (steps.length + 1)));
  };

  const selectScenario = (tab, focus = false) => {
    tabs.forEach((candidate) => {
      const selected = candidate === tab;
      candidate.setAttribute('aria-selected', String(selected));
      candidate.tabIndex = selected ? 0 : -1;
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.landingPanel !== tab.dataset.landingTab;
    });
    playPanel(panels.find((panel) => !panel.hidden));
    if (focus) tab.focus();
  };

  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectScenario(tab));
    tab.addEventListener('keydown', (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      let next = index;
      if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      selectScenario(tabs[next], true);
    });
  });

  controls.forEach((control) => {
    control.addEventListener('click', () => {
      const selected = tabs.findIndex((tab) => tab.getAttribute('aria-selected') === 'true');
      if (control.dataset.landingAction === 'pause') return stopPlayback();
      if (control.dataset.landingAction === 'replay') return playPanel(panels[selected]);
      const offset = control.dataset.landingAction === 'previous' ? -1 : 1;
      selectScenario(tabs[(selected + offset + tabs.length) % tabs.length], true);
    });
  });

  reducedMotion.addEventListener('change', () => {
    const selected = tabs.findIndex((tab) => tab.getAttribute('aria-selected') === 'true');
    playPanel(panels[selected]);
  });
  playPanel(panels[0]);
}

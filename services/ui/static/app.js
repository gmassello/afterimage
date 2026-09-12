const root = document.documentElement;
const label = document.getElementById('theme-label');
const toggle = document.getElementById('theme');
const paint = (theme) => {
  root.dataset.theme = theme;
  label.textContent = theme === 'dark' ? 'Light' : 'Dark';
  toggle.setAttribute('aria-label', `Switch to the ${theme === 'dark' ? 'light' : 'dark'} theme`);
};
paint(root.dataset.theme);
toggle.addEventListener('click', () => {
  const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
  paint(next);
  try { localStorage.setItem('afterimage-theme', next); } catch (e) {}
});

function placeBoxes() {
  document.querySelectorAll('.box[data-bbox]').forEach((box) => {
    const img = box.parentElement.querySelector('img');
    const place = () => {
      if (!img.naturalWidth || !img.naturalHeight) return;
      const [x, y, w, h] = JSON.parse(box.dataset.bbox);
      box.style.left = (x / img.naturalWidth * 100) + '%';
      box.style.top = (y / img.naturalHeight * 100) + '%';
      box.style.width = (w / img.naturalWidth * 100) + '%';
      box.style.height = (h / img.naturalHeight * 100) + '%';
      box.hidden = false;
    };
    img.complete ? place() : img.addEventListener('load', place);
  });
}
placeBoxes();

const page = document.querySelector('.page');
const says = document.querySelector('.runstate .says');
const clock = document.querySelector('.runstate .clock');
const opened = Date.now();
let ticker = null;

const say = (text) => {
  if (says && text && says.textContent !== text) says.textContent = text;
};

const stopClock = () => {
  clearInterval(ticker);
  if (clock) clock.textContent = '';
};

if (page.dataset.runState === 'unstarted' && page.dataset.executeUrl) {
  fetch(page.dataset.executeUrl, { method: 'POST' }).catch(() => {
    stopClock();
    say('the run could not be started — reload the page to retry');
  });
}

if (document.querySelector('[data-poll]') && page.dataset.runState !== 'done') {
  const every = Number(document.querySelector('[data-poll]').dataset.poll);
  const cap = 400;
  let live = true;
  let attempts = 0;
  let pending = null;
  const halt = () => { live = false; stopClock(); };
  addEventListener('submit', halt, true);
  addEventListener('click', (e) => e.target.closest?.('a') && halt(), true);
  const block = () => document.querySelector('[data-poll]');
  const busy = () => {
    const shown = block();
    return shown.contains(document.activeElement) || !!shown.querySelector('details[open]');
  };
  const flush = () => {
    if (!pending || busy()) return;
    block().replaceWith(pending);
    pending = null;
    placeBoxes();
  };
  addEventListener('focusout', () => setTimeout(flush, 0));
  addEventListener('toggle', flush, true);
  const poll = async () => {
    if (document.hidden) { setTimeout(poll, 5000); return; }
    let next = every;
    try {
      const res = await fetch(location.pathname, { headers: { accept: 'text/html' } });
      const doc = new DOMParser().parseFromString(await res.text(), 'text/html');
      pending = doc.querySelector('[data-poll]') || pending;
      flush();
      say(doc.querySelector('.runstate .says')?.textContent);
      const state = doc.querySelector('.page').dataset.runState;
      if (state) page.dataset.runState = state;
      if (state === 'done') stopClock();
    } catch (e) { next = 3000; }
    if (!live || page.dataset.runState === 'done') return;
    if (++attempts >= cap) {
      stopClock();
      say(`no answer after ${Math.round(cap * every / 60000)} minutes — reload the page to retry`);
      return;
    }
    setTimeout(poll, next);
  };
  if (clock) {
    ticker = setInterval(() => {
      clock.textContent = ` · ${Math.round((Date.now() - opened) / 1000)} s`;
    }, 1000);
  }
  setTimeout(poll, every);
}

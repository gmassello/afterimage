const root = document.documentElement;
const label = document.getElementById('theme-label');
const paint = (theme) => {
  root.dataset.theme = theme;
  label.textContent = theme === 'dark' ? 'Light' : 'Dark';
};
paint(root.dataset.theme === 'light' ? 'light' : 'dark');
document.getElementById('theme').addEventListener('click', () => {
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
if (page.dataset.runState === 'unstarted' && page.dataset.executeUrl) {
  fetch(page.dataset.executeUrl, { method: 'POST' }).catch(() => {});
}

if (document.querySelector('[data-poll]') && page.dataset.runState !== 'done') {
  const every = Number(document.querySelector('[data-poll]').dataset.poll);
  let live = true;
  let attempts = 0;
  const halt = () => { live = false; };
  addEventListener('submit', halt, true);
  addEventListener('click', (e) => e.target.closest?.('a') && halt(), true);
  const busy = () => [...document.querySelectorAll('details')].some((d) => d.open);
  const poll = async () => {
    if (document.hidden) { setTimeout(poll, 5000); return; }
    let next = every;
    try {
      const res = await fetch(location.pathname, { headers: { accept: 'text/html' } });
      const doc = new DOMParser().parseFromString(await res.text(), 'text/html');
      const fresh = doc.querySelector('[data-poll]');
      const current = document.querySelector('[data-poll]');
      if (fresh && current && !busy()) {
        current.replaceWith(fresh);
        placeBoxes();
      }
      const state = doc.querySelector('.page').dataset.runState;
      if (state) page.dataset.runState = state;
    } catch (e) { next = 3000; }
    if (live && page.dataset.runState !== 'done' && ++attempts < 400) setTimeout(poll, next);
  };
  setTimeout(poll, every);
}

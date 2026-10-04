const T = (() => {
  const fallback = {
    dark: 'Dark',
    light: 'Light',
    confirm: 'Confirm?',
    arm: 'Click Confirm? again to {action}, or move away to cancel.',
    tooLarge: 'image larger than 6 MB',
    notAnImage: 'not a decodable image',
    sampleFailed: 'the example could not be loaded \u2014 pick a file instead',
    sampleLoaded: 'Loaded: {sample}. Press inspect.',
    sampleLocked: 'Sample 1 first: it sets the reference.',
    runStartFailed: 'the run could not be started',
    pollTimeout: 'the run did not answer in time \u2014 open activity to check it',
  };
  try {
    return { ...fallback, ...JSON.parse(document.getElementById('i18n').textContent) };
  } catch (e) { return fallback; }
})();

const root = document.documentElement;
const label = document.getElementById('theme-label');
const toggle = document.getElementById('theme');
const paint = (theme) => {
  root.dataset.theme = theme;
  label.textContent = theme === 'dark' ? T.light : T.dark;
};
paint(root.dataset.theme === 'dark' ? 'dark' : 'light');
toggle.addEventListener('click', () => {
  const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
  paint(next);
  try { localStorage.setItem('afterimage-theme', next); } catch (e) {}
});

const duration = (name) => parseFloat(getComputedStyle(root).getPropertyValue(name)) || 0;

function tween(cell, shown, span, ease = (at) => at) {
  const [, lead, rest] = shown.match(/^(\d+(?:\.\d+)?)([\s\S]*)$/) || [];
  if (!lead || !span) return;
  const target = Number(lead);
  const decimals = (lead.split('.')[1] || '').length;
  const began = performance.now();
  const tick = (now) => {
    const at = Math.min(1, (now - began) / span);
    cell.textContent = at < 1 ? (target * ease(at)).toFixed(decimals) + rest : shown;
    if (at < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

let counted = null;
function countUp() {
  const cell = document.querySelector('.hero .big .n');
  if (!cell) return;
  const shown = cell.textContent.trim();
  if (shown === counted) return;
  counted = shown;
  tween(cell, shown, duration('--dur-live'));
}
countUp();

const metrics = document.querySelector('.landing-metrics');
if (metrics && duration('--dur-live')) {
  const watcher = new IntersectionObserver((entries) => {
    if (!entries.some((entry) => entry.isIntersecting)) return;
    watcher.disconnect();
    metrics.querySelectorAll('strong').forEach((cell) =>
      tween(cell, cell.textContent.trim(), 900, (at) => 1 - Math.pow(1 - at, 3)));
  }, { threshold: 0.4 });
  watcher.observe(metrics);
}

let typed = { run: null, count: 0 };
function typeLines() {
  const lines = [...document.querySelectorAll('.terminal li')];
  const run = document.querySelector('.terminal .chrome span')?.textContent;
  if (typed.run !== run) typed = { run, count: 0 };
  const fresh = lines.slice(typed.count);
  typed.count = lines.length;
  const step = duration('--dur-type');
  if (!fresh.length || !step) return;
  let end = 0;
  const plan = fresh.map((line) => {
    const chars = line.textContent.length;
    line.style.setProperty('--shown', '0ch');
    const entry = { line, chars, from: end };
    end += chars * step + 350;
    return entry;
  });
  const began = performance.now();
  const frame = () => {
    const elapsed = performance.now() - began;
    plan.forEach(({ line, chars, from }) => {
      const shown = Math.max(0, Math.min(chars, Math.floor((elapsed - from) / step)));
      if (shown >= chars) line.style.removeProperty('--shown');
      else line.style.setProperty('--shown', `${shown}ch`);
    });
    if (elapsed < end) setTimeout(frame, step);
  };
  frame();
}
typeLines();

function zoomRegions() {
  document.querySelectorAll('.zoom[data-bbox]').forEach((zoom) => {
    const img = zoom.querySelector('img');
    const place = () => {
      const W = img.naturalWidth, H = img.naturalHeight;
      if (!W || !H) return;
      const [x, y, w, h] = JSON.parse(zoom.dataset.bbox);
      const side = Math.min(Math.max(80, Math.max(w, h) * 2.5), W, H);
      const left = Math.min(Math.max(x + w / 2 - side / 2, 0), W - side);
      const top = Math.min(Math.max(y + h / 2 - side / 2, 0), H - side);
      img.style.width = (W / side * 100) + '%';
      img.style.left = (-left / side * 100) + '%';
      img.style.top = (-top / side * 100) + '%';
      zoom.classList.add('zoomed');
    };
    img.complete ? place() : img.addEventListener('load', place);
  });
}

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
      requestAnimationFrame(() => box.classList.add('enter'));
    };
    img.complete ? place() : img.addEventListener('load', place);
  });
}
placeBoxes();
zoomRegions();

const disarm = (button) => {
  button.textContent = button.dataset.armed;
  delete button.dataset.armed;
  const say = button.closest('.acts')?.querySelector('.say');
  if (say) say.textContent = '';
};

addEventListener('click', (e) => {
  const button = e.target.closest?.('.acts button');
  if (!button || button.dataset.armed) return;
  e.preventDefault();
  button.dataset.armed = button.textContent;
  button.textContent = T.confirm;
  button.focus();
  const say = button.closest('.acts')?.querySelector('.say');
  if (say) say.textContent = T.arm.replace('{action}', button.dataset.armed.toLowerCase());
});

addEventListener('focusout', (e) => {
  const button = e.target.closest?.('.acts button');
  if (button && button.dataset.armed) disarm(button);
});

const MAX_UPLOAD_BYTES = 6 * 1024 * 1024;
const zone = document.querySelector('.dropzone');
if (zone) {
  const input = zone.querySelector('input[type=file]');
  const preview = zone.querySelector('.drop-preview');
  const review = () => {
    const file = input.files[0];
    let problem = '';
    if (file && file.size > MAX_UPLOAD_BYTES) problem = T.tooLarge;
    else if (file && file.type && !['image/jpeg', 'image/png'].includes(file.type)) problem = T.notAnImage;
    input.setCustomValidity(problem);
    if (preview.src) URL.revokeObjectURL(preview.src);
    preview.hidden = !file || !!problem;
    zone.classList.toggle('picked', !preview.hidden);
    if (!preview.hidden) preview.src = URL.createObjectURL(file);
  };
  input.addEventListener('change', review);
  zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('over'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('over');
    input.files = e.dataTransfer.files;
    review();
  });
  const demoAssets = new Set([...document.querySelectorAll('.sample[data-asset]')]
    .map((sample) => sample.dataset.asset));
  const id = document.getElementById('asset-id');
  const sampleInspect = document.querySelector('[data-sample-inspect]');
  const ownPhoto = () => {
    if (id && demoAssets.has(id.value)) id.value = '';
    if (sampleInspect) sampleInspect.disabled = true;
    document.querySelectorAll('.sample[aria-pressed=true]').forEach((other) => other.setAttribute('aria-pressed', 'false'));
  };
  input.addEventListener('change', ownPhoto);
  zone.addEventListener('drop', ownPhoto);
  document.querySelectorAll('.sample[data-sample]').forEach((button) => {
    button.addEventListener('click', async () => {
      if (button.getAttribute('aria-disabled') === 'true') {
        const status = document.querySelector('[data-sample-status]');
        if (status) status.textContent = T.sampleLocked;
        return;
      }
      if (id && (!id.value || demoAssets.has(id.value))) id.value = button.dataset.asset;
      try {
        const picked = new DataTransfer();
        const body = await (await fetch(button.dataset.sample)).blob();
        picked.items.add(new File([body], button.dataset.name, { type: body.type }));
        input.files = picked.files;
        review();
        document.querySelectorAll('.sample[data-sample]').forEach((other) => {
          other.setAttribute('aria-pressed', String(other === button));
        });
        const status = document.querySelector('[data-sample-status]');
        if (status) status.textContent = T.sampleLoaded.replace('{sample}', button.querySelector('.name').textContent);
        if (sampleInspect) {
          sampleInspect.disabled = false;
          sampleInspect.scrollIntoView({ block: 'nearest' });
        }
      } catch (e) {
        input.setCustomValidity(T.sampleFailed);
        input.reportValidity();
      }
    });
  });
  const carousel = document.querySelector('[data-carousel]');
  if (carousel) {
    const track = carousel.querySelector('[data-groups]');
    const groups = [...track.querySelectorAll('.group')];
    const count = carousel.querySelector('[data-carousel-count]');
    const steps = [...carousel.querySelectorAll('[data-carousel-step]')];
    const current = () => Math.round(track.scrollLeft / track.clientWidth) || 0;
    const show = () => {
      const at = current();
      if (count.textContent !== groups[at].dataset.groupLabel) count.textContent = groups[at].dataset.groupLabel;
      steps.forEach((step) => {
        const to = at + Number(step.dataset.carouselStep);
        step.setAttribute('aria-disabled', String(to < 0 || to >= groups.length));
      });
    };
    const go = (to, behavior) => {
      if (to >= 0 && to < groups.length) track.scrollTo({ left: to * track.clientWidth, behavior });
    };
    steps.forEach((step) => step.addEventListener('click', () => go(current() + Number(step.dataset.carouselStep))));
    track.addEventListener('keydown', (e) => {
      if (e.target !== track || !['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
      e.preventDefault();
      go(current() + (e.key === 'ArrowRight' ? 1 : -1));
    });
    let settle;
    track.addEventListener('scroll', () => { clearTimeout(settle); settle = setTimeout(show, 120); });
    show();
    const preselect = carousel.dataset.preselect;
    const chosen = preselect && document.querySelector(`.sample[data-name="${preselect}.png"]`);
    if (chosen) {
      go(groups.indexOf(chosen.closest('.group')), 'instant');
      chosen.click();
    }
  }
}

const assetFilters = document.querySelector('[data-asset-filters]');
if (assetFilters) {
  const search = assetFilters.querySelector('input[type=search]');
  const result = assetFilters.querySelector('select');
  const cards = [...document.querySelectorAll('.gallery .asset')];
  const empty = document.querySelector('.asset-filter-empty');
  const applyAssetFilters = () => {
    const query = search.value.trim().toLowerCase();
    let shown = 0;
    cards.forEach((card) => {
      const matchesQuery = !query || card.dataset.assetId.toLowerCase().includes(query)
        || card.textContent.toLowerCase().includes(query);
      const matchesResult = !result.value || card.dataset.assetResult === result.value;
      card.hidden = !(matchesQuery && matchesResult);
      if (!card.hidden) shown += 1;
    });
    empty.hidden = shown !== 0;
  };
  assetFilters.addEventListener('input', applyAssetFilters);
  assetFilters.addEventListener('submit', (event) => event.preventDefault());
}

addEventListener('input', (e) => {
  const slider = e.target.closest?.('.compare .split');
  if (slider) slider.parentElement.style.setProperty('--split', slider.value + '%');
}, true);

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
let stopPolling = stopClock;

if (page.dataset.runState === 'unstarted' && page.dataset.executeUrl) {
  const failed = () => {
    stopPolling();
    say(T.runStartFailed);
  };
  fetch(page.dataset.executeUrl, { method: 'POST' })
    .then((res) => { if (!res.ok && res.status !== 409) failed(); })
    .catch(failed);
}

if (document.querySelector('[data-poll]') && page.dataset.runState !== 'done') {
  const every = Number(document.querySelector('[data-poll]').dataset.poll);
  const cap = 400;
  let live = true;
  let attempts = 0;
  let pending = null;
  const halt = () => { live = false; stopClock(); };
  addEventListener('submit', halt, true);
  addEventListener('click', (e) => {
    const link = e.target.closest?.('a[href]');
    if (link && !link.getAttribute('href').startsWith('#') && !e.ctrlKey && !e.metaKey && e.button === 0) halt();
  }, true);
  stopPolling = halt;
  const block = () => document.querySelector('[data-poll]');
  const busy = () => {
    const shown = block();
    return shown.contains(document.activeElement) || !!shown.querySelector('details[open]');
  };
  const flush = () => {
    if (!pending || busy()) return;
    const arrived = pending;
    pending = null;
    const swap = () => { block().replaceWith(arrived); placeBoxes(); zoomRegions(); countUp(); typeLines(); };
    document.startViewTransition ? document.startViewTransition(swap) : swap();
  };
  addEventListener('focusout', () => setTimeout(flush, 0));
  addEventListener('toggle', flush, true);
  const poll = async () => {
    if (!live || page.dataset.runState === 'done') return;
    if (++attempts >= cap) {
      stopClock();
      say(block().dataset.pollTimeout || T.pollTimeout);
      return;
    }
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
    setTimeout(poll, next);
  };
  if (clock) {
    ticker = setInterval(() => {
      clock.textContent = ` · ${Math.round((Date.now() - opened) / 1000)} s`;
    }, 1000);
  }
  setTimeout(poll, every);
}

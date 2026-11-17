(() => {
  if (customElements.get('twelve-deck-studio')) return;

  const timber = ['#b88250', '#ead1a5', '#886347', '#e1bb88', '#bc9166', '#eed0a2', '#98704d'];
  const cuts = [['nose', 0, .2], ['body', .198, .802], ['tail', .8, 1]];
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const span = (name) => {
    const node = document.createElement('span');
    node.className = name;
    return node;
  };

  // The catalogue uses studio photos with different margins. Sample the matte
  // at the sides and trace the photographed deck at each height.
  function readArtwork(image) {
    const canvas = document.createElement('canvas');
    const scale = Math.min(1, 540 / Math.max(image.naturalWidth, image.naturalHeight));
    const w = canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    const h = canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, w, h);
    ctx.drawImage(image, 0, 0, w, h);
    const pixels = ctx.getImageData(0, 0, w, h).data;
    const rows = [];
    for (let y = 0; y < h; y++) {
      const start = y * w * 4;
      const limit = start + (w - 1) * 4;
      let left = w, right = -1, count = 0;
      for (let x = 1; x < w - 1; x++) {
        const pos = start + x * 4;
        let difference = 0;
        for (let channel = 0; channel < 3; channel++) {
          const matte = (pixels[start + channel] + pixels[limit + channel]) * .5;
          difference = Math.max(difference, Math.abs(pixels[pos + channel] - matte));
        }
        if (difference > 26) {
          left = Math.min(left, x);
          right = x;
          count++;
        }
      }
      if (count > w * .018 && right - left > w * .045) rows.push({ y, left, right });
    }
    if (rows.length < h * .45) return null;
    const ordered = (key) => rows.map(row => row[key]).sort((a, b) => a - b);
    const left = ordered('left')[Math.floor(rows.length * .025)];
    const right = ordered('right')[Math.floor(rows.length * .975)];
    const top = rows[0].y, bottom = rows[rows.length - 1].y;
    const width = right - left + 1, height = bottom - top + 1, ratio = width / height;
    if (ratio < .15 || ratio > .43 || height < .52 * h) return null;
    const cropped = document.createElement('canvas');
    cropped.width = width;
    cropped.height = height;
    cropped.getContext('2d').drawImage(canvas, left, top, width, height, 0, 0, width, height);
    return { url: cropped.toDataURL('image/png'), ratio, rows, top, height, left, width };
  }

  function outline(art, start, end) {
    const lhs = [], rhs = [];
    for (let i = 0; i <= 20; i++) {
      const t = i / 20;
      const y = start + t * (end - start);
      const cap = Math.max(0, (Math.abs(2 * y - 1) - .73) / .27);
      const half = Math.max(.035, Math.sqrt(Math.max(0, 1 - cap * cap))) * .5;
      let lo = .5 - half, hi = .5 + half;
      if (art) {
        const target = art.top + y * (art.height - 1);
        const near = art.rows.filter(row => Math.abs(row.y - target) <= 2);
        if (near.length) {
          const median = key => near.map(row => row[key]).sort((a,b) => a - b)[Math.floor(near.length / 2)];
          const a = (median('left') - art.left) / art.width;
          const b = (median('right') - art.left + 1) / art.width;
          // A run of white ink can blend into a white studio backdrop.
          if (b - a > half * 1.25 || y < .02 || y > .98) {
            lo = Math.max(0, a);
            hi = Math.min(1, b);
          }
        }
      }
      lhs.push((lo * 100).toFixed(2) + '% ' + (t * 100) + '%');
      rhs.unshift((hi * 100).toFixed(2) + '% ' + (t * 100) + '%');
    }
    return 'polygon(' + lhs.concat(rhs).join(',') + ')';
  }

  function buildDeck(image, art) {
    const model = span('tbs-model');
    const floating = span('tbs-model__float');
    const turning = span('tbs-model__turn');
    const url = art ? art.url : image.currentSrc || image.src;
    model.style.setProperty('--deck-art', 'url("' + url.replace(/["\\]/g, '\\$&') + '")');
    model.style.setProperty('--deck-ratio', art ? art.ratio : .25);
    model.style.setProperty('--art-width', art ? '100%' : '305%');
    for (const [name, start, end] of cuts) {
      const piece = span('tbs-model__piece tbs-model__piece--' + name);
      piece.style.setProperty('--deck-shape', outline(art, start, end));
      piece.style.setProperty('--art-size', (100 / (end - start)) + '%');
      piece.style.setProperty('--art-position', (100 * start / (1 - end + start)) + '%');
      const wood = span('tbs-model__skin tbs-model__skin--wood');
      if (name === 'body') wood.append(span('tbs-model__punches'));
      piece.append(wood);
      timber.forEach((colour, i) => {
        const ply = span('tbs-model__skin');
        ply.style.setProperty('--ply', colour);
        ply.style.setProperty('--z', (i - 3) + 'px');
        piece.append(ply);
      });
      piece.append(span('tbs-model__skin tbs-model__skin--graphic'));
      turning.append(piece);
    }
    floating.append(turning);
    model.append(floating);
    return model;
  }

  function addModel(stage, model) {
    stage.querySelector('.tbs-model')?.remove();
    stage.append(model);
    stage.classList.add('is-model');
  }

  class DeckStudio extends HTMLElement {
    connectedCallback() {
      this.startFrame = requestAnimationFrame(() => this.mount());
    }
    mount() {
      this.rack = this.querySelector('.tbs-studio__lineup');
      this.dialog = this.querySelector('dialog');
      if (!this.rack || !this.dialog) return;
      this.events = new AbortController();
      const options = { signal: this.events.signal };
      const paging = this.querySelector('.tbs-studio__paging');
      const [previous, next] = paging.querySelectorAll('button');
      const refresh = () => {
        const max = this.rack.scrollWidth - this.rack.clientWidth;
        const pos = Math.abs(this.rack.scrollLeft);
        paging.hidden = max <= 2;
        previous.setAttribute('aria-disabled', String(pos < 2));
        next.setAttribute('aria-disabled', String(pos >= max - 2));
      };
      for (const stage of this.querySelectorAll('.tbs-studio__stage')) {
        const img = stage.querySelector('img');
        if (!img) continue;
        addModel(stage, buildDeck(img, null));
        const trim = () => {
          if (!img.naturalWidth || !stage.isConnected) return;
          let art;
          try { art = readArtwork(img); } catch { return; }
          if (!art) return;
          addModel(stage, buildDeck(img, art));
          if (this.active?.contains(stage) && this.dialog.open) this.fillViewer();
        };
        if (img.complete) trim();
        else img.addEventListener('load', trim, { ...options, once: true });
      }
      const steer = event => {
        if (event.pointerType === 'touch' || reduceMotion.matches) return;
        const hit = event.target.closest('.tbs-studio__hit');
        if (!hit) return;
        const stage = hit.querySelector('.tbs-studio__stage');
        const rect = stage.getBoundingClientRect();
        const x = Math.max(-1, Math.min(1, 2 * (event.clientX - rect.left) / rect.width - 1));
        const y = Math.max(-1, Math.min(1, 2 * (event.clientY - rect.top) / rect.height - 1));
        stage.style.setProperty('--yaw', (45 + x * 43) + 'deg');
        stage.style.setProperty('--pitch', (-y * 13) + 'deg');
        stage.style.setProperty('--lift', '-9px');
      };
      this.rack.addEventListener('pointermove', steer, options);
      this.rack.addEventListener('pointerover', steer, options);
      this.rack.addEventListener('pointerout', event => {
        const hit = event.target.closest('.tbs-studio__hit');
        if (!hit || hit.contains(event.relatedTarget)) return;
        const stage = hit.querySelector('.tbs-studio__stage');
        for (const prop of ['--yaw', '--pitch', '--lift']) stage.style.removeProperty(prop);
      }, options);
      this.rack.addEventListener('click', event => {
        const hit = event.target.closest('.tbs-studio__hit');
        if (!hit || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || typeof this.dialog.showModal !== 'function') return;
        event.preventDefault();
        this.active = hit;
        const detail = hit.parentElement.querySelector('template');
        this.dialog.querySelector('.tbs-studio__body').replaceChildren(detail.content.cloneNode(true));
        this.dialog.setAttribute('aria-label', this.dialog.querySelector('h2').textContent);
        this.fillViewer();
        this.dialog.showModal();
      }, options);
      this.dialog.addEventListener('click', event => {
        if (event.target === this.dialog || event.target.closest('.tbs-studio__close')) this.dialog.close();
        const turn = event.target.closest('.tbs-studio__turn');
        if (turn) {
          const turned = this.dialog.querySelector('.tbs-studio__viewer').classList.toggle('is-turned');
          turn.setAttribute('aria-pressed', String(turned));
        }
      }, options);
      this.dialog.addEventListener('close', () => {
        this.dialog.querySelector('.tbs-studio__body').replaceChildren();
        this.active?.focus({ preventScroll: true });
        this.active = null;
      }, options);
      this.dialog.addEventListener('change', event => {
        const select = event.target.closest('select[name="id"]');
        if (!select) return;
        const option = select.selectedOptions[0], form = select.form;
        const button = form.querySelector('button[type=submit]');
        button.disabled = option.dataset.available !== 'true';
        button.textContent = button.disabled ? button.dataset.sold : button.dataset.buy;
        form.elements.quantity.value = option.dataset.min;
        this.dialog.querySelector('[data-price]').textContent = option.dataset.price;
        const compare = this.dialog.querySelector('[data-compare]');
        compare.hidden = !option.dataset.compare;
        compare.textContent = option.dataset.compare;
        const full = this.dialog.querySelector('.tbs-studio__full');
        const url = new URL(full.href);
        url.searchParams.set('variant', option.value);
        full.href = url.href;
      }, options);
      paging.addEventListener('click', event => {
        const button = event.target.closest('button');
        if (!button || button.getAttribute('aria-disabled') === 'true') return;
        const stride = this.rack.firstElementChild.getBoundingClientRect().width + parseFloat(getComputedStyle(this.rack).columnGap);
        const rtl = getComputedStyle(this.rack).direction === 'rtl';
        this.rack.scrollBy({ left: Number(button.dataset.step) * stride * (rtl ? -1 : 1), behavior: reduceMotion.matches ? 'instant' : 'smooth' });
      }, options);
      this.rack.addEventListener('scroll', refresh, { ...options, passive: true });
      this.resize = new ResizeObserver(refresh);
      this.resize.observe(this.rack);
      refresh();
    }
    fillViewer() {
      const viewer = this.dialog.querySelector('.tbs-studio__viewer');
      const stage = this.active.querySelector('.tbs-studio__stage');
      viewer.replaceChildren(...Array.from(stage.children).map(node => node.cloneNode(true)));
      viewer.classList.toggle('is-model', stage.classList.contains('is-model'));
      this.dialog.querySelector('.tbs-studio__turn').hidden = !stage.classList.contains('is-model');
    }
    disconnectedCallback() {
      cancelAnimationFrame(this.startFrame);
      this.events?.abort();
      this.resize?.disconnect();
      if (this.dialog?.open) this.dialog.close();
    }
  }
  customElements.define('twelve-deck-studio', DeckStudio);
})();

/* ==========================================================================
   DJOID Studio — Main Application Controller (/billskill compliant)
   ========================================================================== */

(function () {
  const state = {
    appBuild: '2026.10.15-r1',
    tracks: [],
    edges: [],
    presets: {},
    curve: [3, 4, 5, 6, 7, 8, 9, 9],
    weights: {
      harmonic_strictness: 82,
      bpm_tolerance: 3.5,
      energy_adherence: 85,
    },
    solvedSet: { slots: [], metrics: {} },
    bridgeResult: null,
    xmlPreview: '',
    vibeColorMode: 'camelot',
    previewSlotIndex: 1, // Default transition: Slot 1 -> Slot 2
    searchQuery: '',
    energyFilter: 'all',
    seedTrackId: null,
  };

  /* ------------------------------------------------------------------------
     Diagnostics & Error Overlay (/billskill Rule 7)
     ------------------------------------------------------------------------ */
  function showBanner(msg) {
    const banner = document.getElementById('diag-error-banner');
    const txt = document.getElementById('diag-error-text');
    if (!banner || !txt) return;
    txt.textContent = msg;
    banner.classList.add('visible');
    setTimeout(() => banner.classList.remove('visible'), 4200);
  }

  function logDiagnostic(event, detail) {
    fetch('/api/log', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event, detail }),
    }).catch(() => {});
  }

  window.addEventListener('error', (e) => {
    showBanner(`Runtime notice: ${e.message || 'script error'}`);
    logDiagnostic('window_error', e.message || 'unknown');
  });

  /* ------------------------------------------------------------------------
     Theme Sync with Helix & OS (/billskill Rule 6)
     ------------------------------------------------------------------------ */
  function applyTheme(mode) {
    const root = document.documentElement;
    const icon = document.getElementById('theme-icon');
    if (mode === 'dark') {
      root.setAttribute('data-theme', 'dark');
      if (icon) icon.textContent = 'light_mode';
    } else {
      root.removeAttribute('data-theme');
      if (icon) icon.textContent = 'dark_mode';
    }
  }

  function initThemeSync() {
    const saved = localStorage.getItem('djoid-theme');
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    if (saved === 'dark' || saved === 'light') {
      applyTheme(saved);
    } else {
      applyTheme(mq.matches ? 'dark' : 'light');
    }
    mq.addEventListener('change', (e) => {
      if (!localStorage.getItem('djoid-theme')) {
        applyTheme(e.matches ? 'dark' : 'light');
      }
    });
    const toggleBtn = document.getElementById('btn-theme-toggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        const next = isDark ? 'light' : 'dark';
        localStorage.setItem('djoid-theme', next);
        applyTheme(next);
      });
    }
  }

  /* ------------------------------------------------------------------------
     Shared Inline Clear Button Module (/billskill Rule 12)
     ------------------------------------------------------------------------ */
  function initClearableInputs() {
    document.querySelectorAll('.input-clear-btn').forEach((btn) => {
      const targetId = btn.getAttribute('data-clear-for');
      const input = targetId ? document.getElementById(targetId) : null;
      if (!input) return;

      const syncVisibility = () => {
        if (input.value && input.value.length > 0) {
          btn.classList.add('visible');
        } else {
          btn.classList.remove('visible');
        }
      };

      syncVisibility();
      input.addEventListener('input', syncVisibility);

      btn.addEventListener('mousedown', (e) => {
        e.preventDefault();
      });

      btn.addEventListener('click', () => {
        input.value = '';
        syncVisibility();
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.focus();
      });
    });
  }

  /* ------------------------------------------------------------------------
     SVG 30x30px 270-Degree Rotary Encoders (/billskill §20)
     ------------------------------------------------------------------------ */
  function polarToCartesian(cx, cy, r, angleDeg) {
    const rad = ((angleDeg - 90) * Math.PI) / 180.0;
    return {
      x: cx + r * Math.cos(rad),
      y: cy + r * Math.sin(rad),
    };
  }

  function describeArc(cx, cy, r, startAngle, endAngle) {
    if (Math.abs(endAngle - startAngle) < 0.1) {
      const pt = polarToCartesian(cx, cy, r, startAngle);
      return `M ${pt.x.toFixed(2)} ${pt.y.toFixed(2)} A ${r} ${r} 0 0 1 ${(pt.x + 0.01).toFixed(2)} ${pt.y.toFixed(2)}`;
    }
    const start = polarToCartesian(cx, cy, r, startAngle);
    const end = polarToCartesian(cx, cy, r, endAngle);
    const largeArc = endAngle - startAngle <= 180 ? '0' : '1';
    return `M ${start.x.toFixed(2)} ${start.y.toFixed(2)} A ${r} ${r} 0 ${largeArc} 1 ${end.x.toFixed(2)} ${end.y.toFixed(2)}`;
  }

  function updateRotaryVisual(dialEl, rawVal) {
    if (!dialEl) return;
    const min = parseFloat(dialEl.dataset.min || '0');
    const max = parseFloat(dialEl.dataset.max || '100');
    const step = parseFloat(dialEl.dataset.step || '1');
    const unit = dialEl.dataset.unit || '%';
    const param = dialEl.dataset.param;

    const clamped = Math.max(min, Math.min(max, rawVal));
    const rounded = Math.round(clamped / step) * step;
    const pct = max > min ? (rounded - min) / (max - min) : 0;

    const startDeg = -135;
    const endDeg = -135 + pct * 270;

    const trackPath = dialEl.querySelector('.rotary-dial-track-arc');
    const valuePath = dialEl.querySelector('.rotary-dial-value-arc');
    if (trackPath) {
      trackPath.setAttribute('d', describeArc(28, 28, 21, -135, 135));
    }
    if (valuePath) {
      valuePath.setAttribute('d', describeArc(28, 28, 21, startDeg, endDeg));
    }

    dialEl.setAttribute('aria-valuenow', String(rounded));
    state.weights[param] = rounded;

    const row = dialEl.closest('.control-row');
    if (row) {
      const valSpan = row.querySelector('.control-value');
      if (valSpan) {
        const prefix = param === 'bpm_tolerance' ? '±' : '';
        const formatted = step < 1 ? rounded.toFixed(1) : String(Math.round(rounded));
        valSpan.textContent = `${prefix}${formatted}${unit}`;
      }
    }
  }

  function initRotaryEncoders() {
    document.querySelectorAll('.rotary-dial-widget').forEach((dial) => {
      const param = dial.dataset.param;
      const defVal = parseFloat(dial.dataset.default || '50');
      updateRotaryVisual(dial, state.weights[param] ?? defVal);

      let dragging = false;
      let startY = 0;
      let startVal = defVal;

      dial.addEventListener('pointerdown', (e) => {
        dragging = true;
        startY = e.clientY;
        startVal = state.weights[param] ?? defVal;
        dial.setPointerCapture(e.pointerId);
      });

      dial.addEventListener('pointermove', (e) => {
        if (!dragging) return;
        const min = parseFloat(dial.dataset.min || '0');
        const max = parseFloat(dial.dataset.max || '100');
        const deltaY = startY - e.clientY;
        const nextVal = startVal + (deltaY / 110) * (max - min);
        updateRotaryVisual(dial, nextVal);
      });

      const endDrag = () => {
        if (!dragging) return;
        dragging = false;
        requestSolveSet();
      };

      dial.addEventListener('pointerup', endDrag);
      dial.addEventListener('pointercancel', endDrag);

      dial.addEventListener('wheel', (e) => {
        e.preventDefault();
        const step = parseFloat(dial.dataset.step || '1');
        const dir = e.deltaY < 0 ? 1 : -1;
        updateRotaryVisual(dial, (state.weights[param] ?? defVal) + dir * step);
        requestSolveSet();
      }, { passive: false });

      dial.addEventListener('dblclick', () => {
        updateRotaryVisual(dial, defVal);
        requestSolveSet();
      });

      dial.addEventListener('keydown', (e) => {
        const step = parseFloat(dial.dataset.step || '1');
        if (e.key === 'ArrowUp' || e.key === 'ArrowRight') {
          e.preventDefault();
          updateRotaryVisual(dial, (state.weights[param] ?? defVal) + step);
          requestSolveSet();
        } else if (e.key === 'ArrowDown' || e.key === 'ArrowLeft') {
          e.preventDefault();
          updateRotaryVisual(dial, (state.weights[param] ?? defVal) - step);
          requestSolveSet();
        }
      });
    });
  }

  /* ------------------------------------------------------------------------
     Badge Colour Mapping Helper (/billskill Rule 14)
     ------------------------------------------------------------------------ */
  function camelotTone(camelot) {
    const num = parseInt(String(camelot).slice(0, -1), 10) || 8;
    const tones = ['blue', 'teal', 'green', 'yellow', 'orange', 'red', 'purple'];
    return tones[num % tones.length];
  }

  function energyTone(energy) {
    if (energy <= 4) return 'teal';
    if (energy <= 7) return 'blue';
    if (energy <= 8) return 'purple';
    return 'red';
  }

  /* ------------------------------------------------------------------------
     Render Interactive 8-Slot Energy Curve Drawer
     ------------------------------------------------------------------------ */
  function renderEnergyArc() {
    const grid = document.getElementById('arc-bars-grid');
    if (!grid) return;
    grid.innerHTML = '';

    const slots = state.solvedSet.slots || [];
    state.curve.forEach((targetE, idx) => {
      const solvedSlot = slots[idx];
      const actualE = solvedSlot ? solvedSlot.actual_energy : targetE;
      const trk = solvedSlot ? solvedSlot.track : null;

      const col = document.createElement('div');
      col.className = 'arc-slot-col';

      const trackBox = document.createElement('div');
      trackBox.className = 'arc-bar-track';

      const targetBar = document.createElement('div');
      targetBar.className = 'arc-bar-target';
      targetBar.style.height = `${Math.round((targetE / 10) * 100)}%`;

      const actualBar = document.createElement('div');
      actualBar.className = 'arc-bar-actual';
      actualBar.style.height = `${Math.round((actualE / 10) * 100)}%`;

      trackBox.appendChild(targetBar);
      trackBox.appendChild(actualBar);

      const stepBtn = document.createElement('button');
      stepBtn.type = 'button';
      stepBtn.className = 'arc-step-btn';
      stepBtn.id = `btn-arc-slot-${idx + 1}`;
      stepBtn.title = trk ? `Slot ${idx + 1}: ${trk.title} (${trk.camelot}) — click to cycle target energy` : `Slot ${idx + 1}`;
      stepBtn.setAttribute('aria-label', `Adjust slot ${idx + 1} target energy (${targetE})`);
      stepBtn.innerHTML = `<span>S${idx + 1}</span><span>E${targetE}</span>`;

      stepBtn.addEventListener('click', () => {
        const nextE = targetE >= 10 ? 2 : targetE + 1;
        state.curve[idx] = nextE;
        document.querySelectorAll('#preset-tabs .m3-pill-tab').forEach((t) => {
          t.classList.remove('active');
          t.setAttribute('aria-selected', 'false');
        });
        requestSolveSet();
      });

      col.appendChild(trackBox);
      col.appendChild(stepBtn);
      grid.appendChild(col);
    });

    const m = state.solvedSet.metrics || {};
    const scoreEl = document.getElementById('metric-set-score');
    const harmEl = document.getElementById('metric-harmonic-flow');
    const bpmEl = document.getElementById('metric-bpm-jump');
    const durEl = document.getElementById('metric-duration');
    if (scoreEl) scoreEl.textContent = `Set compatibility: ${m.set_score ?? 92.0}%`;
    if (harmEl) harmEl.textContent = `Harmonic flow: ${m.harmonic_flow ?? 95.0}%`;
    if (bpmEl) bpmEl.textContent = `Max tempo step: ${m.max_bpm_jump ?? 2.0} BPM`;
    if (durEl) durEl.textContent = `Runtime: ${m.total_duration_formatted || '48m 10s'}`;
  }

  /* ------------------------------------------------------------------------
     Render 2D Vibe Map & A* Bridge Pathfinder
     ------------------------------------------------------------------------ */
  function renderVibeMap() {
    const svg = document.getElementById('vibe-map-svg');
    if (!svg) return;
    svg.innerHTML = '';

    const width = 520;
    const height = 260;
    const padX = 36;
    const padY = 26;

    const byId = {};
    state.tracks.forEach((t) => {
      byId[t.id] = {
        ...t,
        cx: padX + t.vibe_x * (width - padX * 2),
        cy: height - padY - t.vibe_y * (height - padY * 2),
      };
    });

    const bridgeIds = new Set(
      state.bridgeResult && state.bridgeResult.path
        ? state.bridgeResult.path.map((t) => t.id)
        : []
    );
    const bridgePairs = new Set();
    if (state.bridgeResult && state.bridgeResult.path) {
      const p = state.bridgeResult.path;
      for (let i = 0; i < p.length - 1; i++) {
        bridgePairs.add(`${p[i].id}::${p[i + 1].id}`);
        bridgePairs.add(`${p[i + 1].id}::${p[i].id}`);
      }
    }

    // Draw harmonic graph edges
    state.edges.forEach((edge) => {
      const a = byId[edge.source];
      const b = byId[edge.target];
      if (!a || !b) return;
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', a.cx.toFixed(1));
      line.setAttribute('y1', a.cy.toFixed(1));
      line.setAttribute('x2', b.cx.toFixed(1));
      line.setAttribute('y2', b.cy.toFixed(1));
      const isBridgeEdge = bridgePairs.has(`${edge.source}::${edge.target}`);
      line.setAttribute('class', isBridgeEdge ? 'vibe-edge bridge-active' : 'vibe-edge');
      svg.appendChild(line);
    });

    // Also draw explicit A* bridge segments even if they span wider hops
    if (state.bridgeResult && state.bridgeResult.path) {
      const p = state.bridgeResult.path;
      for (let i = 0; i < p.length - 1; i++) {
        const a = byId[p[i].id];
        const b = byId[p[i + 1].id];
        if (!a || !b) continue;
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', a.cx.toFixed(1));
        line.setAttribute('y1', a.cy.toFixed(1));
        line.setAttribute('x2', b.cx.toFixed(1));
        line.setAttribute('y2', b.cy.toFixed(1));
        line.setAttribute('class', 'vibe-edge bridge-active');
        svg.appendChild(line);
      }
    }

    const setTrackIds = new Set((state.solvedSet.slots || []).map((s) => s.track.id));

    // Draw track nodes
    Object.values(byId).forEach((trk) => {
      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      let cls = 'vibe-node';
      if (bridgeIds.has(trk.id)) cls += ' bridge-node';
      else if (setTrackIds.has(trk.id)) cls += ' in-set';
      g.setAttribute('class', cls);

      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', trk.cx.toFixed(1));
      circle.setAttribute('cy', trk.cy.toFixed(1));
      circle.setAttribute('r', bridgeIds.has(trk.id) ? '8.5' : setTrackIds.has(trk.id) ? '7' : '5.5');
      circle.setAttribute('class', 'vibe-node-circle');

      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      label.setAttribute('x', (trk.cx + 9).toFixed(1));
      label.setAttribute('y', (trk.cy + 3.5).toFixed(1));
      label.setAttribute('class', 'vibe-node-label');
      label.textContent = state.vibeColorMode === 'energy' ? `E${trk.energy}` : trk.camelot;

      g.appendChild(circle);
      g.appendChild(label);

      g.addEventListener('click', () => {
        const targetSel = document.getElementById('select-bridge-target');
        if (targetSel) {
          targetSel.value = trk.id;
          requestBridgePath();
        }
      });

      svg.appendChild(g);
    });
  }

  function populateBridgeSelects() {
    const startSel = document.getElementById('select-bridge-start');
    const targetSel = document.getElementById('select-bridge-target');
    if (!startSel || !targetSel) return;

    const prevStart = startSel.value || (state.tracks[2] && state.tracks[2].id);
    const prevTarget = targetSel.value || (state.tracks[18] && state.tracks[18].id);

    const html = state.tracks
      .map((t) => `<option value="${t.id}">${t.camelot} • ${t.bpm} BPM — ${t.title}</option>`)
      .join('');
    startSel.innerHTML = html;
    targetSel.innerHTML = html;

    if (prevStart) startSel.value = prevStart;
    if (prevTarget) targetSel.value = prevTarget;
  }

  function renderBridgeResult() {
    const box = document.getElementById('bridge-result-box');
    if (!box || !state.bridgeResult) return;

    const path = state.bridgeResult.path || [];
    const chainBadges = path
      .map((t, idx) => {
        const tone = idx === 0 ? 'blue' : idx === path.length - 1 ? 'purple' : 'green';
        const role = idx === 0 ? 'Start' : idx === path.length - 1 ? 'Target' : `Bridge ${idx}`;
        return `<span class="badge badge-${tone}">${role}: ${t.title} (${t.camelot} • ${t.bpm} BPM)</span>`;
      })
      .join('');

    box.innerHTML = `
      <div class="badge-row">${chainBadges}</div>
      <div>${state.bridgeResult.summary || ''}</div>
    `;
  }

  /* ------------------------------------------------------------------------
     Render Solved Set Sequence & AI Transition Coaching
     ------------------------------------------------------------------------ */
  function renderSetTimeline() {
    const list = document.getElementById('set-timeline-list');
    if (!list) return;
    list.innerHTML = '';

    const slots = state.solvedSet.slots || [];
    slots.forEach((slotObj, idx) => {
      const trk = slotObj.track;
      const trans = slotObj.transition_from_prev;
      const card = document.createElement('div');
      card.className = 'set-slot-card' + (idx === state.previewSlotIndex ? ' active-preview' : '');

      const camTone = camelotTone(trk.camelot);
      const eTone = energyTone(trk.energy);

      let coachingHtml = '';
      if (trans) {
        coachingHtml = `
          <div class="coaching-callout">
            <span class="material-symbols-outlined">auto_awesome</span>
            <div>
              <strong>Transition ${idx}→${idx + 1} (${trans.overall}% • ${trans.harmonic_label}):</strong>
              ${trans.coaching}
            </div>
          </div>
        `;
      }

      const canPreviewPair = idx > 0;
      const previewBtnHtml = canPreviewPair
        ? `<button type="button" class="btn-outlined" id="btn-preview-slot-${idx}">
             <span class="material-symbols-outlined">headphones</span>
             Load deck pair
           </button>`
        : `<span class="badge badge-green">Opening anchor</span>`;

      card.innerHTML = `
        <div class="set-slot-main">
          <div class="slot-identity">
            <span class="slot-index-pill">${slotObj.slot}</span>
            <div class="slot-title-block">
              <span class="slot-track-title">${trk.title}</span>
              <span class="slot-track-artist">${trk.artist} • ${trk.genre}</span>
            </div>
          </div>
          <div class="badge-row">
            <span class="badge badge-${camTone}">${trk.camelot} (${trk.musical_key})</span>
            <span class="badge badge-blue">${trk.bpm.toFixed(1)} BPM</span>
            <span class="badge badge-${eTone}">Energy ${trk.energy}/10</span>
            ${previewBtnHtml}
          </div>
        </div>
        ${coachingHtml}
      `;

      list.appendChild(card);

      if (canPreviewPair) {
        const btn = document.getElementById(`btn-preview-slot-${idx}`);
        if (btn) {
          btn.addEventListener('click', () => {
            state.previewSlotIndex = idx;
            renderSetTimeline();
            renderDualDeckPreviewer();
          });
        }
      }
    });
  }

  /* ------------------------------------------------------------------------
     Render Dual-Deck Multi-Band Waveform & Hot Cue Previewer
     ------------------------------------------------------------------------ */
  function drawDeckWaveform(svgId, track, playheadPct) {
    const svg = document.getElementById(svgId);
    if (!svg || !track) return;
    svg.innerHTML = '';

    const wf = track.waveform || { low: [], mid: [], high: [] };
    const bins = (wf.low && wf.low.length) || 64;
    const width = 520;
    const height = 76;
    const barW = width / bins;

    for (let i = 0; i < bins; i++) {
      const l = wf.low[i] || 0.3;
      const m = wf.mid[i] || 0.3;
      const h = wf.high[i] || 0.2;
      const x = i * barW + 1;

      const lH = Math.max(4, l * 34);
      const mH = Math.max(3, m * 22);
      const hH = Math.max(2, h * 14);

      const rectL = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rectL.setAttribute('x', x.toFixed(1));
      rectL.setAttribute('y', (height - lH).toFixed(1));
      rectL.setAttribute('width', Math.max(2, barW - 2).toFixed(1));
      rectL.setAttribute('height', lH.toFixed(1));
      rectL.setAttribute('class', 'wf-bar-low');
      svg.appendChild(rectL);

      const rectM = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rectM.setAttribute('x', x.toFixed(1));
      rectM.setAttribute('y', (height - lH - mH).toFixed(1));
      rectM.setAttribute('width', Math.max(2, barW - 2).toFixed(1));
      rectM.setAttribute('height', mH.toFixed(1));
      rectM.setAttribute('class', 'wf-bar-mid');
      svg.appendChild(rectM);

      const rectH = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rectH.setAttribute('x', x.toFixed(1));
      rectH.setAttribute('y', Math.max(2, height - lH - mH - hH).toFixed(1));
      rectH.setAttribute('width', Math.max(2, barW - 2).toFixed(1));
      rectH.setAttribute('height', hH.toFixed(1));
      rectH.setAttribute('class', 'wf-bar-high');
      svg.appendChild(rectH);
    }

    if (typeof playheadPct === 'number' && playheadPct >= 0) {
      const px = Math.min(width - 2, Math.max(2, playheadPct * width));
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', px.toFixed(1));
      line.setAttribute('y1', '0');
      line.setAttribute('x2', px.toFixed(1));
      line.setAttribute('y2', String(height));
      line.setAttribute('class', 'wf-playhead');
      svg.appendChild(line);
    }
  }

  function formatSec(sec) {
    const s = Math.max(0, Math.round(sec));
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  }

  function renderDeckCues(containerId, track, deckTag) {
    const container = document.getElementById(containerId);
    if (!container || !track) return;
    container.innerHTML = '';

    (track.cues || []).forEach((cue) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `cue-trigger-btn badge-${cue.tone || 'blue'}`;
      btn.id = `btn-cue-${deckTag}-${cue.slot}`;
      btn.textContent = `${cue.slot}: ${cue.section} (${formatSec(cue.start)})`;
      btn.addEventListener('click', () => {
        if (window.DjoidAudio) {
          window.DjoidAudio.playCuePreview(track, cue.slot, () => {
            updatePlayButtonLabel(false);
          });
          updatePlayButtonLabel(true, `Cue ${cue.slot}`);
        }
      });
      container.appendChild(btn);
    });
  }

  function getPreviewPair() {
    const slots = state.solvedSet.slots || [];
    const idx = Math.max(1, Math.min(slots.length - 1, state.previewSlotIndex));
    const trackA = (slots[idx - 1] && slots[idx - 1].track) || state.tracks[0];
    const trackB = (slots[idx] && slots[idx].track) || state.tracks[1];
    return { trackA, trackB };
  }

  function renderDualDeckPreviewer(playheadA = 0.82, playheadB = 0.08) {
    const { trackA, trackB } = getPreviewPair();
    if (!trackA || !trackB) return;

    const titleA = document.getElementById('deck-a-title');
    const metaA = document.getElementById('deck-a-meta');
    const titleB = document.getElementById('deck-b-title');
    const metaB = document.getElementById('deck-b-meta');

    if (titleA) titleA.textContent = `${trackA.title} — ${trackA.artist}`;
    if (metaA) metaA.textContent = `${trackA.camelot} • ${trackA.bpm.toFixed(1)} BPM • E${trackA.energy}`;
    if (titleB) titleB.textContent = `${trackB.title} — ${trackB.artist}`;
    if (metaB) metaB.textContent = `${trackB.camelot} • ${trackB.bpm.toFixed(1)} BPM • E${trackB.energy}`;

    drawDeckWaveform('waveform-svg-a', trackA, playheadA);
    drawDeckWaveform('waveform-svg-b', trackB, playheadB);
    renderDeckCues('deck-a-cues', trackA, 'a');
    renderDeckCues('deck-b-cues', trackB, 'b');
  }

  function updatePlayButtonLabel(playing, customLabel) {
    const icon = document.getElementById('icon-play-transition');
    const label = document.getElementById('label-play-transition');
    if (!icon || !label) return;
    if (playing) {
      icon.textContent = 'stop';
      label.textContent = customLabel || 'Stop audition';
    } else {
      icon.textContent = 'play_arrow';
      label.textContent = 'Audition mix';
    }
  }

  /* ------------------------------------------------------------------------
     Render Rekordbox XML Preview & Full 24-Track Library Table
     ------------------------------------------------------------------------ */
  function renderXmlPreview() {
    const pre = document.getElementById('xml-preview-code');
    if (!pre) return;
    pre.textContent = state.xmlPreview || '';
  }

  function renderLibraryTable() {
    const tbody = document.getElementById('library-table-body');
    const countBadge = document.getElementById('library-count-badge');
    if (countBadge) {
      countBadge.textContent = `${state.tracks.length} tracks ready`;
    }
    if (!tbody) return;
    tbody.innerHTML = '';

    const q = state.searchQuery.trim().toLowerCase();
    const filtered = state.tracks.filter((t) => {
      if (q) {
        const hay = `${t.title} ${t.artist} ${t.genre} ${t.camelot} ${t.musical_key}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (state.energyFilter === 'warmup' && t.energy > 5) return false;
      if (state.energyFilter === 'groovy' && (t.energy < 6 || t.energy > 8)) return false;
      if (state.energyFilter === 'peak' && t.energy < 9) return false;
      return true;
    });

    filtered.forEach((trk) => {
      const tr = document.createElement('tr');
      const camTone = camelotTone(trk.camelot);
      const eTone = energyTone(trk.energy);
      const cueSummary = (trk.cues || [])
        .map((c) => `<span class="badge badge-${c.tone}">${c.slot} ${formatSec(c.start)}</span>`)
        .join(' ');

      tr.innerHTML = `
        <td>${trk.track_number}</td>
        <td>
          <strong>${trk.title}</strong><br>
          <span>${trk.artist}</span>
        </td>
        <td>${trk.genre}</td>
        <td><span class="badge badge-${camTone}">${trk.camelot} (${trk.musical_key})</span></td>
        <td>${trk.bpm.toFixed(1)}</td>
        <td><span class="badge badge-${eTone}">E${trk.energy} (${trk.lufs} LUFS)</span></td>
        <td><div class="badge-row">${cueSummary}</div></td>
        <td>
          <button type="button" class="btn-outlined" id="btn-seed-${trk.id}">
            <span class="material-symbols-outlined">play_circle</span>
            Lead set
          </button>
        </td>
      `;
      tbody.appendChild(tr);

      const seedBtn = document.getElementById(`btn-seed-${trk.id}`);
      if (seedBtn) {
        seedBtn.addEventListener('click', () => {
          state.seedTrackId = trk.id;
          state.curve[0] = trk.energy;
          requestSolveSet();
        });
      }
    });
  }

  /* ------------------------------------------------------------------------
     API Calls: Solve Set, Find A* Bridge, Import XML / Audio, Export
     ------------------------------------------------------------------------ */
  async function requestSolveSet() {
    const plInput = document.getElementById('input-playlist-name');
    const playlistName = (plInput && plInput.value.trim()) || 'DJOID Studio AI Set';
    const res = await fetch('/api/solve-set', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        curve: state.curve,
        harmonic_strictness: state.weights.harmonic_strictness,
        bpm_tolerance: state.weights.bpm_tolerance,
        energy_adherence: state.weights.energy_adherence,
        seed_track_id: state.seedTrackId,
        playlist_name: playlistName,
      }),
    });
    const data = await res.json();
    state.solvedSet = data.solved_set || state.solvedSet;
    state.xmlPreview = data.xml_preview || state.xmlPreview;
    state.seedTrackId = null;

    renderEnergyArc();
    renderVibeMap();
    renderSetTimeline();
    renderDualDeckPreviewer();
    renderXmlPreview();
  }

  async function requestBridgePath() {
    const startSel = document.getElementById('select-bridge-start');
    const targetSel = document.getElementById('select-bridge-target');
    if (!startSel || !targetSel) return;
    const res = await fetch('/api/bridge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_id: startSel.value,
        target_id: targetSel.value,
        bpm_tolerance: state.weights.bpm_tolerance,
      }),
    });
    state.bridgeResult = await res.json();
    renderBridgeResult();
    renderVibeMap();
  }

  async function importRekordboxXmlText(xmlString) {
    const res = await fetch('/api/import-xml', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ xml: xmlString }),
    });
    const data = await res.json();
    if (data.error) {
      showBanner(data.error);
      return;
    }
    state.tracks = data.tracks || state.tracks;
    state.edges = data.edges || state.edges;
    state.solvedSet = data.solved_set || state.solvedSet;
    state.xmlPreview = data.xml_preview || state.xmlPreview;
    populateBridgeSelects();
    renderAll();
  }

  /* ------------------------------------------------------------------------
     Modal Controls (Click outside, Escape key, Explicit Close Button)
     ------------------------------------------------------------------------ */
  function openGuideModal() {
    const modal = document.getElementById('modal-rekordbox-guide');
    if (modal) modal.classList.add('open');
  }

  function closeGuideModal() {
    const modal = document.getElementById('modal-rekordbox-guide');
    if (modal) modal.classList.remove('open');
  }

  function triggerDownload(url) {
    const a = document.createElement('a');
    a.href = url;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  function bindEvents() {
    // Preset tabs
    document.querySelectorAll('#preset-tabs .m3-pill-tab').forEach((tab) => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('#preset-tabs .m3-pill-tab').forEach((t) => {
          t.classList.remove('active');
          t.setAttribute('aria-selected', 'false');
        });
        tab.classList.add('active');
        tab.setAttribute('aria-selected', 'true');
        const key = tab.dataset.preset;
        if (state.presets[key] && state.presets[key].curve) {
          state.curve = [...state.presets[key].curve];
          requestSolveSet();
        }
      });
    });

    // Vibe map color mode tabs
    document.querySelectorAll('#vibe-mode-tabs .m3-pill-tab').forEach((tab) => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('#vibe-mode-tabs .m3-pill-tab').forEach((t) => {
          t.classList.remove('active');
          t.setAttribute('aria-selected', 'false');
        });
        tab.classList.add('active');
        tab.setAttribute('aria-selected', 'true');
        state.vibeColorMode = tab.dataset.mode || 'camelot';
        renderVibeMap();
      });
    });

    // Bridge finder
    const btnBridge = document.getElementById('btn-find-bridge');
    if (btnBridge) btnBridge.addEventListener('click', requestBridgePath);

    // Dual-deck synth transition audition
    const btnPlayTrans = document.getElementById('btn-play-transition');
    if (btnPlayTrans) {
      btnPlayTrans.addEventListener('click', () => {
        if (!window.DjoidAudio) return;
        if (window.DjoidAudio.isPlaying()) {
          window.DjoidAudio.stopPreview(() => {
            updatePlayButtonLabel(false);
            renderDualDeckPreviewer(0.82, 0.08);
          });
          return;
        }
        const { trackA, trackB } = getPreviewPair();
        updatePlayButtonLabel(true, 'Playing mix...');
        window.DjoidAudio.playTransitionPreview(
          trackA,
          trackB,
          (tickInfo) => {
            const pA = 0.80 + tickInfo.progress * 0.16;
            const pB = 0.08 + tickInfo.progress * 0.24;
            renderDualDeckPreviewer(pA, pB);
            updatePlayButtonLabel(
              true,
              tickInfo.bassSwapped ? `Bass swapped (${tickInfo.beat}/16)` : `Blending (${tickInfo.beat}/16)`
            );
          },
          () => {
            updatePlayButtonLabel(false);
            renderDualDeckPreviewer(0.82, 0.08);
          }
        );
      });
    }

    // Audio & XML uploads
    const btnAudio = document.getElementById('btn-upload-audio');
    const inpAudio = document.getElementById('input-audio-file');
    if (btnAudio && inpAudio) {
      btnAudio.addEventListener('click', () => inpAudio.click());
      inpAudio.addEventListener('change', async () => {
        const file = inpAudio.files && inpAudio.files[0];
        if (!file || !window.DjoidAudio) return;
        const features = await window.DjoidAudio.analyzeAudioFile(file);
        const res = await fetch('/api/analyze-audio', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(features),
        });
        const data = await res.json();
        state.tracks = data.tracks || state.tracks;
        state.edges = data.edges || state.edges;
        state.solvedSet = data.solved_set || state.solvedSet;
        state.xmlPreview = data.xml_preview || state.xmlPreview;
        populateBridgeSelects();
        renderAll();
      });
    }

    const btnXml = document.getElementById('btn-upload-xml');
    const inpXml = document.getElementById('input-xml-file');
    if (btnXml && inpXml) {
      btnXml.addEventListener('click', () => inpXml.click());
      inpXml.addEventListener('change', async () => {
        const file = inpXml.files && inpXml.files[0];
        if (!file) return;
        const text = await file.text();
        await importRekordboxXmlText(text);
      });
    }

    const btnSampleXml = document.getElementById('btn-import-sample-xml');
    if (btnSampleXml) {
      btnSampleXml.addEventListener('click', () => importRekordboxXmlText(''));
    }

    // Export XML & M3U8
    const exportXmlAction = () => {
      const plInput = document.getElementById('input-playlist-name');
      const name = encodeURIComponent((plInput && plInput.value.trim()) || 'DJOID Studio AI Set');
      const ids = (state.solvedSet.slots || []).map((s) => s.track.id).join(',');
      triggerDownload(`/api/export/rekordbox.xml?name=${name}&ids=${encodeURIComponent(ids)}&download=1`);
    };

    const btnExportXml = document.getElementById('btn-export-xml');
    if (btnExportXml) btnExportXml.addEventListener('click', exportXmlAction);

    const btnModalDl = document.getElementById('btn-modal-download-xml');
    if (btnModalDl) btnModalDl.addEventListener('click', exportXmlAction);

    const btnExportM3u = document.getElementById('btn-export-m3u8');
    if (btnExportM3u) {
      btnExportM3u.addEventListener('click', () => {
        const plInput = document.getElementById('input-playlist-name');
        const name = encodeURIComponent((plInput && plInput.value.trim()) || 'DJOID Studio AI Set');
        const ids = (state.solvedSet.slots || []).map((s) => s.track.id).join(',');
        triggerDownload(`/api/export/playlist.m3u8?name=${name}&ids=${encodeURIComponent(ids)}`);
      });
    }

    const btnCopyXml = document.getElementById('btn-copy-xml');
    if (btnCopyXml) {
      btnCopyXml.addEventListener('click', () => {
        if (navigator.clipboard && state.xmlPreview) {
          navigator.clipboard.writeText(state.xmlPreview).catch(() => {});
        }
        btnCopyXml.innerHTML = '<span class="material-symbols-outlined">check</span>Copied XML';
        setTimeout(() => {
          btnCopyXml.innerHTML = '<span class="material-symbols-outlined">content_copy</span>Copy XML';
        }, 1800);
      });
    }

    // Playlist name live update
    const plInput = document.getElementById('input-playlist-name');
    if (plInput) {
      plInput.addEventListener('change', () => requestSolveSet());
    }

    // Library search & energy tier filter
    const searchInput = document.getElementById('input-library-search');
    if (searchInput) {
      searchInput.addEventListener('input', () => {
        state.searchQuery = searchInput.value || '';
        renderLibraryTable();
      });
    }

    const filterSel = document.getElementById('select-library-filter');
    if (filterSel) {
      filterSel.addEventListener('change', () => {
        state.energyFilter = filterSel.value || 'all';
        renderLibraryTable();
      });
    }

    // Modal triggers & mandatory dismissal rules (/billskill Rule 11)
    const btnGuide = document.getElementById('btn-rekordbox-guide');
    const btnGuideInline = document.getElementById('btn-open-guide-inline');
    const btnCloseGuide = document.getElementById('btn-close-guide-modal');
    const btnModalDone = document.getElementById('btn-modal-done');
    const modalBackdrop = document.getElementById('modal-rekordbox-guide');

    if (btnGuide) btnGuide.addEventListener('click', openGuideModal);
    if (btnGuideInline) btnGuideInline.addEventListener('click', openGuideModal);
    if (btnCloseGuide) btnCloseGuide.addEventListener('click', closeGuideModal);
    if (btnModalDone) btnModalDone.addEventListener('click', closeGuideModal);

    if (modalBackdrop) {
      modalBackdrop.addEventListener('click', (e) => {
        if (e.target === modalBackdrop) closeGuideModal();
      });
    }

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeGuideModal();
      }
    });
  }

  function renderAll() {
    renderEnergyArc();
    renderVibeMap();
    renderBridgeResult();
    renderSetTimeline();
    renderDualDeckPreviewer();
    renderXmlPreview();
    renderLibraryTable();
  }

  async function boot() {
    initThemeSync();
    initClearableInputs();
    bindEvents();

    const res = await fetch('/api/state');
    const data = await res.json();
    state.appBuild = data.app_build || state.appBuild;
    state.tracks = data.tracks || [];
    state.edges = data.edges || [];
    state.presets = data.presets || {};
    state.curve = data.curve || state.curve;
    state.weights = data.weights || state.weights;
    state.solvedSet = data.solved_set || { slots: [], metrics: {} };
    state.bridgeResult = data.default_bridge || null;
    state.xmlPreview = data.xml_preview || '';

    initRotaryEncoders();
    populateBridgeSelects();
    renderAll();
    logDiagnostic('client_boot_ok', `tracks=${state.tracks.length}`);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();

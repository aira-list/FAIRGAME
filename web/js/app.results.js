// Results dashboard + rendering page methods — split out of app.js and merged onto the
// Alpine component by fairgame() in app.js (see the merge there).
window.__fgResults = {
      // ---- Results page state -----
      // (The runs list itself and the open run live on the core component
      // in app.js — core helpers like filteredRuns/openRun use them too.)
      results: { tab: 'charts', configFilter: '', page: 1, perPage: 10, tablePage: 1, tablePerPage: 5 },
      compare: { selected: [], open: false },

      _charts: {},   // Chart.js instances, keyed by canvas id

      // ---- Results charts -------------------------------------------

      renderCharts() {
        // Switch the tab first; the dashboard container lives inside
        // x-show=...charts and is display:none until then. Chart.js cannot
        // measure a hidden canvas, so wait for the next frame after the tab
        // is visible before building any chart instances.
        this.results.tab = 'charts';
        if (!this.activeRun || !this.activeRun.id) return;
        this.$nextTick(() => {
          requestAnimationFrame(() => this._renderDashboard());
        });
      },

      // Directed interaction topology as inline SVG (nodes on a circle,
      // arrows coloured by level: blue = sees plays, green = also hears messages).
      _dashGraphSvg(chart) {
        const nodes = chart.nodes || [], edges = chart.edges || [];
        const size = 300, cx = size / 2, cy = size / 2 - 6, R = size * 0.30, r = 26;
        const pos = {};
        nodes.forEach((nd, i) => {
          const a = -Math.PI / 2 + i * 2 * Math.PI / Math.max(nodes.length, 1);
          pos[nd.id] = [cx + R * Math.cos(a), cy + R * Math.sin(a)];
        });
        let s = `<svg width="100%" viewBox="0 0 ${size} ${size}" class="select-none max-w-full">`;
        s += '<defs>'
          + '<marker id="dg-see" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#0284c7"/></marker>'
          + '<marker id="dg-talk" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#059669"/></marker>'
          + '</defs>';
        for (const e of edges) {
          const a = pos[e.from], b = pos[e.to];
          if (!a || !b) continue;
          const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1;
          const ux = dx / L, uy = dy / L, ox = -uy * 7, oy = ux * 7;  // offset so opposite edges don't overlap
          const x1 = a[0] + ux * r + ox, y1 = a[1] + uy * r + oy;
          const x2 = b[0] - ux * r + ox, y2 = b[1] - uy * r + oy;
          const talk = e.level === 'talk';
          s += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${talk ? '#059669' : '#0284c7'}" stroke-width="2" marker-end="url(#${talk ? 'dg-talk' : 'dg-see'})"/>`;
        }
        for (const nd of nodes) {
          const [x, y] = pos[nd.id];
          s += `<circle cx="${x}" cy="${y}" r="${r}" fill="#eff6ff" stroke="#2563eb" stroke-width="1.5"/>`
            + `<text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="middle" font-size="11" fill="#1e3a8a">${escapeHtml(nd.id)}</text>`;
        }
        s += `<text x="${cx}" y="${size - 6}" text-anchor="middle" font-size="10" fill="#64748b">blue → sees plays · green → also hears messages</text>`;
        return s + '</svg>';
      },

      async _renderDashboard() {
        const root = document.getElementById('dash-root');
        if (!root) return;
        root.innerHTML = '<div class="text-sm text-slate-400 p-4">Loading charts…</div>';
        let spec;
        try {
          spec = await this.api(`/api/runs/${this.activeRun.id}/dashboard`);
        } catch (e) {
          root.innerHTML = '<div class="text-sm text-rose-500 p-4">Could not load charts for this run.</div>';
          return;
        }
        this._renderSpecInto(root, spec, 'dash', 'This run has no chartable results.');
      },

      toggleCompare(id) {
        const i = this.compare.selected.indexOf(id);
        if (i >= 0) this.compare.selected.splice(i, 1);
        else this.compare.selected.push(id);
      },

      runCompare() {
        this.activeRun = null;       // single-run and compare are separate modes
        this.compare.open = true;
        this.$nextTick(() => requestAnimationFrame(async () => {
          const root = document.getElementById('compare-root');
          if (!root) return;
          root.innerHTML = '<div class="text-sm text-slate-400 p-4">Loading comparison…</div>';
          let spec;
          try {
            spec = await this.api('/api/compare', {
              method: 'POST', body: JSON.stringify({ run_ids: this.compare.selected }),
            });
          } catch (e) {
            root.innerHTML = '<div class="text-sm text-rose-500 p-4">Could not load comparison.</div>';
            return;
          }
          this._renderSpecInto(root, spec, 'cmp',
            'No comparable results (need runs with recorded models).');
        }));
      },

      // Render a chart-spec ({sections:[{title,charts:[…]}]}) into an element.
      // Reused by the per-run dashboard and the cross-model compare panel.
      _renderSpecInto(root, spec, prefix, emptyMsg) {
        // Tear down only the charts belonging to this panel (by id prefix).
        for (const id of Object.keys(this._charts)) {
          if (!id.startsWith(prefix + '-')) continue;
          try { this._charts[id].destroy(); } catch {}
          delete this._charts[id];
        }
        const sections = (spec && spec.sections) || [];
        root.innerHTML = '';
        if (!sections.length) {
          root.innerHTML = `<div class="text-sm text-slate-500 p-4">${emptyMsg || 'Nothing to show.'}</div>`;
          return;
        }

        const palette = ['#2563eb', '#16a34a', '#dc2626', '#9333ea', '#d97706', '#0891b2', '#db2777'];
        const pending = [];   // charts to instantiate after the DOM is attached
        let n = 0;

        for (const section of sections) {
          const sec = document.createElement('section');
          sec.className = 'mb-8';
          const h = document.createElement('h3');
          h.className = 'text-sm font-semibold mb-3 text-slate-700 border-b pb-1';
          h.textContent = section.title;
          sec.appendChild(h);
          const grid = document.createElement('div');
          grid.className = 'grid md:grid-cols-2 gap-6';
          sec.appendChild(grid);
          root.appendChild(sec);   // attach before building charts so canvases are measurable

          for (const chart of section.charts) {
            const cell = document.createElement('div');
            if (chart.kind === 'graph') cell.className = 'md:col-span-2';
            const title = document.createElement('h4');
            title.className = 'text-xs font-medium mb-1 text-slate-600';
            title.textContent = chart.title;
            cell.appendChild(title);
            if (chart.description) {
              const d = document.createElement('div');
              d.className = 'text-[11px] text-slate-400 mb-2';
              d.textContent = chart.description;
              cell.appendChild(d);
            }
            const box = document.createElement('div');
            box.className = 'border rounded-md p-2 relative';
            cell.appendChild(box);
            grid.appendChild(cell);

            if (chart.kind === 'graph') {
              box.innerHTML = this._dashGraphSvg(chart);
              continue;
            }
            box.style.height = chart.kind === 'radar' ? '340px' : '280px';
            if (chart.kind === 'radar') cell.className = 'md:col-span-2';
            const canvas = document.createElement('canvas');
            const cid = `${prefix}-chart-${n++}`;
            canvas.id = cid;
            box.appendChild(canvas);
            const soft = chart.kind === 'line' || chart.kind === 'radar';
            const datasets = (chart.datasets || []).map((ds, i) => {
              const color = palette[i % palette.length];
              return {
                label: ds.label,
                data: ds.data,
                borderColor: color,
                backgroundColor: soft ? color + '33' : color,
                pointBackgroundColor: color,
                tension: 0.2,
              };
            });
            // Radar uses a radial axis; give it a fixed [0,1] scale since its
            // metrics are normalised. Other charts auto-scale.
            const scaleOpts = chart.kind === 'radar'
              ? { r: { suggestedMin: 0, suggestedMax: 1 } }
              : undefined;
            pending.push([cid, chart.kind, { labels: chart.labels || [], datasets }, scaleOpts]);
          }
        }
        for (const [cid, kind, data, scaleOpts] of pending) this._mkChart(cid, kind, data, scaleOpts);
      },

      _mkChart(canvasId, type, data, scaleOpts) {
        const el = document.getElementById(canvasId);
        if (!el) return;
        if (this._charts[canvasId]) {
          try { this._charts[canvasId].destroy(); } catch {}
          delete this._charts[canvasId];
        }
        if (data.datasets.length === 0) {
          // No data for this metric in this run (e.g. equilibrium metrics or
          // belief Brier scores were not recorded). Draw an explanatory
          // placeholder rather than leaving a blank box that reads as broken.
          const ctx = el.getContext('2d');
          if (ctx) {
            const w = el.clientWidth || el.width || 300;
            const h = el.clientHeight || el.height || 200;
            el.width = w; el.height = h;
            ctx.clearRect(0, 0, w, h);
            ctx.fillStyle = '#94a3b8';
            ctx.font = '13px system-ui, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('No data for this metric in this run', w / 2, h / 2);
          }
          return;
        }
        const options = {
          responsive: true,
          // Without a fixed aspect ratio Chart.js will keep its own
          // intrinsic 2:1 from the first measurement, which (when the
          // canvas was briefly hidden) leads to a stuck small chart.
          maintainAspectRatio: false,
          scales: scaleOpts,
          plugins: {
            // A legend only helps when there are multiple series to tell apart;
            // for a single-series (one-colour) chart it's just noise.
            legend: {
              display: data.datasets.length > 1,
              position: 'bottom',
              labels: { boxWidth: 12 },
            },
          },
        };
        this._charts[canvasId] = new Chart(el, { type, data, options });
      },

      // ---- Rendering helpers ----------------------------------------

      renderTable(rows) {
        if (!rows || rows.length === 0) return '<p class="text-slate-500 italic">No data.</p>';
        const cols = Object.keys(rows[0]);
        // Column names and cell values are run/CSV data (operator/LLM
        // controlled) rendered via x-html — escape both to prevent XSS.
        const head = cols.map(c => `<th class="text-left px-2 py-1.5 bg-slate-100 border-b text-[10px] font-semibold text-slate-700 whitespace-nowrap">${escapeHtml(c)}</th>`).join('');
        const body = rows.map(r =>
          '<tr>' + cols.map(c => `<td class="px-2 py-1 text-[11px] border-b text-slate-700">${escapeHtml(this.fmt(r[c]))}</td>`).join('') + '</tr>'
        ).join('');
        return `<div class="overflow-auto rounded-md border border-slate-200">
          <table class="min-w-full text-[11px]"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>
        </div>`;
      },

      fmt(v) {
        if (v === null || v === undefined) return '—';
        if (typeof v === 'number') return Number.isInteger(v) ? v : v.toFixed(3);
        if (typeof v === 'object') return JSON.stringify(v);
        const s = String(v);
        return s.length > 60 ? s.slice(0, 57) + '…' : s;
      },

      downloadJson(obj, filename) {
        const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filename; a.click();
        URL.revokeObjectURL(url);
      },};

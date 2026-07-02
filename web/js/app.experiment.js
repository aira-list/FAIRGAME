// Experiment page methods — split out of app.js and merged onto the
// Alpine component by fairgame() in app.js (see the merge there).
window.__fgExperiment = {
      // ---- Experiment page state -----
      experiment: {
        selectedConfig: '',
        nIterations: 1,
        running: false, error: '', results: [],
        // Live progress, driven by the SSE run-batch/stream endpoint.
        progress: { active: false, completed: 0, total: 0, label: '' },
      },

      // ---- Experiment -----------------------------------------------

      configurationsByGameType() {
        // {game_type_id: [config, …]} — games first in the order games came back
        // from /api/game-types so the picker is stable across reloads.
        const groups = {};
        for (const gt of this.gameTypes) {
          const inGroup = this.configurations.filter(c => c.game_type_id === gt.id);
          if (inGroup.length) groups[gt.id] = inGroup;
        }
        // Orphan configurations under unknown games (rare but possible).
        const knownIds = new Set(this.gameTypes.map(t => t.id));
        for (const c of this.configurations) {
          if (!knownIds.has(c.game_type_id)) {
            (groups[c.game_type_id] = groups[c.game_type_id] || []).push(c);
          }
        }
        return groups;
      },

      async runExperiment() {
        this.experiment.running = true;
        this.experiment.error = '';
        this.experiment.results = [];
        this.experiment.progress = { active: true, completed: 0, total: 0, label: 'Preparing…' };
        try {
          const res = await fetch('/api/configurations/run-batch/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              configuration_ids: [this.experiment.selectedConfig],
              iterations: Math.max(1, this.experiment.nIterations || 1),
              demo: this.demoMode,
            }),
          });
          if (!res.ok || !res.body) {
            throw new Error(`Run failed (HTTP ${res.status})`);
          }
          await this._consumeRunStream(res.body);
          await this.loadRuns();
        } catch (e) {
          this.experiment.error = String(e.message || e);
        } finally {
          this.experiment.running = false;
          this.experiment.progress.active = false;
        }
      },

      // Parse the text/event-stream body of run-batch/stream, updating the
      // progress bar live and collecting the final result rows.
      async _consumeRunStream(body) {
        const reader = body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        const dispatchFrame = (frame) => {
          const line = frame.split('\n').find(l => l.startsWith('data:'));
          if (!line) return;
          let ev;
          try { ev = JSON.parse(line.slice(5).trim()); } catch { return; }
          this._handleRunEvent(ev);
        };
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          // SSE frames are separated by a blank line.
          let sep;
          while ((sep = buffer.indexOf('\n\n')) !== -1) {
            dispatchFrame(buffer.slice(0, sep));
            buffer = buffer.slice(sep + 2);
          }
        }
        // Flush a trailing frame not terminated by a blank line, so the final
        // `done` event is never lost if the stream ends without "\n\n".
        if (buffer.trim()) dispatchFrame(buffer);
      },

      _handleRunEvent(ev) {
        const p = this.experiment.progress;
        if (ev.type === 'start') {
          p.total = ev.total || 0;
          p.completed = 0;
          p.label = p.total ? `0 / ${p.total} games` : 'Running…';
        } else if (ev.type === 'progress') {
          p.completed = ev.completed || 0;
          p.total = ev.total || p.total;
          const where = [ev.config_name, ev.variant].filter(Boolean).join(' · ');
          const lang = ev.language ? ` [${ev.language}]` : '';
          p.label = `${p.completed} / ${p.total} games — ${where} (iter ${ev.iteration})${lang}`;
        } else if (ev.type === 'run') {
          this.experiment.results.push(ev);
        } else if (ev.type === 'done') {
          if (Array.isArray(ev.results)) this.experiment.results = ev.results;
          if (p.total) p.completed = p.total;
          p.label = 'Done';
        } else if (ev.type === 'error') {
          if (Array.isArray(ev.results) && ev.results.length) this.experiment.results = ev.results;
          this.experiment.error = ev.error || 'Run failed.';
        }
      },

};

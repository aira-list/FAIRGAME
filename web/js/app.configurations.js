// Configurations + scenario builder page methods — split out of app.js and merged onto the
// Alpine component by fairgame() in app.js (see the merge there).
window.__fgConfigurations = {
      // ---- Configurations page state -----
      // The Configuration form *is* the Scenario Builder form plus the
      // metadata fields below. Source of truth for the engine config is
      // the existing ``builder`` state object; ``configsPage.draft``
      // only holds metadata that lives outside the engine config
      // (display name, game/variation pointer used to look up the
      // template at run time). Languages live on ``builder.cfg`` so
      // the metadata picker and the rest of the form stay in sync.
      configurations: [],
      configsPage: {
        editing: null,
        draft: { name: '', game_type_id: '', variation: '' },
        error: '',
        importMsg: '',
        importError: '',
        importing: false,
        // Saved-list pager (same pattern as the Results run list).
        page: 1,
        perPage: 6,
        // Payoff variants the user is editing. Empty array = leaf
        // configuration (the matrix-tab grid is the source of truth).
        // Each entry: { name, value }. ``value`` is the engine matrix
        // shape (weights/strategies/combinations/matrix).
        variants: [],
        // Index into ``variants`` of the variant whose matrix the grid
        // is currently bound to. ``null`` means "the leaf single matrix".
        activeVariantIdx: null,
      },

      builder: {
        tab: 'template',
        // 'llm'      → at least one agent is a model; needs a prompt template,
        //              and languages come from the template's availability.
        // 'baseline' → every agent is a baseline strategy; no prompt, no
        //              language dimension (the engine runs in one internal
        //              language and the prompt is never read).
        runType: 'llm',
        cfg: defaultBuilderCfg(),
        commStyle: 'none',           // 'none' | 'real' | 'fake_dec' | 'fake_hex'
        // Costly-monitoring (trust) treatment — prompt-facing, so LLM-mode only.
        trust: { enabled: false, lookCost: 0.25 },
        // Agent interaction graph (visibility + communication). Off by
        // default → the implicit complete graph (everyone perceives everyone).
        // cell['from|to'] holds the directed level ('none'|'see'|'talk') and
        // falls back to 'talk' when absent.
        // The graph always reflects the current agents; edges default to a
        // full clique (every pair 'talk') and only serialise to an
        // ``interaction`` block when the user makes it differ from complete.
        interaction: { directed: true, cell: {}, selected: null },
        tournamentMode: false,       // round-robin between every pair of agents
        equilibriaMode: 'none',      // 'none' | 'auto' | 'manual'
        equilibriaCsv: '',
        baselineCooperate: 'strategy1',
        baselineDefect: 'strategy2',
        // Personalities and strategy labels are per-language ({lang: text})
        // because they're written verbatim into the prompt the LLM reads.
        agents: [
          { name: 'agent1', llm: 'OpenAIGPT4o', personalities: { en: 'cooperative' }, opponentPersonalityPr: 0.0 },
          { name: 'agent2', llm: 'OpenAIGPT4o', personalities: { en: 'selfish' },     opponentPersonalityPr: 0.0 },
        ],
        utilityType: 'identity',
        utilityParams: { gamma: 0.5, offset: 1.0, alpha: 0.4, beta: 0.6 },
        // Payoff matrix scratchpad
        matrix: defaultBuilderMatrix(),
        // 'reward' (higher is better) | 'penalty' (lower is better). One
        // setting for the whole configuration — payoff variants share it.
        payoffDirection: 'reward',
        stopGameWhenCsv: '',
        // Personality input mode
        personalityMode: 'per_agent',         // 'per_agent' | 'pool'
        // Pool personalities are per-language too: {lang: "one\nper\nline"}.
        personalityPoolByLang: { en: 'cooperative\nselfish' },
        opponentPriorPoolText: '0',
        json: '',
      },

      // Per-language recommendations for personality / strategy-label inputs.
      // Seeded from existing configurations and from anything typed before
      // (persisted in localStorage), surfaced as <datalist> autocompletions.
      suggestions: { personality: {}, strategy: {} },

      // ---- Configurations page ------------------------------------

      gameTypeName(gameTypeId) {
        const t = this.gameTypes.find(x => x.id === gameTypeId);
        return t ? t.name : '(unknown game)';
      },

      get configsPage_canSave() {
        const d = this.configsPage.draft;
        // Baseline mode needs no template/variant/language; just a name and a
        // game to file it under. LLM mode needs the full template selection.
        if (this.builder.runType === 'baseline') {
          return !!(d.name && d.game_type_id) && this.builderIncompleteReason() === '';
        }
        return !!(d.name && d.game_type_id && d.variation && this.builder.cfg.languages.length > 0)
          && this.builderIncompleteReason() === '';
      },

      // Filter the language picker to only those codes that actually
      // have a template body for the picked (game, variation). Empty
      // when neither has been picked — the form shows a hint instead.
      availableLanguages() {
        const d = this.configsPage.draft;
        if (!d.game_type_id || !d.variation) return [];
        const codes = new Set(
          this.templates
            .filter(t => t.game_type_id === d.game_type_id && t.variation === d.variation)
            .map(t => t.language),
        );
        return (this.languages || []).filter(l => codes.has(l.code));
      },

      // The resolved template bodies for the picked (game, variation) and
      // each currently-selected language. Shown read-only in the Template
      // tab so the user sees exactly the prompt their agents will receive.
      selectedTemplates() {
        const d = this.configsPage.draft;
        if (!d.game_type_id || !d.variation) return [];
        const meta = code => (this.languages || []).find(l => l.code === code)
          || { code, name: code, flag: '' };
        return (this.builder.cfg.languages || [])
          .map(code => {
            const t = this.templates.find(
              x => x.game_type_id === d.game_type_id && x.variation === d.variation
                && x.language === code,
            );
            if (!t) return null;
            const m = meta(code);
            return { code, name: m.name, flag: m.flag, body: t.body || '' };
          })
          .filter(Boolean);
      },

      // When the picked (game, variation) changes, drop already-selected
      // languages that aren't backed by a template anymore — saving
      // would otherwise fail at run-time with "no template for …".
      pruneSelectedLanguages() {
        const allowed = new Set(this.availableLanguages().map(l => l.code));
        this.builder.cfg.languages = (this.builder.cfg.languages || [])
          .filter(c => allowed.has(c));
        this.syncLanguageFields();
      },

      // ---- LLM vs baseline awareness ------------------------------
      // Baselines (TitForTat, AlwaysCooperate, …) never see a prompt, so
      // personality / beliefs / communication / mixed-strategy settings are
      // inert for them. The UI greys those out and explains why.
      isBaselineAgent(agent) {
        return String(agent && agent.llm || '').startsWith('baseline:');
      },

      // ---- Custom (any LiteLLM) model support ---------------------
      // Models outside the curated list are stored as ``litellm:<model>``.
      _LITELLM_PREFIX: 'litellm:',
      isCustomModel(llm) {
        return typeof llm === 'string' && llm.startsWith(this._LITELLM_PREFIX);
      },
      // The value the <select> should show for an agent: '__custom__' when the
      // model is a free-form LiteLLM string, otherwise the model name itself.
      modelSelectValue(llm) {
        return this.isCustomModel(llm) ? '__custom__' : llm;
      },
      setAgentModel(agent, value) {
        // Picking "Custom…" seeds an empty litellm: string so the text field appears.
        agent.llm = value === '__custom__' ? this._LITELLM_PREFIX : value;
      },
      customModelText(llm) {
        return this.isCustomModel(llm) ? llm.slice(this._LITELLM_PREFIX.length) : '';
      },
      setCustomModelText(agent, text) {
        agent.llm = this._LITELLM_PREFIX + (text || '').trim();
      },
      hasLLMAgents() {
        return this.builder.agents.some(a => !this.isBaselineAgent(a));
      },
      allBaselineAgents() {
        const a = this.builder.agents;
        return a.length > 0 && a.every(x => this.isBaselineAgent(x));
      },
      isLLMMode() { return this.builder.runType === 'llm'; },

      // ---- Interaction graph (visibility + communication) editor --------
      // An edge A->B at level L means B perceives A: 'see' exposes A's plays
      // to B, 'talk' also delivers A's messages. 'none' = no edge. Levels are
      // ordinal (talk subsumes see). The matrix defaults to a full clique so
      // enabling the graph without edits reproduces today's behaviour.
      _INTERACTION_LEVELS: ['none', 'see', 'talk'],
      interactionAgentNames() { return this.builder.agents.map(a => a.name); },
      interactionLevel(from, to) {
        if (from === to) return 'talk';
        return this.builder.interaction.cell[from + '|' + to] || 'talk';
      },
      setInteractionLevel(from, to, level) {
        if (from === to) return;
        this.builder.interaction.cell[from + '|' + to] = level;
        if (!this.builder.interaction.directed) {
          this.builder.interaction.cell[to + '|' + from] = level;
        }
      },
      cycleInteraction(from, to) {
        if (from === to) return;
        const order = this._INTERACTION_LEVELS;
        const cur = this.interactionLevel(from, to);
        this.setInteractionLevel(from, to, order[(order.indexOf(cur) + 1) % order.length]);
      },
      interactionIsComplete() {
        // True when the graph is still the default clique (every ordered pair
        // 'talk'), in which case no ``interaction`` block is emitted.
        const names = this.interactionAgentNames();
        for (const f of names) {
          for (const t of names) {
            if (f !== t && this.interactionLevel(f, t) !== 'talk') return false;
          }
        }
        return true;
      },
      interactionLevelLabel(level) {
        return level === 'talk' ? 'Talk' : level === 'see' ? 'See' : '—';
      },
      interactionSetAll(level) {
        const names = this.interactionAgentNames();
        for (const f of names) {
          for (const t of names) {
            if (f !== t) this.builder.interaction.cell[f + '|' + t] = level;
          }
        }
      },
      // Node-click editing: first click picks a source, the next click on a
      // different node cycles the directed source->target edge; clicking the
      // selected node again clears the selection.
      onInteractionNodeClick(name) {
        const it = this.builder.interaction;
        if (!it.selected) { it.selected = name; return; }
        if (it.selected === name) { it.selected = null; return; }
        this.cycleInteraction(it.selected, name);
      },
      // Geometry for the SVG diagram: nodes evenly spaced on a circle, edges
      // as curved directed arrows so A->B and B->A bow to opposite sides.
      interactionGraphGeom() {
        const names = this.interactionAgentNames();
        const n = names.length || 1;
        const size = 360;
        const cx = size / 2;
        const cy = size / 2;
        const nodeR = 26;
        const radius = n <= 1 ? 0 : Math.max(90, Math.min(135, 45 + n * 16));
        const nodes = names.map((name, i) => {
          const a = -Math.PI / 2 + (i * 2 * Math.PI) / n;
          return { name, x: cx + radius * Math.cos(a), y: cy + radius * Math.sin(a) };
        });
        const pos = Object.fromEntries(nodes.map((p) => [p.name, p]));
        const edges = [];
        for (const f of names) {
          for (const t of names) {
            if (f === t) continue;
            const lvl = this.interactionLevel(f, t);
            if (lvl === 'none') continue;
            const A = pos[f];
            const B = pos[t];
            const dx = B.x - A.x;
            const dy = B.y - A.y;
            const len = Math.hypot(dx, dy) || 1;
            const ux = dx / len;
            const uy = dy / len;
            const sx = A.x + ux * nodeR;
            const sy = A.y + uy * nodeR;
            const ex = B.x - ux * nodeR;
            const ey = B.y - uy * nodeR;
            const mx = (sx + ex) / 2;
            const my = (sy + ey) / 2;
            const curve = len * 0.16 + 14;
            const ccx = mx + -uy * curve;
            const ccy = my + ux * curve;
            edges.push({
              from: f,
              to: t,
              level: lvl,
              d: `M ${sx.toFixed(1)} ${sy.toFixed(1)} Q ${ccx.toFixed(1)} ${ccy.toFixed(1)} ${ex.toFixed(1)} ${ey.toFixed(1)}`,
            });
          }
        }
        return { size, nodes, edges, nodeR };
      },
      // Render the whole diagram as an SVG string injected via x-html. We
      // can't use <template x-for> to build SVG children: Alpine clones them
      // in the HTML namespace, so <circle>/<path> never render. Setting
      // innerHTML with a full <svg> string parses in the SVG namespace, and
      // clicks are handled by delegation (see onInteractionSvgClick).
      interactionSvg() {
        const g = this.interactionGraphGeom();
        const sel = this.builder.interaction.selected;
        const esc = (s) => escapeHtml(s);   // global helper from app.shared.js
        const parts = [];
        parts.push(
          `<svg width="${g.size}" height="${g.size}" viewBox="0 0 ${g.size} ${g.size}" class="select-none max-w-full">`
        );
        parts.push(
          '<defs>' +
          '<marker id="fg-arrow-see" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#0284c7"/></marker>' +
          '<marker id="fg-arrow-talk" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#059669"/></marker>' +
          '</defs>'
        );
        for (const e of g.edges) {
          const talk = e.level === 'talk';
          parts.push(
            `<path d="${e.d}" fill="none" stroke="${talk ? '#059669' : '#0284c7'}" ` +
            `stroke-width="${talk ? 4 : 2}" marker-end="url(#${talk ? 'fg-arrow-talk' : 'fg-arrow-see'})" ` +
            `style="cursor:pointer" data-edge-from="${esc(e.from)}" data-edge-to="${esc(e.to)}">` +
            `<title>${esc(e.from)} → ${esc(e.to)} (${esc(this.interactionLevelLabel(e.level))})</title></path>`
          );
        }
        for (const node of g.nodes) {
          const on = sel === node.name;
          parts.push(
            `<g style="cursor:pointer" data-node="${esc(node.name)}">` +
            `<circle cx="${node.x.toFixed(1)}" cy="${node.y.toFixed(1)}" r="${g.nodeR}" ` +
            `fill="${on ? '#2563eb' : '#ffffff'}" stroke="${on ? '#1d4ed8' : '#94a3b8'}" stroke-width="2"/>` +
            `<text x="${node.x.toFixed(1)}" y="${(node.y + 4).toFixed(1)}" text-anchor="middle" ` +
            `fill="${on ? '#ffffff' : '#334155'}" font-size="11" font-weight="600">${esc(node.name)}</text>` +
            '</g>'
          );
        }
        parts.push('</svg>');
        return parts.join('');
      },
      onInteractionSvgClick(ev) {
        const nodeEl = ev.target.closest('[data-node]');
        if (nodeEl) { this.onInteractionNodeClick(nodeEl.getAttribute('data-node')); return; }
        const edgeEl = ev.target.closest('[data-edge-from]');
        if (edgeEl) {
          this.cycleInteraction(
            edgeEl.getAttribute('data-edge-from'),
            edgeEl.getAttribute('data-edge-to')
          );
        }
      },

      // Internal single language used to run a baseline-only configuration —
      // the engine still loops over config.languages, but for baselines no
      // prompt is read so the choice is invisible and irrelevant.
      _BASELINE_LANG: 'en',

      // Switch run type, coercing agents so the two modes stay consistent:
      // baseline mode forces every agent to a baseline; LLM mode guarantees
      // at least one model-backed agent (baselines may still be added later
      // for mixed / tournament setups).
      setRunType(type) {
        if (this.builder.runType === type) return;
        this.builder.runType = type;
        if (type === 'baseline') {
          const b0 = 'baseline:' + (this.baselines[0] || 'TitForTat');
          for (const a of this.builder.agents) {
            if (!this.isBaselineAgent(a)) a.llm = b0;
          }
          // Personality pools are meaningless without prompts — use the
          // simple per-agent roster. NOTE: we deliberately do NOT collapse
          // builder.cfg.languages here — buildConfig() already serialises a
          // baseline run under the single internal language, and clearing the
          // selection would destroy the user's per-language personalities /
          // strategy labels if they later switch back to LLM mode.
          this.builder.personalityMode = 'per_agent';
        } else {
          if (!this.hasLLMAgents() && this.builder.agents.length) {
            this.builder.agents[0].llm = this.llms[0] || 'OpenAIGPT4o';
          }
        }
      },

      // Why the current draft can't be saved/run yet (''=OK). Enforces the
      // "all information compiled in each language" rule for LLM mode and the
      // "not all baseline" rule once LLM mode is chosen.
      builderIncompleteReason() {
        if (this.builder.agents.length === 0) return 'Add at least one agent.';
        if (this.isLLMMode()) {
          if (!this.hasLLMAgents()) {
            return 'LLM mode needs at least one model-backed agent (not all baselines). Switch an agent to a model, or pick Baseline mode.';
          }
          const langs = this.builder.cfg.languages || [];
          if (langs.length === 0) return 'Pick at least one language for the prompt template.';
          for (const lang of langs) {
            for (const s of this.builder.matrix.strategies) {
              if (!((s.labels && s.labels[lang]) || '').trim()) {
                return `Strategy "${s.key}" is missing its ${lang} label — every strategy needs a label in each language.`;
              }
            }
            if (this.builder.personalityMode === 'per_agent') {
              for (const a of this.builder.agents) {
                if (this.isBaselineAgent(a)) continue;   // baselines have none
                if (!((a.personalities && a.personalities[lang]) || '').trim()) {
                  return `Agent "${a.name}" is missing its ${lang} personality — fill it in for every language.`;
                }
              }
            } else {
              const lines = (this.builder.personalityPoolByLang[lang] || '')
                .split(/\r?\n/).map(s => s.trim()).filter(Boolean);
              if (lines.length === 0) {
                return `The personality pool is empty for ${lang} — provide it in every language.`;
              }
            }
          }
        }
        return '';
      },

      // Factory for a fresh agent row, with a per-language personality map
      // seeded (blank) for every currently-selected language.
      newAgent() {
        const personalities = {};
        for (const lang of (this.builder.cfg.languages || [])) personalities[lang] = '';
        // Baseline mode only offers baseline strategies in the model picker,
        // so a fresh agent must start as one — an LLM default would render as
        // a blank select and slip an unrunnable model into the config.
        const llm = this.isLLMMode()
          ? (this.llms[0] || 'OpenAIGPT4o')
          : 'baseline:' + (this.baselines[0] || 'TitForTat');
        return {
          name: 'agent' + (this.builder.agents.length + 1),
          llm,
          personalities,
          opponentPersonalityPr: 0.0,
        };
      },
      addAgent() { this.builder.agents.push(this.newAgent()); },

      // Rename an agent while keeping the interaction graph attached to it —
      // its edges are keyed 'from|to' by name, so remap them or a rename
      // silently reverts every restriction on that agent to the full clique.
      renameAgent(agent, newName) {
        const oldName = agent.name;
        agent.name = newName;
        if (newName === oldName) return;
        const cell = this.builder.interaction.cell;
        for (const key of Object.keys(cell)) {
          const [f, t] = key.split('|');
          if (f !== oldName && t !== oldName) continue;
          const remapped = (f === oldName ? newName : f) + '|' + (t === oldName ? newName : t);
          cell[remapped] = cell[key];
          delete cell[key];
        }
        if (this.builder.interaction.selected === oldName) {
          this.builder.interaction.selected = newName;
        }
      },

      // First-language (or any) personality, for compact displays like the
      // Beliefs tab's per-agent rows and the JSON-view fallbacks.
      agentPersonalityDisplay(agent) {
        const p = agent.personalities || {};
        const lang0 = (this.builder.cfg.languages || [])[0];
        return p[lang0] || Object.values(p).find(Boolean) || '—';
      },
      // Display label for a strategy in the (language-neutral) payoff grid.
      stratLabel(strat) {
        const l = strat.labels || {};
        const lang0 = (this.builder.cfg.languages || [])[0];
        return l[lang0] || Object.values(l).find(Boolean) || strat.key;
      },

      // Keep every per-language field map in step with the selected
      // languages: add a blank entry for newly-added languages, drop the
      // ones that were deselected. New languages start blank by design —
      // the user fills them with help from the saved recommendations.
      syncLanguageFields() {
        const langs = this.builder.cfg.languages || [];
        const sync = (obj) => {
          for (const lang of langs) if (!(lang in obj)) obj[lang] = '';
          for (const key of Object.keys(obj)) if (!langs.includes(key)) delete obj[key];
        };
        for (const agent of this.builder.agents) {
          agent.personalities = agent.personalities || {};
          sync(agent.personalities);
        }
        sync(this.builder.personalityPoolByLang);
        for (const s of this.builder.matrix.strategies) {
          s.labels = s.labels || {};
          sync(s.labels);
        }
      },

      // ---- Per-language recommendations ---------------------------
      _SUGGESTIONS_KEY: 'fairgame_suggestions_v1',
      suggestionsFor(kind, lang) {
        return (this.suggestions[kind] && this.suggestions[kind][lang]) || [];
      },
      _addSuggestion(kind, lang, value) {
        const v = (value || '').trim();
        if (!v || !lang) return;
        const bucket = this.suggestions[kind][lang] || (this.suggestions[kind][lang] = []);
        if (!bucket.includes(v)) bucket.push(v);
      },
      // Harvest everything currently in the form into the recommendation
      // store + localStorage. Called on save/run so good values are kept.
      harvestSuggestions() {
        for (const agent of this.builder.agents) {
          for (const [lang, val] of Object.entries(agent.personalities || {})) {
            this._addSuggestion('personality', lang, val);
          }
        }
        for (const [lang, text] of Object.entries(this.builder.personalityPoolByLang || {})) {
          (text || '').split(/\r?\n/).forEach(v => this._addSuggestion('personality', lang, v));
        }
        for (const s of this.builder.matrix.strategies) {
          for (const [lang, val] of Object.entries(s.labels || {})) {
            this._addSuggestion('strategy', lang, val);
          }
        }
        this._persistSuggestions();
      },
      _persistSuggestions() {
        try {
          localStorage.setItem(this._SUGGESTIONS_KEY, JSON.stringify(this.suggestions));
        } catch (e) { /* storage may be unavailable; recommendations are best-effort */ }
      },
      // Build the initial recommendation store from localStorage + every
      // saved configuration's per-language personalities and strategy labels.
      seedSuggestions() {
        try {
          const saved = JSON.parse(localStorage.getItem(this._SUGGESTIONS_KEY) || '{}');
          for (const kind of ['personality', 'strategy']) {
            for (const [lang, arr] of Object.entries(saved[kind] || {})) {
              (arr || []).forEach(v => this._addSuggestion(kind, lang, v));
            }
          }
        } catch (e) { /* ignore malformed cache */ }
        for (const cfg of this.configurations) {
          const gc = cfg.game_config || {};
          const persons = (gc.agents && gc.agents.personalities) || {};
          for (const [lang, arr] of Object.entries(persons)) {
            (Array.isArray(arr) ? arr : []).forEach(v => this._addSuggestion('personality', lang, v));
          }
          const strat = (gc.payoffMatrix && gc.payoffMatrix.strategies) || {};
          for (const [lang, dict] of Object.entries(strat)) {
            Object.values(dict || {}).forEach(v => this._addSuggestion('strategy', lang, v));
          }
        }
      },

      variationsForGameType(gameTypeId) {
        if (!gameTypeId) return [];
        const set = new Set();
        for (const t of this.templates) {
          if (t.game_type_id === gameTypeId) set.add(t.variation);
        }
        return Array.from(set).sort();
      },

      resetConfigDraft() {
        this.configsPage.editing = null;
        this.configsPage.draft = { name: '', game_type_id: '', variation: '' };
        this.configsPage.error = '';
        this.configsPage.variants = [];
        this.configsPage.activeVariantIdx = null;
        // Wipe the embedded builder back to defaults so a stale
        // configuration doesn't leak into the next "+ New configuration".
        this.applyConfigToBuilder({});
        this.builder.cfg.languages = [];
      },

      loadConfigForEdit(cfg) {
        this.configsPage.editing = cfg.id;
        this.configsPage.draft = {
          name: cfg.name,
          game_type_id: cfg.game_type_id,
          variation: cfg.variation,
        };
        this.configsPage.error = '';
        // Hydrate the full builder form from the saved game_config.
        const full = JSON.parse(JSON.stringify(cfg.game_config || {}));
        full.name = cfg.name;
        full.languages = cfg.languages;
        this.applyConfigToBuilder(full);
        // Variants: a group ships with cfg.variations, each entry
        // ``{axis, name, value}``. Currently every value is a payoff
        // matrix; bind the first to the matrix grid so the user can
        // edit it. Empty array means leaf — the matrix grid stays bound
        // to the single ``cfg.payoffMatrix`` populated by
        // applyConfigToBuilder above.
        const variations = cfg.variations || [];
        this.configsPage.variants = variations.map(v => ({
          name: v.name, value: JSON.parse(JSON.stringify(v.value)),
        }));
        if (this.configsPage.variants.length > 0) {
          this.configsPage.activeVariantIdx = 0;
          this.importPayoffMatrix(this.configsPage.variants[0].value, full.languages?.[0] || 'en');
        } else {
          this.configsPage.activeVariantIdx = null;
        }
      },

      // ---- Payoff variants ----------------------------------------

      addPayoffVariant() {
        // Snapshot the current matrix grid as the default starting point
        // for the new variant. If we're already in variant mode, also
        // capture-back the open variant so its in-progress edits aren't
        // lost when we switch.
        this._captureActiveVariantFromGrid();
        const langs = this.builder.cfg.languages?.length
          ? this.builder.cfg.languages : ['en'];
        const snapshot = this.buildPayoffMatrixForBuild(langs);
        const proposed = `variant${this.configsPage.variants.length + 1}`;
        this.configsPage.variants.push({ name: proposed, value: snapshot });
        this.configsPage.activeVariantIdx = this.configsPage.variants.length - 1;
        // Grid is already showing this matrix (it's a clone of what's there).
      },

      removePayoffVariant(idx) {
        // Commit the open variant's in-progress grid edits first (like
        // switch/add do) — otherwise removing a *different* variant would
        // silently discard them when the grid is re-imported below.
        this._captureActiveVariantFromGrid();
        const active = this.configsPage.activeVariantIdx ?? 0;
        this.configsPage.variants.splice(idx, 1);
        if (this.configsPage.variants.length === 0) {
          this.configsPage.activeVariantIdx = null;
        } else {
          // Removing an index below the active one shifts it down by one so
          // the same variant stays active; removing the active one falls
          // back to its neighbour (same position, clamped to the new end).
          const next = idx < active ? active - 1 : active;
          this.configsPage.activeVariantIdx = Math.min(
            next,
            this.configsPage.variants.length - 1,
          );
          this.importPayoffMatrix(
            this.configsPage.variants[this.configsPage.activeVariantIdx].value,
            this.builder.cfg.languages?.[0] || 'en',
          );
        }
      },

      switchPayoffVariant(idx) {
        // Commit the open variant's edits before swapping the grid.
        this._captureActiveVariantFromGrid();
        this.configsPage.activeVariantIdx = idx;
        this.importPayoffMatrix(
          this.configsPage.variants[idx].value,
          this.builder.cfg.languages?.[0] || 'en',
        );
      },

      _captureActiveVariantFromGrid() {
        // Re-export the matrix grid into the active variant's value so
        // user edits are persisted across switches and Save.
        const idx = this.configsPage.activeVariantIdx;
        if (idx === null || idx === undefined) return;
        const langs = this.builder.cfg.languages?.length
          ? this.builder.cfg.languages : ['en'];
        this.configsPage.variants[idx].value =
          this.buildPayoffMatrixForBuild(langs);
      },

      async saveConfiguration() {
        this.configsPage.error = '';
        // Baseline configs carry no template: synthesise the bookkeeping
        // variant label so the user never has to pick a template they
        // wouldn't use. The internal language is applied to the *payload*
        // below — we never mutate builder.cfg.languages here, so the user's
        // per-language data survives if they switch back to LLM mode.
        if (this.builder.runType === 'baseline' && !this.configsPage.draft.variation) {
          this.configsPage.draft.variation = 'baseline';
        }
        const reason = this.builderIncompleteReason();
        if (reason) { this.configsPage.error = reason; return; }
        if (!this.configsPage_canSave) {
          this.configsPage.error = this.builder.runType === 'baseline'
            ? 'Need a configuration name and a game to file it under.'
            : 'Need a name, game, variant, and at least one language.';
          return;
        }
        // Capture any pending edits in the active variant before serialising.
        this._captureActiveVariantFromGrid();
        // Remember the per-language values typed here as future suggestions.
        this.harvestSuggestions();
        try {
          // Build the full engine config from the Builder state.
          const game_config = this.buildConfig();
          // The saved Configuration owns name/languages/promptTemplate at
          // run time, so don't double-store them in game_config.
          delete game_config.name;
          delete game_config.languages;
          delete game_config.promptTemplate;
          delete game_config.templateFilename;

          const variants = this.configsPage.variants;
          const isGroup = variants.length > 0;
          const payload = {
            name: this.configsPage.draft.name,
            game_type_id: this.configsPage.draft.game_type_id,
            variation: this.configsPage.draft.variation,
            // Baseline runs have no language dimension — persist the single
            // internal language without touching the live form selection.
            languages: this.builder.runType === 'baseline'
              ? [this._BASELINE_LANG]
              : this.builder.cfg.languages,
            game_config,
          };
          if (isGroup) {
            // Move the matrix out of game_config — it lives per-variant.
            delete payload.game_config.payoffMatrix;
            payload.variations = variants.map(v => ({
              axis: 'payoffMatrix', name: v.name, value: v.value,
            }));
          }

          const path = this.configsPage.editing
            ? `/api/configurations/${this.configsPage.editing}`
            : '/api/configurations';
          const method = this.configsPage.editing ? 'PUT' : 'POST';
          await this.api(path, { method, body: JSON.stringify(payload) });
          await this.loadConfigurations();
          if (!this.configsPage.editing) {
            this.resetConfigDraft();
            this.configsPage.page = 1;  // new config is prepended — show it
          }
        } catch (e) { this.configsPage.error = String(e.message || e); }
      },

      async deleteConfiguration(id) {
        if (!confirm('Delete this configuration?')) return;
        try {
          await this.api(`/api/configurations/${id}`, { method: 'DELETE' });
          await this.loadConfigurations();
        } catch (e) { alert(e.message || e); }
      },

      async cloneConfiguration(id) {
        try {
          await this.api(`/api/configurations/${id}/clone`, { method: 'POST' });
          await this.loadConfigurations();
          // The clone is prepended server-side (newest first); jump to
          // page 1 so it is immediately visible.
          this.configsPage.page = 1;
        } catch (e) { alert(e.message || e); }
      },

      // Read a .fgbundle.json file the user picked and POST it to /api/import,
      // then refresh the library + runs so the imported config and its results
      // appear immediately. The same file can be re-picked (input is cleared).
      async importConfiguration(event) {
        const file = event.target.files && event.target.files[0];
        if (!file) return;
        this.configsPage.importError = '';
        this.configsPage.importMsg = '';
        this.configsPage.importing = true;
        try {
          let bundle;
          try { bundle = JSON.parse(await file.text()); }
          catch (e) { throw new Error('That file is not valid JSON.'); }
          const out = await this.api('/api/import', {
            method: 'POST', body: JSON.stringify(bundle),
          });
          await this.loadConfigurations();
          await this.loadRuns();
          this.configsPage.page = 1;  // imported config is prepended — show it
          const n = out.imported_runs;
          this.configsPage.importMsg =
            `Imported “${out.configuration.name}” with ${n} result${n === 1 ? '' : 's'}` +
            (out.added_templates ? ` and ${out.added_templates} template(s)` : '') + '.';
        } catch (e) {
          this.configsPage.importError = 'Import failed: ' + String(e.message || e);
        } finally {
          this.configsPage.importing = false;
          event.target.value = '';
        }
      },

      isGroupConfig(cfg) {
        return Array.isArray(cfg.variations) && cfg.variations.length > 0;
      },

      async loadLanguages() {
        try { this.languages = (await this.api('/api/languages')).languages; }
        catch (e) { console.error('loadLanguages', e); }
      },

      // ---- Builder --------------------------------------------------

      // Hydrate the form state from an engine config. The inverse of
      // buildConfig(): orchestrates focused `_hydrate*` helpers, each owning
      // one field group. Order matters — agents are hydrated before the
      // interaction graph (which falls back to the roster) and before the
      // run-type inference and language sync at the end.
      applyConfigToBuilder(cfg) {
        // Pull known fields into the builder; preserve everything else
        // by stashing the raw config so buildConfig() can layer on top.
        this.builder._raw = JSON.parse(JSON.stringify(cfg));
        this._hydrateScalars(cfg);
        this._hydrateCommStyle(cfg);
        this._hydrateEquilibria(cfg);
        this._hydrateBaselineSemantics(cfg);
        this._hydrateAgents(cfg);
        this._hydrateTrust(cfg);
        this._hydrateInteraction(cfg);
        this._hydrateUtilityTransform(cfg);
        this._hydratePayoffMatrix(cfg);

        // Infer run type from the agents: an all-baseline roster is a
        // non-LLM run (no template / no language dimension).
        this.builder.runType = this.allBaselineAgents() ? 'baseline' : 'llm';

        // Make sure every per-language field has an entry for each selected
        // language (and no orphan keys) after a full hydrate.
        this.syncLanguageFields();

        // Stop game conditions.
        this.builder.stopGameWhenCsv = (cfg.stopGameWhen || []).join(', ');

        this.builder.json = JSON.stringify(this.buildConfig(), null, 2);
      },

      // ---- applyConfigToBuilder() helpers: engine config -> form state ---

      // Scalars: value from the config, else the canonical default — never
      // the current form state, so neither a fresh draft nor an edit of a
      // sparse config inherits leftovers from the previously open one.
      _hydrateScalars(cfg) {
        const c = this.builder.cfg;
        const dflts = defaultBuilderCfg();
        for (const key of Object.keys(dflts)) {
          c[key] = cfg[key] ?? dflts[key];
        }
        // Note: cfg.llm at the top level is ignored — agent LLMs come
        // from the per-agent rows (agents.llmServices).
        c.languages = cfg.languages || ['en'];
      },

      _hydrateCommStyle(cfg) {
        if (cfg.fakeCommunication) {
          this.builder.commStyle = (cfg.fakeMessageBase === 'hex') ? 'fake_hex' : 'fake_dec';
        } else if (cfg.agentsCommunicate) {
          this.builder.commStyle = 'real';
        } else {
          this.builder.commStyle = 'none';
        }
      },

      _hydrateEquilibria(cfg) {
        if (cfg.equilibria === 'auto') this.builder.equilibriaMode = 'auto';
        else if (Array.isArray(cfg.equilibria) && cfg.equilibria.length > 0) {
          this.builder.equilibriaMode = 'manual';
          this.builder.equilibriaCsv = cfg.equilibria.join(', ');
        } else {
          this.builder.equilibriaMode = 'none';
          this.builder.equilibriaCsv = '';
        }
      },

      _hydrateBaselineSemantics(cfg) {
        this.builder.baselineCooperate = cfg.baselineSemantics?.cooperate || 'strategy1';
        this.builder.baselineDefect = cfg.baselineSemantics?.defect || 'strategy2';
      },

      // Agents — try the canonical shape first.
      _hydrateAgents(cfg) {
        const c = this.builder.cfg;
        if (cfg.agents && cfg.agents.names) {
          const a = cfg.agents;
          const langs = c.languages;
          const personsByLang = a.personalities || {};   // {lang: [..]}
          const probs = a.opponentPersonalityProb || [];
          // Per-agent models: the engine's canonical field is the top-level
          // ``llms`` (a list in agent order, or a dict keyed by agent name).
          // Fall back to the legacy ``agents.llmServices`` then a default.
          const topLlms = cfg.llms;
          const legacy = a.llmServices || [];
          const llmFor = (i, name) => {
            if (Array.isArray(topLlms)) return topLlms[i];
            if (topLlms && typeof topLlms === 'object') return topLlms[name];
            return legacy[i];
          };
          const llms = a.names.map((n, i) => llmFor(i, n) || (this.llms[0] || 'OpenAIGPT4o'));

          this.builder.personalityMode = cfg.allAgentPermutations ? 'pool' : 'per_agent';
          this.builder.tournamentMode = !!(cfg.tournament && (cfg.tournament === true || cfg.tournament.enabled));
          if (this.builder.personalityMode === 'pool') {
            // Pool mode: each language's list is the pool, not per-agent.
            const poolByLang = {};
            for (const lang of langs) poolByLang[lang] = (personsByLang[lang] || []).join('\n');
            this.builder.personalityPoolByLang = poolByLang;
            this.builder.opponentPriorPoolText = probs.map(String).join('\n');
            this.builder.agents = a.names.map((n, i) => ({
              name: n,
              llm: llms[i] || (this.llms[0] || 'OpenAIGPT4o'),
              personalities: {},
              opponentPersonalityPr: 0,
            }));
          } else {
            this.builder.agents = a.names.map((n, i) => {
              const personalities = {};
              for (const lang of langs) personalities[lang] = (personsByLang[lang] || [])[i] || '';
              return {
                name: n,
                llm: llms[i] || (this.llms[0] || 'OpenAIGPT4o'),
                personalities,
                opponentPersonalityPr: probs[i] || 0,
              };
            });
          }
        } else {
          // No agents in the config (e.g. a fresh "+ New configuration" via
          // resetConfigDraft → applyConfigToBuilder({})): reset the roster,
          // pools, and modes to defaults so a previously-edited config never
          // leaks into the new draft.
          this.builder.agents = [
            { name: 'agent1', llm: this.llms[0] || 'OpenAIGPT4o', personalities: { en: '' }, opponentPersonalityPr: 0 },
            { name: 'agent2', llm: this.llms[0] || 'OpenAIGPT4o', personalities: { en: '' }, opponentPersonalityPr: 0 },
          ];
          this.builder.personalityMode = 'per_agent';
          this.builder.personalityPoolByLang = { en: '' };
          this.builder.opponentPriorPoolText = '0';
          this.builder.tournamentMode = false;
        }
      },

      // Trust / costly-monitoring treatment (independent of agent shape).
      _hydrateTrust(cfg) {
        const trustBlock = cfg.trust || {};
        this.builder.trust = {
          enabled: !!trustBlock.enabled,
          lookCost: trustBlock.lookCost ?? 0.25,
        };
      },

      // Interaction graph: rebuild the full editor matrix from the block's
      // default level + explicit edges, so the grid faithfully mirrors it.
      _hydrateInteraction(cfg) {
        const inter = cfg.interaction;
        this.builder.interaction = {
          directed: inter ? inter.directed !== false : true,
          cell: {},
          selected: null,
        };
        if (inter) {
          const dflt = inter.default || 'talk';
          const names = (cfg.agents && cfg.agents.names) || this.builder.agents.map(a => a.name);
          for (const f of names) {
            for (const t of names) {
              if (f !== t) this.builder.interaction.cell[f + '|' + t] = dflt;
            }
          }
          for (const e of (inter.edges || [])) {
            if (e && e.from != null && e.to != null) {
              this.builder.interaction.cell[e.from + '|' + e.to] = e.level || dflt;
            }
          }
        }
      },

      _hydrateUtilityTransform(cfg) {
        const utilBlock = cfg.utilityTransform || cfg.utility;  // accept legacy key on import
        if (utilBlock && utilBlock.type) {
          this.builder.utilityType = utilBlock.type;
          Object.assign(this.builder.utilityParams, utilBlock);
        } else {
          this.builder.utilityType = 'identity';
        }
      },

      _hydratePayoffMatrix(cfg) {
        const c = this.builder.cfg;
        // Direction of the numbers: 'penalty' means lower is better.
        this.builder.payoffDirection = cfg.payoffDirection === 'penalty' ? 'penalty' : 'reward';
        if (cfg.payoffMatrix) {
          this.importPayoffMatrix(cfg.payoffMatrix, c.languages[0]);
        } else {
          // Fresh draft: restore the default 2x2 matrix so a prior config's
          // strategies/cells don't carry over.
          this.builder.matrix = defaultBuilderMatrix();
        }
      },

      // ``lang`` picks the strategy *keys* (any language's dict has them all);
      // labels are imported for every language present so multilingual
      // configs round-trip without loss.
      importPayoffMatrix(pm, lang) {
        const stratsByLang = pm.strategies || {};
        const keySource = stratsByLang[lang] || Object.values(stratsByLang)[0] || {};
        const stratKeys = Object.keys(keySource);
        if (stratKeys.length === 0) return;
        // Pristine copy of the imported block: buildPayoffMatrixForBuild
        // re-emits its weight-key wiring verbatim (or updates its values in
        // place) so the template's {weightN} placeholders keep meaning what
        // they meant. A fresh draft has no ``original`` (defaultBuilderMatrix).
        this.builder.matrix.original = JSON.parse(JSON.stringify(pm));
        this.builder.matrix.strategies = stratKeys.map(k => {
          const labels = {};
          for (const [lc, dict] of Object.entries(stratsByLang)) labels[lc] = (dict || {})[k] || '';
          return { key: k, labels };
        });
        this.builder.matrix.cells = {};
        for (const [comboKey, stratPair] of Object.entries(pm.combinations || {})) {
          const cellKey = stratPair.join('|');
          const wkeys = pm.matrix?.[comboKey];
          if (!wkeys) continue;
          this.builder.matrix.cells[cellKey] = wkeys.map(wk => pm.weights?.[wk] ?? 0);
        }
      },

      cellValue(rowKey, colKey, agentIdx) {
        const k = rowKey + '|' + colKey;
        const cell = this.builder.matrix.cells[k];
        return cell ? cell[agentIdx] ?? 0 : 0;
      },

      setCellValue(rowKey, colKey, agentIdx, raw) {
        const v = parseFloat(raw);
        const k = rowKey + '|' + colKey;
        this.builder.matrix.cells[k] = this.builder.matrix.cells[k] || [0, 0];
        this.builder.matrix.cells[k][agentIdx] = isNaN(v) ? 0 : v;
      },

      addStrategy() {
        const n = this.builder.matrix.strategies.length + 1;
        // Blank per-language labels for the currently-selected languages.
        const labels = {};
        for (const lang of (this.builder.cfg.languages || ['en'])) labels[lang] = '';
        this.builder.matrix.strategies.push({ key: 'strategy' + n, labels });
      },

      rebuildCombos() {
        // Drop cells that reference deleted strategies.
        const keys = new Set(this.builder.matrix.strategies.map(s => s.key));
        for (const k of Object.keys(this.builder.matrix.cells)) {
          const [a, b] = k.split('|');
          if (!keys.has(a) || !keys.has(b)) delete this.builder.matrix.cells[k];
        }
      },

      buildPayoffMatrixForBuild(langs) {
        // Convert the editor scratchpad into the engine's
        // weights/strategies/combinations/matrix shape.
        //
        // Weight keys are IDENTITY, not compression: templates reference
        // {weightN} placeholders, so re-interning keys by value order (the
        // old behaviour) silently re-wired which payoff each placeholder
        // showed — prompts stated inverted payoffs while scoring was fine.
        const sm = this.builder.matrix;
        // Editing an imported matrix whose strategy/cell layout is intact:
        // preserve its wiring (round-trips verbatim when nothing changed).
        if (sm.original && this._matrixWiringMatches(sm.original)) {
          return this._payoffMatrixFromOriginal(sm.original, langs);
        }
        const labels = this._matrixLabelsForBuild(langs);
        // New configuration: the canonical 2x2 symmetric layout gets the
        // documented weight1..weight4 schema every shipped template assumes.
        const canonical = this._canonicalSymmetric2x2();
        if (canonical) {
          return {
            weights: canonical.weights,
            strategies: labels,
            combinations: canonical.combinations,
            matrix: canonical.matrix,
          };
        }
        // Anything else: one weight key per (combination, slot). Equal values
        // in different roles deliberately do NOT share a key.
        const weights = {};
        const combinations = {};
        const matrix = {};
        let ccount = 1;
        let wcount = 1;
        for (const r of sm.strategies) {
          for (const c of sm.strategies) {
            const cell = sm.cells[r.key + '|' + c.key];
            if (!cell) continue;
            const ck = 'combination' + (ccount++);
            combinations[ck] = [r.key, c.key];
            matrix[ck] = cell.map(value => {
              const wk = 'weight' + (wcount++);
              weights[wk] = Number(value);
              return wk;
            });
          }
        }
        return { weights, strategies: labels, combinations, matrix };
      },

      // Per-language strategy labels, falling back to the key when blank.
      _matrixLabelsForBuild(langs) {
        const labels = {};
        for (const lang of langs) {
          labels[lang] = {};
          for (const s of this.builder.matrix.strategies) {
            labels[lang][s.key] = ((s.labels && s.labels[lang]) || '').trim() || s.key;
          }
        }
        return labels;
      },

      // True when the grid still matches the imported block's wiring: every
      // combination maps onto an existing grid cell of the same arity (with
      // resolvable weight keys), and every grid cell is covered by a
      // combination. Renamed/added/removed strategies or cells fall back to
      // the fresh-allocation paths in buildPayoffMatrixForBuild.
      _matrixWiringMatches(pm) {
        const sm = this.builder.matrix;
        const stratKeys = new Set(sm.strategies.map(s => s.key));
        const combos = Object.entries(pm.combinations || {});
        if (combos.length === 0) return false;
        const covered = new Set();
        for (const [ck, pair] of combos) {
          const wkeys = (pm.matrix || {})[ck];
          if (!Array.isArray(pair) || !Array.isArray(wkeys)) return false;
          if (!pair.every(k => stratKeys.has(k))) return false;
          if (wkeys.some(wk => (pm.weights || {})[wk] === undefined)) return false;
          const cell = sm.cells[pair.join('|')];
          if (!cell || cell.length !== wkeys.length) return false;
          covered.add(pair.join('|'));
        }
        for (const r of sm.strategies) {
          for (const c of sm.strategies) {
            const key = r.key + '|' + c.key;
            if (sm.cells[key] && !covered.has(key)) return false;
          }
        }
        return true;
      },

      // Re-emit the imported weights/combinations/matrix. Unchanged grids
      // round-trip byte-identically; edited cells update their weight's value
      // in place, and a shared weight key whose slots now disagree keeps the
      // unchanged slots (fresh weightN keys are minted for the changed ones).
      _payoffMatrixFromOriginal(pm, langs) {
        const sm = this.builder.matrix;
        const weights = JSON.parse(JSON.stringify(pm.weights));
        const combinations = JSON.parse(JSON.stringify(pm.combinations));
        const matrix = JSON.parse(JSON.stringify(pm.matrix));
        // Group every (combination, slot) by the weight key wiring it.
        const slotsByKey = {};
        for (const [ck, pair] of Object.entries(combinations)) {
          const cell = sm.cells[pair.join('|')];
          matrix[ck].forEach((wk, i) => {
            (slotsByKey[wk] = slotsByKey[wk] || []).push({ ck, i, value: Number(cell[i]) });
          });
        }
        const nextKey = () => {
          let n = 1;
          while (weights['weight' + n] !== undefined) n++;
          return 'weight' + n;
        };
        for (const [wk, slots] of Object.entries(slotsByKey)) {
          const values = new Set(slots.map(s => s.value));
          if (values.size === 1) {
            // All the key's slots agree — update the shared value in place
            // (a no-op when nothing changed).
            weights[wk] = slots[0].value;
            continue;
          }
          // Slots diverged: the ones still at the original value keep the key
          // (first slot's value when none kept it); the rest get one fresh
          // key per distinct new value.
          const original = Number(pm.weights[wk]);
          const keepValue = values.has(original) ? original : slots[0].value;
          weights[wk] = keepValue;
          const freshByValue = {};
          for (const s of slots) {
            if (s.value === keepValue) continue;
            if (freshByValue[s.value] === undefined) {
              const fresh = nextKey();
              freshByValue[s.value] = fresh;
              weights[fresh] = s.value;
            }
            matrix[s.ck][s.i] = freshByValue[s.value];
          }
        }
        // Preserve the imported per-language labels verbatim and overlay only
        // the languages the form edits — syncLanguageFields prunes the grid's
        // labels to the selected languages, so a multilingual seed's other
        // labels must survive from the original.
        const strategies = JSON.parse(JSON.stringify(pm.strategies || {}));
        const edited = this._matrixLabelsForBuild(langs);
        for (const lang of langs) strategies[lang] = edited[lang];
        return { weights, strategies, combinations, matrix };
      },

      // The canonical documented 2x2 layout: cell(1,1) and cell(2,2) are
      // equal pairs and the off-diagonal cells mirror each other. Returns the
      // weight1..weight4 schema (weight1=cell(1,1), weight3/weight2 =
      // cell(1,2)'s two slots, weight4=cell(2,2)), or null when the grid
      // isn't that shape.
      _canonicalSymmetric2x2() {
        const sm = this.builder.matrix;
        if (sm.strategies.length !== 2) return null;
        const [s1, s2] = sm.strategies.map(s => s.key);
        const c11 = sm.cells[s1 + '|' + s1];
        const c12 = sm.cells[s1 + '|' + s2];
        const c21 = sm.cells[s2 + '|' + s1];
        const c22 = sm.cells[s2 + '|' + s2];
        if (![c11, c12, c21, c22].every(c => Array.isArray(c) && c.length === 2)) return null;
        if (Number(c11[0]) !== Number(c11[1]) || Number(c22[0]) !== Number(c22[1])) return null;
        if (Number(c12[0]) !== Number(c21[1]) || Number(c12[1]) !== Number(c21[0])) return null;
        return {
          weights: {
            weight1: Number(c11[0]),
            weight2: Number(c12[1]),
            weight3: Number(c12[0]),
            weight4: Number(c22[0]),
          },
          combinations: {
            combination1: [s1, s1],
            combination2: [s1, s2],
            combination3: [s2, s1],
            combination4: [s2, s2],
          },
          matrix: {
            combination1: ['weight1', 'weight1'],
            combination2: ['weight3', 'weight2'],
            combination3: ['weight2', 'weight3'],
            combination4: ['weight4', 'weight4'],
          },
        };
      },

      // Serialize the current form state into an engine config. Orchestrates
      // a set of focused `_serialize*` helpers, each of which owns one field
      // group; the call order below is significant and mirrors the engine's
      // expectations.
      buildConfig() {
        const c = this.builder.cfg;
        const langs = this._langsForBuild(c);
        const isPool = this.builder.personalityMode === 'pool';
        const priorPool = this._parsePriorPool();
        const personalities = this._personalitiesForBuild(langs, isPool);

        const cfg = this._baseConfigForBuild(c, langs);
        this._serializeCommStyle(cfg, c);
        this._serializeEquilibria(cfg);
        this._serializeBaselineSemantics(cfg);
        this._serializeStopConditions(cfg);

        cfg.agents = this._serializeAgents(personalities, isPool, priorPool);
        if (isPool) cfg.allAgentPermutations = true;
        else delete cfg.allAgentPermutations;

        this._serializeUtilityTransform(cfg);
        delete cfg.utility;  // remove any legacy/stale key

        // Payoff matrix from the editor (only if we have any cells).
        if (Object.keys(this.builder.matrix.cells).length > 0) {
          cfg.payoffMatrix = this.buildPayoffMatrixForBuild(langs);
        }
        // Whether the numbers are rewards or penalties. Per-configuration
        // (payoff variants share it), so it stays top-level; explicit
        // 'reward' keeps the stored config self-describing.
        cfg.payoffDirection = this.builder.payoffDirection === 'penalty' ? 'penalty' : 'reward';

        this._serializeTournament(cfg);
        this._serializeTrust(cfg);
        this._serializeInteraction(cfg);
        return cfg;
      },

      // ---- buildConfig() helpers: form state -> engine config -----------

      // Baseline-only runs have no language dimension — collapse to one
      // internal language so the engine still produces a single game set.
      _langsForBuild(c) {
        return this.builder.runType === 'baseline'
          ? [this._BASELINE_LANG]
          : ((c.languages && c.languages.length) ? [...c.languages] : ['en']);
      },

      _parsePriorPool() {
        return (this.builder.opponentPriorPoolText || '')
          .split(/\r?\n/).map(s => s.trim()).filter(Boolean)
          .map(s => Number(s)).filter(n => !Number.isNaN(n));
      },

      // Per-language personalities: each language carries its own values
      // (the prompt the LLM reads is in that language). Pool mode draws from
      // the per-language pool textarea; per-agent mode from each agent's
      // per-language personality map.
      _personalitiesForBuild(langs, isPool) {
        const personalities = {};
        for (const lang of langs) {
          personalities[lang] = isPool
            ? (this.builder.personalityPoolByLang[lang] || '')
                .split(/\r?\n/).map(s => s.trim()).filter(Boolean)
            : this.builder.agents.map(a => (a.personalities && a.personalities[lang]) || '');
        }
        return personalities;
      },

      // Clone the preserved raw config and layer every plain scalar form field
      // on top. Keys with special semantics are handled by the callers and the
      // other `_serialize*` helpers: ``name``/``languages`` here,
      // ``fakeMessageCount`` in the comm-style block, ``reputationWindow``
      // (omitted unless > 0) and ``paretoOptimalSum`` (omitted when null).
      _baseConfigForBuild(c, langs) {
        const cfg = JSON.parse(JSON.stringify(this.builder._raw || {}));
        // The configuration name is the single source of truth; the engine
        // overwrites it at run time, so it only matters for the JSON
        // preview / download.
        cfg.name = this.configsPage.draft.name || c.name;
        cfg.languages = langs;
        const specialCfgKeys = new Set([
          'name', 'languages', 'fakeMessageCount', 'reputationWindow', 'paretoOptimalSum',
        ]);
        for (const key of Object.keys(defaultBuilderCfg())) {
          if (!specialCfgKeys.has(key)) cfg[key] = c[key];
        }
        // Per-agent models, in agent order. This is the field the engine
        // actually reads (PermutationExpander.resolve_llms); a single
        // top-level ``llm`` would be applied to *every* agent, collapsing
        // distinct line-ups (e.g. AlwaysCooperate vs AlwaysDefect) into one.
        cfg.llms = this.builder.agents.map(a => a.llm);
        // Drop any single ``llm`` carried over from a loaded config so it
        // can't shadow the per-agent ``llms`` list above.
        delete cfg.llm;
        if (c.reputationWindow > 0) cfg.reputationWindow = c.reputationWindow;
        if (c.paretoOptimalSum !== null && c.paretoOptimalSum !== undefined) {
          cfg.paretoOptimalSum = c.paretoOptimalSum;
        } else delete cfg.paretoOptimalSum;
        return cfg;
      },

      // Communication style → engine fields.
      _serializeCommStyle(cfg, c) {
        const style = this.builder.commStyle;
        cfg.agentsCommunicate = (style === 'real');
        if (style === 'fake_dec' || style === 'fake_hex') {
          cfg.fakeCommunication = true;
          cfg.fakeMessageCount = c.fakeMessageCount;
          cfg.fakeMessageBase = (style === 'fake_hex') ? 'hex' : 'dec';
        } else {
          delete cfg.fakeCommunication;
          delete cfg.fakeMessageCount;
          delete cfg.fakeMessageBase;
        }
      },

      _serializeEquilibria(cfg) {
        if (this.builder.equilibriaMode === 'auto') cfg.equilibria = 'auto';
        else if (this.builder.equilibriaMode === 'manual') {
          cfg.equilibria = this.builder.equilibriaCsv
            .split(',').map(s => s.trim()).filter(Boolean);
        } else {
          delete cfg.equilibria;
        }
      },

      // Baseline semantics — only emit when at least one player is a baseline.
      _serializeBaselineSemantics(cfg) {
        const usingBaseline = this.builder.agents.some(a => this.isBaselineAgent(a));
        if (usingBaseline) {
          cfg.baselineSemantics = {
            cooperate: this.builder.baselineCooperate || 'strategy1',
            defect: this.builder.baselineDefect || 'strategy2',
          };
        } else {
          delete cfg.baselineSemantics;
        }
      },

      _serializeStopConditions(cfg) {
        const stops = (this.builder.stopGameWhenCsv || '')
          .split(',').map(s => s.trim()).filter(Boolean);
        if (stops.length > 0) cfg.stopGameWhen = stops; else delete cfg.stopGameWhen;
      },

      _serializeAgents(personalities, isPool, priorPool) {
        return {
          names: this.builder.agents.map(a => a.name),
          personalities,
          llmServices: this.builder.agents.map(a => a.llm),
          opponentPersonalityProb: isPool
            ? (priorPool.length ? priorPool : [0])
            : this.builder.agents.map(a => a.opponentPersonalityPr || 0),
        };
      },

      // Key MUST be ``utilityTransform`` — that's what the validator's
      // ConfigModel and GameConfig.from_raw read. (Emitting ``utility``
      // silently dropped the transform at validation time.)
      _serializeUtilityTransform(cfg) {
        if (this.builder.utilityType !== 'identity') {
          cfg.utilityTransform = { type: this.builder.utilityType };
          if (this.builder.utilityType === 'CRRA') {
            cfg.utilityTransform.gamma = this.builder.utilityParams.gamma;
            cfg.utilityTransform.offset = this.builder.utilityParams.offset;
          } else if (this.builder.utilityType === 'FehrSchmidt') {
            cfg.utilityTransform.alpha = this.builder.utilityParams.alpha;
            cfg.utilityTransform.beta = this.builder.utilityParams.beta;
          }
        } else {
          delete cfg.utilityTransform;
        }
      },

      // Tournament mode — engine accepts a literal True or a config dict.
      _serializeTournament(cfg) {
        if (this.builder.tournamentMode) {
          cfg.tournament = { enabled: true, mode: 'round_robin', symmetric: true };
        } else {
          delete cfg.tournament;
        }
      },

      // Trust / costly monitoring — prompt-facing, so only for LLM runs.
      _serializeTrust(cfg) {
        if (this.builder.trust.enabled && this.isLLMMode()) {
          cfg.trust = {
            enabled: true,
            lookCost: this.builder.trust.lookCost,
            historyScope: 'full',
          };
        } else {
          delete cfg.trust;
        }
      },

      // Agent interaction graph — prompt-facing visibility/messaging, so only
      // for LLM runs. Serialised as default:'none' + an explicit edge for every
      // non-'none' ordered pair, but only when the user has made the graph
      // differ from the default complete clique.
      _serializeInteraction(cfg) {
        if (this.isLLMMode() && !this.interactionIsComplete()) {
          const names = this.builder.agents.map(a => a.name);
          const edges = [];
          for (const f of names) {
            for (const t of names) {
              if (f === t) continue;
              const lvl = this.interactionLevel(f, t);
              if (lvl !== 'none') edges.push({ from: f, to: t, level: lvl });
            }
          }
          cfg.interaction = {
            directed: this.builder.interaction.directed,
            default: 'none',
            edges,
          };
        } else {
          delete cfg.interaction;
        }
      },

      syncJsonToForm() {
        // User edited the JSON tab — re-import.
        try {
          const cfg = JSON.parse(this.builder.json);
          this.applyConfigToBuilder(cfg);
        } catch (e) { /* leave as-is; the parse error surfaces on Run */ }
      },

      // Regenerate the JSON textarea from the current form state, so it always
      // reflects what's been entered across the other tabs.
      refreshBuilderJson() {
        this._captureActiveVariantFromGrid();
        this.builder.json = JSON.stringify(this.buildConfig(), null, 2);
      },

      // Tab switch that keeps the JSON view in sync: opening it rebuilds the
      // JSON from the form so it's never stale.
      selectBuilderTab(id) {
        if (id === 'json') this.refreshBuilderJson();
        this.builder.tab = id;
      },

};

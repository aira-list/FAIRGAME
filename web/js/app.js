// Core Alpine component. Owns cross-page state (active page, UI mode,
// wizard, shared lookups like llms/languages, and the runs list used by
// several pages) plus networking and pagination helpers. Page-specific
// state and methods live in js/app.<page>.js and are merged onto this
// base below; cross-module helper functions live in js/app.shared.js.
function fairgame() {
  const base = {
    activePage: 'home',
    // UI complexity mode: 'basic' (default) hides the research-grade
    // machinery; 'advanced' reveals everything. Persisted so an expert
    // sets it once. Toggle lives in the sidebar.
    uiMode: 'basic',
    get advanced() { return this.uiMode === 'advanced'; },
    // Guided first-run wizard (a linear overlay over the builder state).
    wizard: { open: false, step: 1, total: 4 },
    // Inline SVG line icons (rendered via x-html in the sidebar). Stroke
    // uses currentColor so they pick up nav-link colour + active state.
    pages: [
      { id: 'home',           label: 'Home',
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9.5"/><path d="M9.5 21v-6h5v6"/></svg>' },
      { id: 'templates',      label: 'Templates',
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16"/><path d="M4 12h10"/><path d="M4 19h7"/><path d="M17 14l4 4-4 4" transform="translate(0 -5)"/></svg>' },
      { id: 'configurations', label: 'Configurations',
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.56V21a2 2 0 1 1-4 0v-.09A1.7 1.7 0 0 0 8.7 19.3a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.56-1H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.7 8.7a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34H9a1.7 1.7 0 0 0 1-1.56V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.56 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87V9a1.7 1.7 0 0 0 1.56 1H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1z"/></svg>' },
      { id: 'experiment',     label: 'Experiment',
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6"/><path d="M10 3v6.5L5.2 17.4A2 2 0 0 0 7 20.5h10a2 2 0 0 0 1.8-3.1L14 9.5V3"/><path d="M7.5 15h9"/></svg>' },
      { id: 'results',        label: 'Results',
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><rect x="7" y="11" width="3" height="6" rx="0.5"/><rect x="12.5" y="7" width="3" height="10" rx="0.5"/><rect x="18" y="13" width="3" height="4" rx="0.5"/></svg>' },
    ],
    builderTabs: [
      { id: 'template', label: 'Template' },
      { id: 'basics',   label: 'General' },
      { id: 'agents',   label: 'Agents' },
      { id: 'interaction', label: 'Interaction' },
      { id: 'matrix',   label: 'Payoff matrix' },
      { id: 'theory',   label: 'Game theory' },
      { id: 'history',  label: 'History' },
      { id: 'beliefs',  label: 'Beliefs' },
      { id: 'repro',    label: 'Reproducibility' },
      { id: 'json',     label: 'JSON view' },
    ],

    // FAIRGAME community showcase website. Empty by default (links hidden);
    // populated from /api/settings, set via FAIRGAME_COMMUNITY_URL on deploy.
    communityUrl: '',
    // Default LLM the translate endpoint uses when the dialog doesn't override
    // it; populated from /api/settings (FAIRGAME_TRANSLATOR_MODEL on deploy).
    translatorModel: '',
    llms: [],
    baselines: [],
    languages: [],   // populated from /api/languages
    // Demo mode: runs use an offline deterministic fake LLM (no API keys, no
    // charges). On by default; turn off in the sidebar to use real models.
    // The backend also defaults every run to demo, so this only needs to be
    // sent when the user turns it OFF.
    demoMode: true,

    // Runs live here (not in app.results.js) because core code uses them
    // too: resultsForConfig/filteredRuns below, loadRuns/openRun, and the
    // experiment page refreshes the list after a batch.
    runs: [],
    activeRun: null,

    async init() {
      await Promise.all([
        this.loadSettings(),
        this.loadRuns(),
        this.loadModelLists(),
        this.loadLanguages(),
        this.loadGameTypes(),
        this.loadTemplates(),
        this.loadConfigurations(),
      ]);
      // Recommendations depend on the loaded configurations.
      this.seedSuggestions();
      this.loadUiMode();
    },

    // ---- Networking helpers ---------------------------------------

    async api(path, options = {}) {
      const res = await fetch(path, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
      });
      const ct = res.headers.get('content-type') || '';
      const body = ct.includes('json') ? await res.json() : await res.text();
      if (!res.ok) {
        const detail = (body && body.detail) || body || res.statusText;
        throw new Error(detail);
      }
      return body;
    },

    // --- config <-> results mapping helpers (link is run.configuration_id) ---
    resultsForConfig(configId) {
      return this.runs.filter(r => r.configuration_id === configId);
    },
    filteredRuns() {
      return this.results.configFilter
        ? this.runs.filter(r => r.configuration_id === this.results.configFilter)
        : this.runs;
    },
    // Long lists (runs, saved configurations, result-table rows) are paged
    // so the content around them stays reachable. One generic pager backs
    // the three thin wrappers the templates call; ``state[pageKey]`` is
    // clamped in place so a shrinking list never strands the current page.
    _pageCount(items, per) {
      return Math.max(1, Math.ceil(items.length / per));
    },
    _pageSlice(items, state, pageKey, per) {
      const total = this._pageCount(items, per);
      state[pageKey] = Math.min(Math.max(1, state[pageKey]), total);
      const start = (state[pageKey] - 1) * per;
      return items.slice(start, start + per);
    },

    totalPages() { return this._pageCount(this.filteredRuns(), this.results.perPage); },
    pagedRuns() { return this._pageSlice(this.filteredRuns(), this.results, 'page', this.results.perPage); },
    goToPage(p) {
      this.results.page = Math.min(Math.max(1, p), this.totalPages());
    },

    configsTotalPages() { return this._pageCount(this.configurations, this.configsPage.perPage); },
    pagedConfigurations() { return this._pageSlice(this.configurations, this.configsPage, 'page', this.configsPage.perPage); },
    goToConfigsPage(p) {
      this.configsPage.page = Math.min(Math.max(1, p), this.configsTotalPages());
    },

    tableTotalPages() { return this._pageCount(this.activeRun?.rows || [], this.results.tablePerPage); },
    pagedRows() { return this._pageSlice(this.activeRun?.rows || [], this.results, 'tablePage', this.results.tablePerPage); },
    goToTablePage(p) {
      this.results.tablePage = Math.min(Math.max(1, p), this.tableTotalPages());
    },
    configName(configId) {
      const c = this.configurations.find(x => x.id === configId);
      return c ? c.name : '(unlinked)';
    },
    viewConfigResults(configId) {
      this.results.configFilter = configId;
      this.activePage = 'results';
      window.scrollTo(0, 0);
    },

    async loadRuns() {
      try { this.runs = (await this.api('/api/runs')).runs; }
      catch (e) { console.error('loadRuns', e); }
    },

    async loadSettings() {
      try {
        const s = await this.api('/api/settings');
        this.communityUrl = s.community_url || '';
        this.translatorModel = s.translator_model || '';
      }
      catch (e) { console.error('loadSettings', e); }
    },

    async loadModelLists() {
      try {
        const [a, b] = await Promise.all([
          this.api('/api/llms'), this.api('/api/baselines'),
        ]);
        this.llms = a.llms;
        this.baselines = b.baselines;
      } catch (e) { console.error('loadModelLists', e); }
    },

    async openRun(runId) {
      try {
        this.compare.open = false;   // single-run and compare are separate modes
        this.activeRun = await this.api(`/api/runs/${runId}`);
        this.results.tablePage = 1;
        this.activePage = 'results';
        // Tear down any chart instances from the previous run before we
        // build new ones, so they don't leak into the next render.
        for (const id of Object.keys(this._charts)) {
          try { this._charts[id]?.destroy(); } catch {}
          delete this._charts[id];
        }
        // Default view is Charts.
        this.renderCharts();
        // The results panel sits at the top of the page; scroll up so the
        // freshly opened run's charts come into view instead of leaving
        // the user looking at the carousel below.
        this.$nextTick(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
      } catch (e) { console.error('openRun', e); }
    },

    // ---- Basic / Advanced UI mode -------------------------------
    _UI_MODE_KEY: 'fairgame_ui_mode',
    // Builder tabs that only appear in Advanced mode.
    _ADVANCED_TABS: ['theory', 'history', 'interaction', 'beliefs', 'repro', 'json'],

    setUiMode(mode) {
      this.uiMode = mode === 'advanced' ? 'advanced' : 'basic';
      try { localStorage.setItem(this._UI_MODE_KEY, this.uiMode); } catch (e) { /* best effort */ }
      // If we just hid the tab the user was on, fall back to the first tab.
      if (!this.advanced && this._ADVANCED_TABS.includes(this.builder.tab)) {
        this.builder.tab = 'template';
      }
    },
    loadUiMode() {
      try {
        const saved = localStorage.getItem(this._UI_MODE_KEY);
        if (saved === 'advanced' || saved === 'basic') this.uiMode = saved;
      } catch (e) { /* best effort */ }
    },
    // Builder tabs visible in the current mode.
    visibleBuilderTabs() {
      if (this.advanced) return this.builderTabs;
      return this.builderTabs.filter(t => !this._ADVANCED_TABS.includes(t.id));
    },

    // ---- Guided first-run wizard --------------------------------
    startWizard() {
      this.resetConfigDraft();          // clean slate
      this.activePage = 'configurations';
      this.wizard.step = 1;
      this.wizard.open = true;
    },
    wizardFirstLang() {
      return (this.builder.cfg.languages || [])[0] || 'en';
    },
    // Validation message for the current step ('' = OK to advance).
    wizardStepError() {
      const d = this.configsPage.draft;
      const s = this.wizard.step;
      if (s === 1) {
        if (!d.name || !d.name.trim()) return 'Give your configuration a name.';
        return '';
      }
      if (s === 2) {
        if (!d.game_type_id) return 'Pick a game.';
        if (this.isLLMMode()) {
          if (!d.variation) return 'Pick a variant.';
          if ((this.builder.cfg.languages || []).length === 0) return 'Pick at least one language.';
        }
        return '';
      }
      if (s === 3) {
        if (this.builder.agents.length === 0) return 'Add at least one agent.';
        if (this.isLLMMode() && !this.hasLLMAgents()) {
          return 'LLM mode needs at least one model-backed agent.';
        }
        return '';
      }
      return '';
    },
    wizardNext() {
      if (this.wizardStepError()) return;
      if (this.wizard.step < this.wizard.total) this.wizard.step += 1;
    },
    wizardBack() {
      if (this.wizard.step > 1) this.wizard.step -= 1;
    },
    // Fill the fields the engine requires but the wizard doesn't ask for,
    // so a wizard-built config is always complete: blank personalities →
    // "neutral", blank strategy labels → an existing label or the key.
    _wizardPrefillForRun() {
      if (!this.isLLMMode()) return;
      const langs = this.builder.cfg.languages || [];
      for (const a of this.builder.agents) {
        if (this.isBaselineAgent(a)) continue;
        a.personalities = a.personalities || {};
        for (const lang of langs) {
          if (!((a.personalities[lang] || '').trim())) a.personalities[lang] = 'neutral';
        }
      }
      for (const strat of this.builder.matrix.strategies) {
        strat.labels = strat.labels || {};
        const fallback = Object.values(strat.labels).find(v => (v || '').trim()) || strat.key;
        for (const lang of langs) {
          if (!((strat.labels[lang] || '').trim())) strat.labels[lang] = fallback;
        }
      }
    },
    async wizardFinish() {
      this._wizardPrefillForRun();
      await this.saveConfiguration();
      if (!this.configsPage.error) {
        this.wizard.open = false;
        this.activePage = 'experiment';
        window.scrollTo(0, 0);
      }
    },

    agentSummary() {
      const a = this.builder.agents;
      return `${a.length} agent${a.length === 1 ? '' : 's'} · ${a.map(x => x.name).join(', ')}`;
    },

  };
  // Merge each page module onto the base. Object.defineProperties with
  // getOwnPropertyDescriptors preserves getters/setters (get advanced,
  // get configsPage_canSave) — Object.assign would invoke a getter and
  // copy its one-time value, breaking Alpine reactivity.
  for (const mod of [
    window.__fgTemplates,
    window.__fgConfigurations,
    window.__fgExperiment,
    window.__fgResults,
  ]) {
    Object.defineProperties(base, Object.getOwnPropertyDescriptors(mod));
  }
  return base;
}

// Templates page methods — split out of app.js and merged onto the
// Alpine component by fairgame() in app.js (see the merge there).
window.__fgTemplates = {
      // ---- Templates page state -----
      gameTypes: [],
      templates: [],
      templatesPage: {
        activeGameType: '',
        activeGameTypeName: '',
        activeGameTypeDesc: '',
        newGameTypeName: '',
        newGameTypeDesc: '',
        newTpl: { variation: '', language: 'en', body: '' },
        tplError: '',
        existingMatch: null,   // template matching (game, variation, language), if any
        historyOpen: false,    // show the existing template's version history
        showArchived: false,   // reveal the archived list
        archived: [],          // archived templates for the active game
        translateDialog: null,
        translateTargets: [],
        translateRunning: false,
        translateError: '',
        translateNotice: '',   // success/skip summary, shown after the dialog closes
      },

      // ---- Templates page -----------------------------------------

      async loadGameTypes() {
        try { this.gameTypes = (await this.api('/api/game-types')).game_types; }
        catch (e) { console.error('loadGameTypes', e); }
      },

      async loadTemplates() {
        try { this.templates = (await this.api('/api/templates')).templates; }
        catch (e) { console.error('loadTemplates', e); }
      },

      async loadConfigurations() {
        try { this.configurations = (await this.api('/api/configurations')).configurations; }
        catch (e) { console.error('loadConfigurations', e); }
      },

      templatesByGameTypeCount(gameTypeId) {
        return this.templates.filter(t => t.game_type_id === gameTypeId).length;
      },

      selectGameType(gameTypeId) {
        const gt = this.gameTypes.find(t => t.id === gameTypeId);
        this.templatesPage.activeGameType = gameTypeId;
        this.templatesPage.activeGameTypeName = gt ? gt.name : '';
        this.templatesPage.activeGameTypeDesc = gt ? (gt.description || '') : '';
      },

      async createGameType() {
        try {
          await this.api('/api/game-types', {
            method: 'POST',
            body: JSON.stringify({
              name: this.templatesPage.newGameTypeName,
              description: this.templatesPage.newGameTypeDesc,
            }),
          });
          this.templatesPage.newGameTypeName = '';
          this.templatesPage.newGameTypeDesc = '';
          await this.loadGameTypes();
        } catch (e) { alert(e.message || e); }
      },

      async deleteGameType(gameTypeId) {
        if (!confirm('Delete this game and all its templates?')) return;
        try {
          await this.api(`/api/game-types/${gameTypeId}`, { method: 'DELETE' });
          if (this.templatesPage.activeGameType === gameTypeId) this.selectGameType('');
          await Promise.all([this.loadGameTypes(), this.loadTemplates()]);
        } catch (e) { alert(e.message || e); }
      },

      templatesGroupedByVariation() {
        const groups = {};
        for (const t of this.templates) {
          if (t.game_type_id !== this.templatesPage.activeGameType) continue;
          (groups[t.variation] = groups[t.variation] || []).push(t);
        }
        // Sort each group by language for stability.
        for (const k of Object.keys(groups)) groups[k].sort((a, b) => a.language.localeCompare(b.language));
        return groups;
      },

      // Distinct variations already defined under the active game — feeds the
      // "type a new name or pick an existing one" datalist.
      variationsForActiveGameType() {
        const set = new Set();
        for (const t of this.templates) {
          if (t.game_type_id === this.templatesPage.activeGameType) set.add(t.variation);
        }
        return Array.from(set).sort();
      },

      // When (variant, language) resolves to an existing template, load its
      // body so the user is editing it; otherwise they're authoring a new one.
      syncNewTplMatch() {
        const gt = this.templatesPage.activeGameType;
        const { variation, language } = this.templatesPage.newTpl;
        const match = this.templates.find(
          t => t.game_type_id === gt && t.variation === variation
            && t.language === language && !t.archived,
        );
        const prev = this.templatesPage.existingMatch;
        if (match) {
          this.templatesPage.newTpl.body = match.body;
          this.templatesPage.existingMatch = match;
        } else {
          // Clear the body only if it was showing the previously-matched
          // template (so switching to a brand-new combo starts blank).
          if (prev) this.templatesPage.newTpl.body = '';
          this.templatesPage.existingMatch = null;
        }
        this.templatesPage.historyOpen = false;
      },

      async createTemplate() {
        this.templatesPage.tplError = '';
        const { variation, language } = this.templatesPage.newTpl;
        try {
          // POST upserts: overwrites the matching (game, variation, language)
          // template (saving a new version) or creates a new one.
          await this.api('/api/templates', {
            method: 'POST',
            body: JSON.stringify({
              game_type_id: this.templatesPage.activeGameType,
              variation, language,
              body: this.templatesPage.newTpl.body,
            }),
          });
          await this.loadTemplates();
          // Keep the form on what was just saved so version history updates.
          this.templatesPage.newTpl.variation = variation;
          this.templatesPage.newTpl.language = language;
          this.syncNewTplMatch();
        } catch (e) { this.templatesPage.tplError = String(e.message || e); }
      },

      // Start a fresh blank template (clears the create/edit form).
      resetNewTpl() {
        this.templatesPage.newTpl = { variation: '', language: 'en', body: '' };
        this.templatesPage.existingMatch = null;
        this.templatesPage.historyOpen = false;
        this.templatesPage.tplError = '';
      },

      // Archive (soft-delete) / restore / purge.
      async archiveTemplate(id) {
        try {
          await this.api(`/api/templates/${id}/archive`, { method: 'POST' });
          await this.loadTemplates();
          if (this.templatesPage.showArchived) await this.loadArchivedTemplates();
          this.syncNewTplMatch();
        } catch (e) { alert(e.message || e); }
      },
      async restoreTemplate(id) {
        try {
          await this.api(`/api/templates/${id}/restore`, { method: 'POST' });
          await this.loadTemplates();
          await this.loadArchivedTemplates();
          this.syncNewTplMatch();
        } catch (e) { alert(e.message || e); }
      },
      async purgeTemplate(id) {
        if (!confirm('Permanently delete this archived template? This cannot be undone.')) return;
        try {
          await this.api(`/api/templates/${id}`, { method: 'DELETE' });
          await this.loadArchivedTemplates();
        } catch (e) { alert(e.message || e); }
      },
      async loadArchivedTemplates() {
        try {
          const data = await this.api('/api/templates?include_archived=true');
          this.templatesPage.archived = (data.templates || []).filter(t => t.archived);
        } catch (e) { /* best-effort */ }
      },
      async toggleArchivedView() {
        this.templatesPage.showArchived = !this.templatesPage.showArchived;
        if (this.templatesPage.showArchived) await this.loadArchivedTemplates();
      },

      // Restore a previous version's body (the current body is itself snapshotted).
      async revertTemplateVersion(tpl, version) {
        try {
          await this.api(`/api/templates/${tpl.id}`, {
            method: 'PUT',
            body: JSON.stringify({
              game_type_id: tpl.game_type_id, variation: tpl.variation,
              language: tpl.language, body: version.body,
            }),
          });
          await this.loadTemplates();
          this.syncNewTplMatch();
        } catch (e) { alert(e.message || e); }
      },

      // Upload a file into the New-template form's body (variant + language
      // are chosen in the form). Seeds the variant name from the filename
      // when it's still blank, as a convenience.
      async uploadNewTemplateFile(event) {
        const file = event.target.files && event.target.files[0];
        event.target.value = '';                 // allow re-picking the same file
        if (!file) return;
        this.templatesPage.tplError = '';
        try {
          this.templatesPage.newTpl.body = await file.text();
          if (!this.templatesPage.newTpl.variation) {
            this.templatesPage.newTpl.variation = file.name.replace(/\.[^.]+$/, '');
          }
        } catch (e) { this.templatesPage.tplError = 'Could not read file: ' + (e.message || e); }
      },


      openTranslateDialog(tpl) {
        this.templatesPage.translateDialog = tpl;
        this.templatesPage.translateTargets = [];
        this.templatesPage.translateError = '';
        this.templatesPage.translateNotice = '';
      },

      async runTranslate() {
        const tpl = this.templatesPage.translateDialog;
        if (!tpl) return;
        this.templatesPage.translateRunning = true;
        this.templatesPage.translateError = '';
        try {
          const result = await this.api(`/api/templates/${tpl.id}/translate`, {
            method: 'POST',
            body: JSON.stringify({
              target_languages: this.templatesPage.translateTargets,
            }),
          });
          let msg = `Created ${result.created.length} translations.`;
          if (result.skipped.length) msg += ` Skipped: ${result.skipped.join(', ')}.`;
          await this.loadTemplates();
          if (result.errors.length) {
            // Keep the dialog open with the failures; successes are in msg.
            this.templatesPage.translateError = msg
              + ` Errors: ${result.errors.map(e => e.language + ' (' + e.error + ')').join('; ')}.`;
          } else {
            // The dialog closes — surface the summary on the page instead.
            this.templatesPage.translateNotice = msg;
            this.templatesPage.translateDialog = null;
          }
        } catch (e) {
          this.templatesPage.translateError = String(e.message || e);
        } finally {
          this.templatesPage.translateRunning = false;
        }
      },

      languageFlag(code) {
        const lang = (this.languages || []).find(l => l.code === code);
        return lang ? lang.flag : '🏳️';
      },

};

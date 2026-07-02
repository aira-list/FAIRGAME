// Cross-module helpers shared by the page modules (app.templates.js,
// app.configurations.js, app.experiment.js, app.results.js) and app.js.
// This file is loaded FIRST in index.html, so these plain top-level
// function declarations are already global by the time any module's
// object literal is evaluated or any method body runs.

// Canonical defaults for the Scenario Builder. Used for both the initial
// page state and every "fresh draft" reset, so a previously edited
// configuration can never leak values into a new one.
function defaultBuilderCfg() {
  return {
    name: 'My scenario',
    nRounds: 1,
    nIterations: 1,
    nRoundsIsKnown: true,
    randomizeBetweenIterations: false,
    languages: ['en'],
    fakeMessageCount: 10,
    elicitBeliefs: false,
    tomOrder: 1,
    reputationWindow: 0,
    reputationApplies: true,
    mixedStrategies: false,
    discountFactor: 1.0,
    discountMode: 'score',
    riskMode: 'score',
    continuationProbability: 1.0,
    paretoOptimalSum: null,
    seed: 0,
    seedCount: 1,
  };
}

// Default 2x2 Prisoner's Dilemma payoff matrix for the builder grid.
function defaultBuilderMatrix() {
  return {
    strategies: [
      { key: 'strategy1', labels: { en: 'Cooperate' } },
      { key: 'strategy2', labels: { en: 'Defect' } },
    ],
    // cells: { 'strategy1|strategy1': [3, 3], ... }
    cells: {
      'strategy1|strategy1': [3, 3],
      'strategy1|strategy2': [0, 5],
      'strategy2|strategy1': [5, 0],
      'strategy2|strategy2': [1, 1],
    },
  };
}

// Escape untrusted text before interpolating into an innerHTML/x-html
// sink. Run/CSV data (agent names, personalities, messages, LLM names)
// is operator/LLM-controlled and must never be treated as markup.
function escapeHtml(v) {
  return String(v ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

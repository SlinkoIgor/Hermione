const TAB_ICONS = {
  'existent': '📄',
  'translation': '🌎',
  'fixed': '✍️',
  'tldr': '⚡',
  'reformulation': '🔄',
  'enrichment': '🦄',
  'emoji': '🙏',
  'math_result': '🔢',
  'math_script': '🐍',
  'error': '⚠️'
};

const TAB_ORDER = {
  'error': -1,
  'existent': 0,
  'translation': 1,
  'fixed': 2,
  'reformulation': 3,
  'tldr': 4,
  'enrichment': 5,
  'emoji': 6,
  'math_result': 7,
  'math_script': 8
};

module.exports = { TAB_ICONS, TAB_ORDER };

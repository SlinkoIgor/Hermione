const TAB_ICONS = {
  'existent': '📄',
  'translation': '🌐',
  'fluent_translation': '🌎',
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
  'fluent_translation': 1,
  'translation': 2,
  'fixed': 3,
  'reformulation': 4,
  'tldr': 5,
  'enrichment': 6,
  'emoji': 7,
  'math_result': 8,
  'math_script': 9
};

module.exports = { TAB_ICONS, TAB_ORDER };

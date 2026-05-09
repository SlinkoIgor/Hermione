const TAB_ICONS = {
  'existent': '📄',
  'translation': '🌐',
  'fluent_translation': '🌎',
  'fixed': '✍️',
  'polished': '✨',
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
  'polished': 4,
  'reformulation': 5,
  'tldr': 6,
  'enrichment': 7,
  'emoji': 8,
  'math_result': 9,
  'math_script': 10
};

module.exports = { TAB_ICONS, TAB_ORDER };

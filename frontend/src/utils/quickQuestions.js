/**
 * 快速问题生成器 - 为聊天界面生成动态推荐问题
 */

// 5种问题模板
const QUESTION_TEMPLATES = [
  {
    type: 'skill',
    template: '{干员}的技能是什么',
    description: '询问干员技能',
    source: 'operators'
  },
  {
    type: 'relation',
    template: '{干员A}和{干员B}的关系',
    description: '询问两个干员之间的关系',
    source: 'characters'
  },
  {
    type: 'background',
    template: '{干员}背景故事',
    description: '询问干员背景故事',
    source: 'characters'
  },
  {
    type: 'story',
    template: '{故事}故事内容',
    description: '询问剧情故事内容',
    source: 'stories'
  },
  {
    type: 'alias',
    template: '{干员}别名有什么',
    description: '询问干员别名',
    source: 'characters'
  }
];

// 不再使用示例数据，完全依赖API数据

/**
 * 获取随机元素
 * @param {Array} array 数组
 * @returns {*} 随机元素
 */
function getRandomElement(array) {
  if (!array || array.length === 0) return null;
  return array[Math.floor(Math.random() * array.length)];
}

/**
 * 获取两个不同的随机元素
 * @param {Array} array 数组
 * @returns {Array} 两个不同元素
 */
function getTwoDifferentElements(array) {
  if (!array || array.length < 2) return [null, null];

  const idx1 = Math.floor(Math.random() * array.length);
  let idx2 = Math.floor(Math.random() * array.length);

  // 确保两个索引不同
  while (idx2 === idx1) {
    idx2 = Math.floor(Math.random() * array.length);
  }

  return [array[idx1], array[idx2]];
}

/**
 * 填充模板生成具体问题
 * @param {Object} template 模板对象
 * @param {Object} data 数据源
 * @returns {string} 生成的问题
 */
function fillTemplate(template, data) {
  let question = template.template;

  // 根据数据源选择数组
  let dataArray = [];
  switch (template.source) {
    case 'operators':
      dataArray = data.operators || [];
      break;
    case 'characters':
      dataArray = data.characters || data.operators || []; // 回退到operators
      break;
    case 'stories':
      dataArray = data.stories || [];
      break;
  }

  // 如果没有数据，无法生成问题
  if (dataArray.length === 0) {
    throw new Error(`没有${template.source}数据，无法生成${template.type}类型问题`);
  }

  // 根据模板类型填充
  switch (template.type) {
    case 'skill':
    case 'background':
    case 'alias':
      // 单个干员/角色
      const name = getRandomElement(dataArray);
      question = question.replace('{干员}', name);
      break;

    case 'relation':
      // 两个不同干员/角色
      const [name1, name2] = getTwoDifferentElements(dataArray);
      question = question
        .replace('{干员A}', name1)
        .replace('{干员B}', name2);
      break;

    case 'story':
      // 故事
      const story = getRandomElement(dataArray);
      question = question.replace('{故事}', story);
      break;
  }

  return question;
}

/**
 * 生成问题的短标签（用于按钮显示）
 * @param {string} question 完整问题
 * @param {string} type 问题类型
 * @returns {string} 短标签
 */
function generateShortLabel(question, type) {
  // 提取问题中的关键名词
  const skillKeywords = ['技能'];
  const relationKeywords = ['关系'];
  const backgroundKeywords = ['背景故事'];
  const storyKeywords = ['故事内容'];
  const aliasKeywords = ['别名'];

  let label = question;

  // 根据类型简化显示
  switch (type) {
    case 'skill':
      label = question.replace('的技能是什么', '技能');
      break;
    case 'relation':
      label = question.replace('和', '/').replace('的关系', '关系');
      break;
    case 'background':
      label = question.replace('背景故事', '背景');
      break;
    case 'story':
      label = question.replace('故事内容', '故事');
      break;
    case 'alias':
      label = question.replace('别名有什么', '别名');
      break;
  }

  // 限制长度
  if (label.length > 10) {
    label = label.substring(0, 8) + '...';
  }

  return label;
}

/**
 * 生成一组快速问题（5个，每个模板一个）
 * @param {Object} options 选项
 * @param {boolean} options.shuffle 是否随机排序
 * @param {Object} options.data 数据源 {operators: [], characters: [], stories: []}
 * @returns {Array<{label: string, question: string, type: string}>} 问题数组
 */
export function generateQuickQuestions(options = {}) {
  const { shuffle = true, data: customData } = options;

  // 数据源：使用传入的数据，如果没有数据则无法生成问题
  if (!customData) {
    throw new Error('没有快速问题数据可用');
  }

  const data = customData;

  // 确保所有必要的字段都存在
  if (!data.operators || data.operators.length === 0) {
    throw new Error('干员数据为空，无法生成问题');
  }
  if (!data.characters || data.characters.length === 0) {
    data.characters = data.operators; // 回退到干员数据
  }
  if (!data.stories || data.stories.length === 0) {
    data.stories = []; // 故事数据可以为空，但相关模板会生成默认问题
  }

  // 生成每个模板的问题
  const questions = QUESTION_TEMPLATES.map(template => {
    const question = fillTemplate(template, data);
    const label = generateShortLabel(question, template.type);

    return {
      label,
      question,
      type: template.type,
      description: template.description
    };
  });

  // 随机排序
  if (shuffle) {
    for (let i = questions.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [questions[i], questions[j]] = [questions[j], questions[i]];
    }
  }

  return questions;
}

/**
 * 刷新单个问题（按类型）
 * @param {string} type 问题类型
 * @param {Object} data 数据源
 * @returns {Object} 新问题对象
 */
export function refreshQuestionByType(type, data) {
  const template = QUESTION_TEMPLATES.find(t => t.type === type);
  if (!template) return null;

  const question = fillTemplate(template, data);
  const label = generateShortLabel(question, type);

  return {
    label,
    question,
    type,
    description: template.description
  };
}

// 默认导出
export default {
  generateQuickQuestions,
  refreshQuestionByType,
  QUESTION_TEMPLATES
};
/**
 * 数据加载工具 - 用于加载游戏数据文件
 */

/**
 * 从all_operators.json加载干员列表
 * @returns {Promise<Array<string>>} 干员名数组
 */
export async function loadOperators() {
  try {
    // 注意：这里需要正确路径，在Vue项目中需要配置路径别名或使用相对路径
    // 由于前端无法直接读取本地文件，我们将通过API获取数据
    // 这里返回一个空数组，实际数据将在quickQuestions.js中通过API获取
    console.log('loadOperators: 前端无法直接读取文件，将通过API获取');
    return [];
  } catch (error) {
    console.error('加载干员数据失败:', error);
    return [];
  }
}

/**
 * 从Markdown表格中提取名字（用于char_summary.md和story_summary.md）
 * @param {string} content - Markdown文件内容
 * @returns {Array<string>} 提取的名字数组
 */
export function extractNamesFromMarkdownTable(content) {
  const names = new Set();

  // 分割行
  const lines = content.split('\n');

  for (const line of lines) {
    // 匹配表格行：以 | 开头和结尾，排除表头分隔行
    if (line.trim().startsWith('|') && line.trim().endsWith('|') &&
        !line.includes('---') && !line.includes('<br />')) {

      // 移除首尾的 | 并分割单元格
      const cells = line.trim().slice(1, -1).split('|').map(cell => cell.trim());

      for (const cell of cells) {
        // 过滤空单元格和特殊标记
        if (cell && cell !== '<br />' && cell !== '--' && !cell.includes('...')) {
          // 移除可能的多余空格和标记
          const name = cell.replace(/\s+/g, ' ').trim();
          if (name) {
            names.add(name);
          }
        }
      }
    }
  }

  return Array.from(names);
}

/**
 * 获取干员名列表（从char_summary.md）
 * @returns {Promise<Array<string>>} 干员名数组
 */
export async function getCharacterNames() {
  try {
    // 同样，前端无法直接读取文件，这里返回示例数据
    // 实际实现需要通过API从后端获取
    console.log('getCharacterNames: 前端无法直接读取文件，将通过API获取');
    return [];
  } catch (error) {
    console.error('获取干员名失败:', error);
    return [];
  }
}

/**
 * 获取故事名列表（从story_summary.md）
 * @returns {Promise<Array<string>>} 故事名数组
 */
export async function getStoryNames() {
  try {
    console.log('getStoryNames: 前端无法直接读取文件，将通过API获取');
    return [];
  } catch (error) {
    console.error('获取故事名失败:', error);
    return [];
  }
}

/**
 * 从API获取干员数据（实际实现）
 * @returns {Promise<Array<{干员名: string}>>} 干员对象数组
 */
export async function fetchOperatorsFromAPI() {
  try {
    // 这里需要调用后端API来获取数据
    // 暂时返回空数组，实际需要在ChatView.vue中集成
    return [];
  } catch (error) {
    console.error('从API获取干员数据失败:', error);
    return [];
  }
}
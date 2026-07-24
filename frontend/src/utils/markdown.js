/* ================================================
   Markdown 渲染工具（markdown-it + DOMPurify）
   ================================================ */

import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const md = new MarkdownIt({
  html: false,      // 禁用原始 HTML，防止注入
  linkify: true,    // 自动识别 URL
  breaks: true,     // 单换行转 <br>，符合聊天场景习惯
})

/**
 * 渲染 Markdown 文本为安全 HTML。
 * 保留来源引用 span 所需的 data-* 属性（引用链接在渲染后由调用方注入）。
 * @param {string} text
 * @returns {string} 消毒后的 HTML
 */
export function renderMarkdown(text) {
  if (!text) return ''
  const html = md.render(text)
  return DOMPurify.sanitize(html, {
    ADD_ATTR: ['target', 'rel', 'title', 'data-chunk-id', 'data-collection', 'data-url', 'data-source-id'],
  })
}

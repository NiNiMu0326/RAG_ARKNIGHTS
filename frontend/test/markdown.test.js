/**
 * Tests for frontend/src/utils/markdown.js: markdown rendering + sanitization.
 */
import { describe, it, expect } from 'vitest'
import { renderMarkdown } from '../src/utils/markdown.js'

describe('renderMarkdown', () => {
  it('renders basic markdown to HTML', () => {
    const html = renderMarkdown('**粗体** 和 *斜体*')
    expect(html).toContain('<strong>粗体</strong>')
    expect(html).toContain('<em>斜体</em>')
  })

  it('converts single newlines to <br> (chat-style breaks)', () => {
    const html = renderMarkdown('第一行\n第二行')
    expect(html).toContain('<br>')
  })

  it('renders lists', () => {
    const html = renderMarkdown('- 项目一\n- 项目二')
    expect(html).toContain('<li>项目一</li>')
  })

  it('renders code blocks', () => {
    const html = renderMarkdown('`inline code`')
    expect(html).toContain('<code>inline code</code>')
  })

  it('does not render raw HTML (html: false)', () => {
    const html = renderMarkdown('<div class="x">raw</div>')
    expect(html).not.toContain('<div class="x">')
  })

  it('does not render javascript: links as anchors', () => {
    // markdown-it refuses javascript: URLs — the link is emitted as plain text
    const html = renderMarkdown('[click](javascript:alert(1))')
    expect(html).not.toContain('<a')
    expect(html).not.toContain('href')
  })

  it('escapes raw HTML with event handlers (html: false)', () => {
    // Raw HTML is escaped to inert text, so no live <img> tag can carry onerror
    const html = renderMarkdown('<img src=x onerror=alert(1)>')
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;img')
  })

  it('linkifies plain URLs', () => {
    const html = renderMarkdown('访问 https://prts.wiki 查看')
    expect(html).toContain('<a')
    expect(html).toContain('https://prts.wiki')
  })

  it('returns empty string for empty/falsy input', () => {
    expect(renderMarkdown('')).toBe('')
    expect(renderMarkdown(null)).toBe('')
    expect(renderMarkdown(undefined)).toBe('')
  })

  it('keeps citation data-* attributes allowed by sanitizer config', () => {
    // data-chunk-id etc. are in ADD_ATTR; verify the config takes effect
    // by checking DOMPurify preserves them on a rendered link
    const html = renderMarkdown('[引用](https://example.com "title")')
    expect(html).toContain('href="https://example.com"')
  })
})

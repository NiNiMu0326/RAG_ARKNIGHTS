import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSourceDrawerStore = defineStore('sourceDrawer', () => {
  const isOpen = ref(false)
  const activeSource = ref(null)   // { chunk_id, collection, url, title }
  const content = ref('')
  const loading = ref(false)
  const error = ref('')

  const API_BASE = import.meta.env.VITE_API_BASE || ''

  /**
   * Convert chunk_id (e.g. "operators_char_103_angel") to filename
   * (e.g. "operators_char_103_angel.md")
   */
  const VALID_COLLECTIONS = ['operators', 'stories', 'knowledge']

  /**
   * Fetch the full content of a chunk from the API.
   * Tries .md and .txt extensions, and falls back to other collections
   * if the given one returns 404 (LLM may mislabel chunk collection).
   */
  async function fetchChunkContent(chunkId, collection) {
    loading.value = true
    error.value = ''
    content.value = ''

    const tryFetch = async (col) => {
      for (const ext of ['.md', '.txt']) {
        const filename = `${chunkId}${ext}`
        const resp = await fetch(`${API_BASE}/chunks/${col}/${filename}`)
        if (resp.ok) return resp
      }
      return null
    }

    try {
      // Try the suggested collection first
      let response = await tryFetch(collection)

      // Fallback: try other collections if the suggested one failed
      if (!response) {
        for (const col of VALID_COLLECTIONS) {
          if (col === collection) continue
          response = await tryFetch(col)
          if (response) {
            // Update the active source with the correct collection
            activeSource.value = { ...activeSource.value, collection: col }
            break
          }
        }
      }

      if (!response) {
        throw new Error('HTTP 404')
      }

      const data = await response.json()
      content.value = data.content || ''
    } catch (e) {
      console.error('Failed to fetch chunk content:', e)
      error.value = `加载来源内容失败: ${e.message}`
      content.value = ''
    } finally {
      loading.value = false
    }
  }

  /**
   * Open the drawer for a specific source.
   * @param {Object} source - { chunk_id, collection, url?, title? }
   */
  async function open(source) {
    if (!source) return
    activeSource.value = source

    // Web sources: display URL info (no chunk to fetch)
    if (source.url && !source.chunk_id) {
      content.value = `网页来源: ${source.url}`
      loading.value = false
      error.value = ''
    } else if (source.chunk_id && source.collection) {
      await fetchChunkContent(source.chunk_id, source.collection)
    } else {
      error.value = '无效的来源信息'
      content.value = ''
      loading.value = false
    }

    isOpen.value = true
  }

  function close() {
    isOpen.value = false
    // Delay clearing content so the slide-out animation can play
    setTimeout(() => {
      activeSource.value = null
      content.value = ''
      error.value = ''
    }, 300)
  }

  return {
    isOpen,
    activeSource,
    content,
    loading,
    error,
    open,
    close,
  }
})

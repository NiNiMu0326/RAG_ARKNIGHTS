import { ref, reactive } from 'vue'
import { api } from '../api'

// Singleton state shared between AppSidebar and GraphView
const graphData = ref({ entities: [], relations: [] })
const selectedNodes = ref([])
const selectedRelations = ref([])
const neighborLevel = ref(1)
const searchQuery = ref('')
const searchResults = ref([])
const searchFocused = ref(false)
const relSearchQuery = ref('')
const relSearchResults = ref([])
const relSearchFocused = ref(false)
const availableRelations = ref([])
const hoveredRelation = ref(null)
const loading = ref(false)
const stats = reactive({ nodes: 0, edges: 0 })
const currentStats = reactive({ nodes: 0, edges: 0 })

// Relation colors for highlighting
const relationColors = {}
const colorPalette = [
  '#00e5cc', '#ff4757', '#ffca28', '#7c4dff', '#00bcd4',
  '#ff6b9d', '#ffd93d', '#6bcb77', '#4d96ff', '#ff8c42'
]

export function useGraphController() {
  // Load graph data
  async function loadGraphData() {
    try {
      loading.value = true
      const data = await api.getGraphData()
      graphData.value = data
      console.log('loadGraphData success, entities:', data.entities?.length, 'relations:', data.relations?.length)
      prepareRelationColors()
      updateStats()
    } catch (error) {
      console.error('Failed to load graph data:', error)
    } finally {
      loading.value = false
    }
  }

  function prepareRelationColors() {
    const relationTypes = new Set()
    ;(graphData.value.relations || []).forEach(r => {
      relationTypes.add(r.relation)
    })
    let colorIndex = 0
    relationTypes.forEach(type => {
      relationColors[type] = colorPalette[colorIndex % colorPalette.length]
      colorIndex++
    })
  }

  function updateStats() {
    stats.nodes = graphData.value.entities?.length || 0
    stats.edges = graphData.value.relations?.length || 0
  }

  function updateCurrentStats(nodes, edges) {
    currentStats.nodes = nodes
    currentStats.edges = edges
  }

  // Node selection
  function addNodeSelection(nodeId) {
    console.log('addNodeSelection called:', nodeId)
    console.log('selectedNodes before:', [...selectedNodes.value])
    if (!selectedNodes.value.includes(nodeId)) {
      selectedNodes.value = [...selectedNodes.value, nodeId]
      console.log('selectedNodes after:', [...selectedNodes.value])
    }
    searchQuery.value = ''
    searchResults.value = []
    searchFocused.value = false
    updateAvailableRelations()
  }

  function removeNodeSelection(nodeId) {
    selectedNodes.value = selectedNodes.value.filter(id => id !== nodeId)
    updateAvailableRelations()
  }

  function clearSelection() {
    selectedNodes.value = []
    selectedRelations.value = []
    availableRelations.value = []
    selectedEdge.value = null
  }

  // Search
  function handleSearch(query) {
    searchQuery.value = query
    const entities = graphData.value.entities || []
    console.log('handleSearch:', query, 'entities:', entities.length)
    if (!query || query.length < 1) {
      searchResults.value = [...entities].sort((a, b) => a.entity.localeCompare(b.entity))
    } else {
      const q = query.toLowerCase()
      searchResults.value = entities
        .filter(e => e.entity.toLowerCase().includes(q))
        .sort((a, b) => a.entity.localeCompare(b.entity))
    }
  }

  function onSearchFocus() {
    searchFocused.value = true
    console.log('onSearchFocus, searchFocused:', searchFocused.value, 'entities:', (graphData.value.entities || []).length)
    if (!searchQuery.value.trim()) {
      searchResults.value = [...(graphData.value.entities || [])].sort((a, b) => a.entity.localeCompare(b.entity))
    }
  }

  function onSearchBlur() {
    searchFocused.value = false
    // 清空搜索结果，避免失去焦点后下拉框仍然显示
    searchResults.value = []
  }

  // Relation search
  function handleRelSearch(query) {
    relSearchQuery.value = query
    const relationTypes = Object.keys(relationColors).sort((a, b) => a.localeCompare(b))

    if (!query || query.length < 1) {
      relSearchResults.value = relationTypes.slice(0, 50)
    } else {
      const q = query.toLowerCase()
      relSearchResults.value = relationTypes.filter(type =>
        type.toLowerCase().includes(q)
      ).slice(0, 50)
    }
  }

  function onRelSearchFocus() {
    relSearchFocused.value = true
    if (!relSearchQuery.value.trim()) {
      relSearchResults.value = Object.keys(relationColors).sort((a, b) => a.localeCompare(b)).slice(0, 50)
    }
  }

  function onRelSearchBlur() {
    relSearchFocused.value = false
    // 清空关系搜索结果，避免失去焦点后下拉框仍然显示
    relSearchResults.value = []
  }

  function toggleRelationSelection(rel) {
    const idx = selectedRelations.value.indexOf(rel)
    if (idx >= 0) {
      selectedRelations.value.splice(idx, 1)
    } else {
      selectedRelations.value.push(rel)
    }
  }

  function updateAvailableRelations() {
    if (selectedNodes.value.length === 0) {
      availableRelations.value = []
      return
    }
    const nodeSet = new Set(selectedNodes.value)
    const relationTypes = new Set()
    ;(graphData.value.relations || []).forEach(r => {
      if (nodeSet.has(r.source) || nodeSet.has(r.target)) {
        relationTypes.add(r.relation)
      }
    })
    availableRelations.value = Array.from(relationTypes).sort((a, b) => a.localeCompare(b))
    // Default: select all
    selectedRelations.value = [...availableRelations.value]
  }

  // Level
  function setNeighborLevel(level) {
    neighborLevel.value = level
  }

  return {
    // State
    graphData,
    selectedNodes,
    selectedRelations,
    neighborLevel,
    searchQuery,
    searchResults,
    searchFocused,
    relSearchQuery,
    relSearchResults,
    relSearchFocused,
    availableRelations,
    hoveredRelation,
    loading,
    stats,
    currentStats,
    relationColors,
    // Actions
    loadGraphData,
    updateCurrentStats,
    addNodeSelection,
    removeNodeSelection,
    clearSelection,
    handleSearch,
    onSearchFocus,
    onSearchBlur,
    handleRelSearch,
    onRelSearchFocus,
    onRelSearchBlur,
    toggleRelationSelection,
    updateAvailableRelations,
    setNeighborLevel
  }
}

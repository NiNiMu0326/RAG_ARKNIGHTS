import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

function _flattenEntities(entities) {
  if (!entities) return []
  if (typeof entities === 'object' && !Array.isArray(entities)) {
    return Object.entries(entities).flatMap(([type, names]) =>
      (names || []).map(name => ({ entity: name, type }))
    )
  }
  return Array.isArray(entities) ? entities : []
}

function _countEntities(entities) {
  if (!entities) return 0
  if (typeof entities === 'object' && !Array.isArray(entities)) {
    return Object.values(entities).reduce((sum, arr) => sum + (arr?.length || 0), 0)
  }
  return Array.isArray(entities) ? entities.length : 0
}

export const useGraphStore = defineStore('graph', () => {
  // State - using array instead of Set for proper reactivity
  const graphData = ref({ entities: {}, relations: [] })
  const selectedNodes = ref([])
  const selectedEdge = ref(null)
  const searchQuery = ref('')
  const searchResults = ref([])
  const relSearchQuery = ref('')
  const relSearchResults = ref([])
  const selectedRelations = ref([])  // Changed from Set to array for reactivity
  const neighborLevel = ref(1)
  const loading = ref(false)
  const searchFocused = ref(false)
  const relSearchFocused = ref(false)

  // Computed
  const entityTypes = computed(() => {
    const entities = graphData.value.entities
    if (typeof entities === 'object' && !Array.isArray(entities)) {
      return Object.keys(entities)
    }
    const types = new Set()
    ;(Array.isArray(entities) ? entities : []).forEach(e => types.add(e.type || 'default'))
    return Array.from(types)
  })

  const relationTypes = computed(() => {
    const types = new Set()
    graphData.value.relations.forEach(r => types.add(r.relation))
    return Array.from(types)
  })

  // Actions
  function setGraphData(data) {
    graphData.value = data
    // Reset selections when data changes
    selectedNodes.value = []
    selectedEdge.value = null
    selectedRelations.value = []
  }

  function addNodeSelection(nodeId) {
    if (!selectedNodes.value.includes(nodeId)) {
      selectedNodes.value.push(nodeId)
    }
    searchQuery.value = ''
    searchResults.value = []
    searchFocused.value = false
  }

  function removeNodeSelection(nodeId) {
    selectedNodes.value = selectedNodes.value.filter(id => id !== nodeId)
  }

  function clearSelection() {
    selectedNodes.value = []
    selectedEdge.value = null
    selectedRelations.value = []
  }

  function handleSearch(query) {
    if (!query.trim()) {
      searchResults.value = []
      return
    }
    const q = query.toLowerCase()
    searchResults.value = _flattenEntities(graphData.value.entities)
      .filter(e => e.entity.toLowerCase().includes(q))
      .slice(0, 20)
  }

  function handleRelSearch(query) {
    if (!query.trim()) {
      relSearchResults.value = []
      return
    }
    const q = query.toLowerCase()
    relSearchResults.value = relationTypes.value
      .filter(r => r.toLowerCase().includes(q))
      .slice(0, 20)
  }

  function toggleRelationSelection(rel) {
    const idx = selectedRelations.value.indexOf(rel)
    if (idx >= 0) {
      selectedRelations.value.splice(idx, 1)
    } else {
      selectedRelations.value.push(rel)
    }
  }

  function onSearchFocus() {
    searchFocused.value = true
    if (!searchQuery.value.trim()) {
      searchResults.value = _flattenEntities(graphData.value.entities).slice(0, 50)
    }
  }

  function onSearchBlur() {
    searchFocused.value = false
  }

  function onRelSearchFocus() {
    relSearchFocused.value = true
    if (!relSearchQuery.value.trim()) {
      relSearchResults.value = relationTypes.value.slice(0, 50)
    }
  }

  function onRelSearchBlur() {
    relSearchFocused.value = false
  }

  return {
    // State
    graphData,
    selectedNodes,
    selectedEdge,
    searchQuery,
    searchResults,
    relSearchQuery,
    relSearchResults,
    selectedRelations,
    neighborLevel,
    loading,
    searchFocused,
    relSearchFocused,
    // Computed
    entityTypes,
    relationTypes,
    // Actions
    setGraphData,
    addNodeSelection,
    removeNodeSelection,
    clearSelection,
    handleSearch,
    handleRelSearch,
    toggleRelationSelection,
    onSearchFocus,
    onSearchBlur,
    onRelSearchFocus,
    onRelSearchBlur
  }
})

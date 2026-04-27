/**
 * Tests for useGraphController composable.
 * Usage: cd frontend && npx vitest run test/graphController.test.js
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock api module
vi.mock('../src/api', () => ({
  api: {
    getGraphData: vi.fn().mockResolvedValue({
      entities: {
        '干员': ['银灰', '初雪', '崖心'],
        '组织': ['喀兰贸易', '罗德岛'],
      },
      relations: [
        { source: '银灰', target: '初雪', relation: '兄妹', description: '哥哥' },
        { source: '银灰', target: '喀兰贸易', relation: '隶属于', description: '' },
        { source: '崖心', target: '罗德岛', relation: '合作', description: '' },
      ],
    }),
  },
}))

import { useGraphController, flattenEntities, countEntities, isEntitiesEmpty } from '../src/composables/useGraphController'

describe('flattenEntities', () => {
  it('flattens dict format to array', () => {
    const entities = { '干员': ['银灰', '初雪'], '组织': ['罗德岛'] }
    const result = flattenEntities(entities)
    expect(result).toEqual([
      { entity: '银灰', type: '干员' },
      { entity: '初雪', type: '干员' },
      { entity: '罗德岛', type: '组织' },
    ])
  })

  it('handles empty/null', () => {
    expect(flattenEntities(null)).toEqual([])
    expect(flattenEntities({})).toEqual([])
  })

  it('handles old array format', () => {
    const result = flattenEntities([{ entity: 'A', type: 'X' }])
    expect(result).toEqual([{ entity: 'A', type: 'X' }])
  })
})

describe('countEntities', () => {
  it('counts dict format', () => {
    expect(countEntities({ '干员': ['a', 'b'], '组织': ['c'] })).toBe(3)
  })

  it('returns 0 for null/empty', () => {
    expect(countEntities(null)).toBe(0)
    expect(countEntities({})).toBe(0)
  })

  it('counts array format', () => {
    expect(countEntities([{ entity: 'a' }, { entity: 'b' }])).toBe(2)
  })
})

describe('isEntitiesEmpty', () => {
  it('returns true for null', () => {
    expect(isEntitiesEmpty(null)).toBe(true)
  })

  it('returns false when entities exist', () => {
    expect(isEntitiesEmpty({ '干员': ['银灰'] })).toBe(false)
  })
})

describe('useGraphController', () => {
  let controller

  beforeEach(() => {
    vi.clearAllMocks()
    controller = useGraphController()
    controller.selectedNodes.value = []
    controller.selectedRelations.value = []
    controller.searchQuery.value = ''
    controller.searchResults.value = []
    controller.graphData.value = { entities: {}, relations: [] }
  })

  describe('loadGraphData', () => {
    it('loads data and prepares relation colors', async () => {
      await controller.loadGraphData()
      const data = controller.graphData.value
      expect(countEntities(data.entities)).toBe(5)
      expect(data.relations.length).toBe(3)
      expect(Object.keys(controller.relationColors).length).toBeGreaterThan(0)
    })

    it('sets loading to false after load', async () => {
      await controller.loadGraphData()
      expect(controller.loading.value).toBe(false)
    })
  })

  describe('node selection', () => {
    beforeEach(async () => {
      await controller.loadGraphData()
    })

    it('adds a node to selection', () => {
      controller.addNodeSelection('银灰')
      expect(controller.selectedNodes.value).toContain('银灰')
    })

    it('does not add duplicate', () => {
      controller.addNodeSelection('银灰')
      controller.addNodeSelection('银灰')
      expect(controller.selectedNodes.value.length).toBe(1)
    })

    it('removes a node from selection', () => {
      controller.addNodeSelection('银灰')
      controller.addNodeSelection('初雪')
      controller.removeNodeSelection('银灰')
      expect(controller.selectedNodes.value).toEqual(['初雪'])
    })

    it('clearSelection removes all', () => {
      controller.addNodeSelection('银灰')
      controller.addNodeSelection('初雪')
      controller.clearSelection()
      expect(controller.selectedNodes.value.length).toBe(0)
      expect(controller.selectedRelations.value.length).toBe(0)
    })
  })

  describe('search', () => {
    beforeEach(async () => {
      await controller.loadGraphData()
    })

    it('searches entities by name', () => {
      controller.handleSearch('银灰')
      expect(controller.searchResults.value.length).toBe(1)
      expect(controller.searchResults.value[0].entity).toBe('银灰')
    })

    it('returns all entities when query is empty', () => {
      controller.handleSearch('')
      expect(controller.searchResults.value.length).toBe(5)
    })

    it('is case sensitive (Chinese)', () => {
      controller.handleSearch('罗德岛')
      expect(controller.searchResults.value.length).toBe(1)
    })
  })

  describe('relation selection', () => {
    beforeEach(async () => {
      await controller.loadGraphData()
    })

    it('updates available relations based on selected nodes', () => {
      controller.addNodeSelection('银灰')
      expect(controller.availableRelations.value.length).toBeGreaterThan(0)
    })

    it('toggle relation selection', () => {
      controller.selectedRelations.value = ['兄妹', '隶属于']
      controller.toggleRelationSelection('兄妹')
      expect(controller.selectedRelations.value).toEqual(['隶属于'])
      controller.toggleRelationSelection('合作')
      expect(controller.selectedRelations.value).toContain('合作')
    })
  })

  describe('neighbor level', () => {
    it('sets neighbor level', () => {
      controller.setNeighborLevel(3)
      expect(controller.neighborLevel.value).toBe(3)
      controller.setNeighborLevel(1)
      expect(controller.neighborLevel.value).toBe(1)
    })
  })

  describe('updateCurrentStats', () => {
    it('updates stats', () => {
      controller.updateCurrentStats(10, 25)
      expect(controller.currentStats.nodes).toBe(10)
      expect(controller.currentStats.edges).toBe(25)
    })
  })
})

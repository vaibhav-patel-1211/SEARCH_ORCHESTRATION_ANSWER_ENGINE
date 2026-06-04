import { useCallback, useEffect, useMemo, useState } from 'react'
import { Search, Plus, ChevronDown, ChevronRight, Info, Eye, Code as CodeIcon, Trash2 } from 'lucide-react'
import { chatAPI } from '../services/api'
import './SkillsView.css'

const DEFAULT_SKILL_DEFINITION = `---
name: exam
description: Long-form explainer for foundational topics.
triggers:
  - explain
  - overview
  - what is
prompt: |
  Explain the topic in detail with a clear definition, key milestones,
  main categories with examples, real-world applications, pros/cons, and
  future trends. Use accessible language with concrete examples.
---
`

function SkillsView() {
  const [selectedSkillId, setSelectedSkillId] = useState('')
  const [isExamplesOpen, setIsExamplesOpen] = useState(true)
  const [isEditing, setIsEditing] = useState(false)
  const [skills, setSkills] = useState([])
  const [draftDefinition, setDraftDefinition] = useState(DEFAULT_SKILL_DEFINITION)
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')

  const filteredSkills = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    if (!query) return skills
    return skills.filter((skill) => String(skill.name || '').toLowerCase().includes(query))
  }, [skills, searchQuery])

  const selectedSkill = skills.find((skill) => skill.id === selectedSkillId) || null

  const loadSkills = useCallback(async (opts = {}) => {
    setIsLoading(true)
    setError('')
    try {
      const data = await chatAPI.getSkills()
      const items = data?.skills || []
      setSkills(items)
      // Only auto-select on initial mount (opts.autoSelect), not on every reload
      if (opts.autoSelect) {
        if (items.length > 0) {
          setSelectedSkillId(items[0].id)
          setDraftDefinition(items[0].definition || '')
        }
      }
    } catch (err) {
      setError(err.message || 'Failed to load skills.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadSkills({ autoSelect: true })
  }, [loadSkills])

  const handleSelectSkill = (skill) => {
    setSelectedSkillId(skill.id)
    setDraftDefinition(skill.definition || '')
    setIsEditing(false)
    setError('')
  }

  const handleCreateNew = () => {
    setSelectedSkillId('')
    setDraftDefinition(DEFAULT_SKILL_DEFINITION)
    setIsEditing(true)
    setError('')
  }

  const handleSave = async () => {
    if (isSaving) return
    const payload = draftDefinition.trim()
    if (!payload) {
      setError('Skill definition is required.')
      return
    }
    setIsSaving(true)
    setError('')
    try {
      if (selectedSkillId) {
        await chatAPI.updateSkill(selectedSkillId, { definition: payload })
      } else {
        const created = await chatAPI.createSkill(payload)
        setSelectedSkillId(created.id)
      }
      await loadSkills()
      setIsEditing(false)
    } catch (err) {
      setError(err.message || 'Failed to save skill.')
    } finally {
      setIsSaving(false)
    }
  }

  const handleToggleEnabled = async () => {
    if (!selectedSkill || isSaving) return
    setIsSaving(true)
    setError('')
    try {
      await chatAPI.updateSkill(selectedSkill.id, { enabled: !selectedSkill.enabled })
      await loadSkills()
    } catch (err) {
      setError(err.message || 'Failed to update skill.')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!selectedSkill || isSaving) return
    setIsSaving(true)
    setError('')
    try {
      await chatAPI.deleteSkill(selectedSkill.id)
      setSelectedSkillId('')
      setDraftDefinition(DEFAULT_SKILL_DEFINITION)
      await loadSkills()
    } catch (err) {
      setError(err.message || 'Failed to delete skill.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="skills-container">
      {/* Middle Pane: Skills List */}
      <div className="skills-list-pane">
        <div className="skills-list-header">
          <h2>Skills</h2>
          <div className="header-icons">
            <button className="icon-btn" onClick={handleCreateNew} title="Create skill">
              <Plus size={18} />
            </button>
          </div>
        </div>

        <div className="skills-search">
          <Search size={14} />
          <input
            type="text"
            placeholder="Search skills"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
          />
        </div>
        
        <div className="skills-scroll-area">
          <div 
            className="group-header" 
            onClick={() => setIsExamplesOpen(!isExamplesOpen)}
          >
            {isExamplesOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <span>Your skills</span>
          </div>
          
          {isExamplesOpen && (
            <div className="skills-items">
              {isLoading ? (
                <div className="skills-empty">Loading skills...</div>
              ) : filteredSkills.length === 0 ? (
                <div className="skills-empty">No skills saved yet.</div>
              ) : (
                filteredSkills.map((skill) => (
                  <div 
                    key={skill.id} 
                    className={`skill-item ${selectedSkillId === skill.id ? 'active' : ''}`}
                    onClick={() => handleSelectSkill(skill)}
                  >
                    <div className="skill-item-icon">
                      <CodeIcon size={14} />
                    </div>
                    <span>{skill.name}</span>
                    <span className={`skill-status ${skill.enabled ? 'on' : 'off'}`}>
                      {skill.enabled ? 'On' : 'Off'}
                    </span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right Pane: Skill Detail */}
      <div className="skill-detail-pane">
        <div className="skill-detail-header">
          <div className="header-left">
            <h1>{selectedSkill ? selectedSkill.name : 'Create Skill'}</h1>
          </div>
          <div className="header-actions">
            {selectedSkill && (
              <>
                <button
                  className={`toggle-btn ${selectedSkill.enabled ? 'active' : ''}`}
                  onClick={handleToggleEnabled}
                  disabled={isSaving}
                  title="Enable skill"
                >
                  <div className="toggle-thumb" />
                </button>
                <button className="icon-btn" onClick={handleDelete} title="Delete skill" disabled={isSaving}>
                  <Trash2 size={16} />
                </button>
              </>
            )}
          </div>
        </div>

        {selectedSkill && (
          <>
            <div className="skill-metadata">
              <div className="metadata-item">
                <span className="label">Triggers</span>
                <div className="skill-trigger-list">
                  {selectedSkill.triggers?.length
                    ? selectedSkill.triggers.map((trigger) => (
                        <span key={trigger} className="skill-trigger-chip">{trigger}</span>
                      ))
                    : <span className="value">No triggers set</span>}
                </div>
              </div>
            </div>

            <div className="skill-description">
              <div className="description-label">
                <span>Description</span>
                <Info size={14} />
              </div>
              <p>{selectedSkill.description || 'No description provided.'}</p>
            </div>
          </>
        )}

        <div className="skill-content-wrapper">
          <div className="content-toolbar">
            <div className="toolbar-right">
              <button 
                className={`toolbar-btn ${!isEditing ? 'active' : ''}`}
                onClick={() => setIsEditing(false)}
                title="Read"
              >
                <Eye size={14} />
              </button>
              <button 
                className={`toolbar-btn ${isEditing ? 'active' : ''}`}
                onClick={() => setIsEditing(true)}
                title="Edit"
              >
                <CodeIcon size={14} />
              </button>
              <button className="primary-btn" onClick={handleSave} disabled={isSaving}>
                Save Skill
              </button>
            </div>
          </div>
          <div className="skill-content-box">
            {!isEditing ? (
              <pre className="skill-readonly">{draftDefinition || 'No skill definition yet.'}</pre>
            ) : (
              <textarea 
                className="skill-edit-textarea"
                value={draftDefinition}
                onChange={(event) => setDraftDefinition(event.target.value)}
                spellCheck="false"
              />
            )}
          </div>
        </div>

        {error && <div className="skills-error">{error}</div>}
      </div>
    </div>
  )
}

export default SkillsView

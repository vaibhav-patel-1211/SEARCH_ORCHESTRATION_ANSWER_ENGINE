import { useState } from 'react'
import { Search, Plus, ChevronDown, ChevronRight, Info, Eye, Code as CodeIcon, MoreHorizontal } from 'lucide-react'
import './SkillsView.css'

function SkillsView() {
  const [selectedSkillId, setSelectedSkillId] = useState('algorithmic-art')
  const [isExamplesOpen, setIsExamplesOpen] = useState(true)
  const [isEditing, setIsEditing] = useState(false)

  const skills = [
    { id: 'skill-creator', name: 'skill-creator' },
    { id: 'algorithmic-art', name: 'algorithmic-art' },
    { id: 'brand-guidelines', name: 'brand-guidelines' },
    { id: 'canvas-design', name: 'canvas-design' },
    { id: 'doc-coauthoring', name: 'doc-coauthoring' },
    { id: 'internal-comms', name: 'internal-comms' },
    { id: 'mcp-builder', name: 'mcp-builder' },
    { id: 'slack-gif-creator', name: 'slack-gif-creator' },
    { id: 'theme-factory', name: 'theme-factory' },
    { id: 'web-artifacts-builder', name: 'web-artifacts-builder' },
  ]

  const selectedSkill = {
    id: 'algorithmic-art',
    name: 'algorithmic-art',
    addedBy: 'Anthropic',
    invokedBy: 'User or Claude',
    description: 'Creating algorithmic art using p5.js with seeded randomness and interactive parameter exploration. Use this when users request creating art using code, generative art, algorithmic art, flow fields, or particle systems. Create original algorithmic art rather than copying existing artists\' work to avoid copyright violations.',
    content: `name: algorithmic-art description: Creating algorithmic art using p5.js with seeded randomness and interactive parameter exploration. Use this when users request creating art using code, generative art, algorithmic art, flow fields, or particle systems. Create original algorithmic art rather than copying existing artists' work to avoid copyright violations. license: Complete terms in LICENSE.txt

Algorithmic philosophies are computational aesthetic movements that are then expressed through code. Output .md files (philosophy), .html files (interactive viewer), and .js files (generative algorithms).

This happens in two steps:
1. Algorithmic Philosophy Creation (.md file)
2. Express by creating p5.js generative art (.html + .js files)`
  }

  const handleAction = (action) => {
    alert(`${action} feature coming soon!`)
  }

  return (
    <div className="skills-container">
      {/* Middle Pane: Skills List */}
      <div className="skills-list-pane">
        <div className="skills-list-header">
          <h2>Skills</h2>
          <div className="header-icons">
            <button className="icon-btn" onClick={() => handleAction('Search')}>
              <Search size={18} />
            </button>
            <button className="icon-btn" onClick={() => handleAction('Add Skill')}>
              <Plus size={18} />
            </button>
          </div>
        </div>
        
        <div className="skills-scroll-area">
          <div 
            className="group-header" 
            onClick={() => setIsExamplesOpen(!isExamplesOpen)}
          >
            {isExamplesOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <span>Examples</span>
          </div>
          
          {isExamplesOpen && (
            <div className="skills-items">
              {skills.map(skill => (
                <div 
                  key={skill.id} 
                  className={`skill-item ${selectedSkillId === skill.id ? 'active' : ''}`}
                  onClick={() => setSelectedSkillId(skill.id)}
                >
                  <div className="skill-item-icon">
                    <CodeIcon size={14} />
                  </div>
                  <span>{skill.name}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right Pane: Skill Detail */}
      <div className="skill-detail-pane">
        <div className="skill-detail-header">
          <div className="header-left">
            <h1>{selectedSkill.name}</h1>
          </div>
        </div>

        <div className="skill-metadata">
          <div className="metadata-item">
            <span className="label">Added by</span>
            <span className="value">{selectedSkill.addedBy}</span>
          </div>
          <div className="metadata-item">
            <span className="label">Invoked by</span>
            <span className="value">{selectedSkill.invokedBy}</span>
          </div>
        </div>

        <div className="skill-description">
          <div className="description-label">
            <span>Description</span>
            <Info size={14} />
          </div>
          <p>{selectedSkill.description}</p>
        </div>

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
            </div>
          </div>
          <div className="skill-content-box">
            {!isEditing ? (
              <div className="markdown-content">
                {selectedSkill.content.split('\n').map((line, i) => {
                  if (line.startsWith('name:')) {
                    return <p key={i} className="content-intro"><strong>{line}</strong></p>
                  }
                  if (line.match(/^\d\./)) {
                    return <li key={i} className="content-list-item">{line}</li>
                  }
                  return <p key={i}>{line}</p>
                })}
              </div>
            ) : (
              <textarea 
                className="skill-edit-textarea"
                defaultValue={selectedSkill.content}
                spellCheck="false"
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default SkillsView

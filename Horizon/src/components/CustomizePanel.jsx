import { ArrowLeft, BrainCircuit, Sparkles } from 'lucide-react'
import './CustomizePanel.css'

function CustomizePanel({ onClose, onNavigate, activeView }) {
  const isMemoryActive = activeView === 'customize'
  const isSkillsActive = activeView === 'skills'
  return (
    <aside className="customize-panel">
      <div className="customize-header">
        <button className="back-btn" onClick={onClose}>
          <ArrowLeft size={20} />
        </button>
        <h2>Customize</h2>
      </div>
      
      <div className="customize-menu">
        <button className={`nav-item ${isMemoryActive ? 'active' : ''}`} onClick={() => onNavigate('customize')}>
          <BrainCircuit size={18} />
          <span>Memory</span>
        </button>
        <button className={`nav-item ${isSkillsActive ? 'active' : ''}`} onClick={() => onNavigate('skills')}>
          <Sparkles size={18} />
          <span>Skills</span>
        </button>
      </div>
    </aside>
  )
}

export default CustomizePanel

import { ArrowLeft, BrainCircuit } from 'lucide-react'
import './CustomizePanel.css'

function CustomizePanel({ onClose, onNavigate }) {
  return (
    <aside className="customize-panel">
      <div className="customize-header">
        <button className="back-btn" onClick={onClose}>
          <ArrowLeft size={20} />
        </button>
        <h2>Customize</h2>
      </div>
      
      <div className="customize-menu">
        <button className="nav-item active" onClick={() => onNavigate('customize')}>
          <BrainCircuit size={18} />
          <span>Memory</span>
        </button>
      </div>
    </aside>
  )
}

export default CustomizePanel

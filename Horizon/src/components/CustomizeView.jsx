import { BrainCircuit, Info, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { chatAPI } from '../services/api'
import './CustomizeView.css'

function CustomizeView() {
  const [memoryEnabled, setMemoryEnabled] = useState(true)
  const [memories, setMemories] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [isUpdating, setIsUpdating] = useState(false)
  const [error, setError] = useState('')

  const loadMemoryState = async () => {
    setIsLoading(true)
    setError('')
    try {
      const [settings, memoryResponse] = await Promise.all([
        chatAPI.getMemorySettings(),
        chatAPI.getMemories(),
      ])
      setMemoryEnabled(Boolean(settings.enabled))
      setMemories(memoryResponse.memories || [])
    } catch (err) {
      setError(err.message || 'Failed to load memories.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadMemoryState()
  }, [])

  const handleToggleMemory = async () => {
    if (isUpdating) return
    const next = !memoryEnabled
    setIsUpdating(true)
    setError('')
    try {
      const response = await chatAPI.updateMemorySettings(next)
      setMemoryEnabled(Boolean(response.enabled))
    } catch (err) {
      setError(err.message || 'Failed to update memory setting.')
    } finally {
      setIsUpdating(false)
    }
  }

  const handleDeleteMemory = async (memoryId) => {
    try {
      await chatAPI.deleteMemory(memoryId)
      setMemories((prev) => prev.filter((item) => item.id !== memoryId))
    } catch (err) {
      setError(err.message || 'Failed to delete memory item.')
    }
  }

  const handleClearMemory = async () => {
    try {
      await chatAPI.clearMemories()
      setMemories([])
    } catch (err) {
      setError(err.message || 'Failed to clear memory.')
    }
  }

  return (
    <div className="customize-view">
      <div className="customize-content">
        <div className="memory-header">
          <div className="memory-icon-wrapper">
            <BrainCircuit size={32} />
          </div>
          <h1 className="customize-title">Memory</h1>
          <p className="customize-subtitle">
            Horizon learns from your conversations to become more helpful over time.
          </p>
        </div>

        <div className="memory-settings">
          <div className="settings-card">
            <div className="settings-row">
              <div className="settings-info">
                <h3>Enable Memory</h3>
                <p>Allow Horizon to remember details from your conversations to provide personalized responses.</p>
              </div>
              <button 
                className={`toggle-btn ${memoryEnabled ? 'active' : ''}`}
                onClick={handleToggleMemory}
                disabled={isUpdating}
              >
                <div className="toggle-thumb" />
              </button>
            </div>

            <div className="settings-divider" />

            <div className="settings-row">
              <div className="settings-info">
                <h3>Manage Memory</h3>
                <p>View or delete specific things Horizon has learned about you.</p>
              </div>
              <span className="memory-count-chip">{memories.length} saved</span>
            </div>

            <div className="settings-divider" />

            <div className="settings-row">
              <div className="settings-info">
                <h3 className="danger-text">Clear all memories</h3>
                <p>This will permanently delete everything Horizon has learned about you across all conversations.</p>
              </div>
              <button className="danger-btn" onClick={handleClearMemory} disabled={memories.length === 0}>
                <Trash2 size={16} />
                Clear Memory
              </button>
            </div>
          </div>

          <div className="memory-list-card">
            {isLoading ? (
              <p className="memory-empty">Loading memories...</p>
            ) : memories.length === 0 ? (
              <p className="memory-empty">No memories saved yet.</p>
            ) : (
              memories.map((item) => (
                <div key={item.id} className="memory-item-row">
                  <div className="memory-item-content">
                    <div className="memory-item-key">{item.key}</div>
                    <div className="memory-item-value">{item.value}</div>
                  </div>
                  <button className="memory-delete-btn" onClick={() => handleDeleteMemory(item.id)}>
                    <Trash2 size={14} />
                  </button>
                </div>
              ))
            )}
          </div>

          <div className="memory-info-box">
            <Info size={16} />
            <p>Memory is stored securely and is only used to improve your experience. You can turn it off or clear it at any time.</p>
          </div>

          {error && <div className="memory-error">{error}</div>}
        </div>
      </div>
    </div>
  )
}

export default CustomizeView

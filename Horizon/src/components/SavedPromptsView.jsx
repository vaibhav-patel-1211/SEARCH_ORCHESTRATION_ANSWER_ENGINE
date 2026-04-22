import { useState, useEffect, useCallback } from 'react'
import { Bookmark, Plus, Trash2, Copy, Check, Search, Terminal, MessageSquarePlus } from 'lucide-react'
import { chatAPI } from '../services/api'
import { buildPromptCommand } from '../services/promptCommands'
import './SavedPromptsView.css'

function SavedPromptsView({ onInsert, showToast }) {
  const [prompts, setPrompts] = useState([])
  const [isAdding, setIsAdding] = useState(false)
  const [newName, setNewName] = useState('')
  const [newContent, setNewContent] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [copiedId, setCopiedId] = useState(null)

  const loadPrompts = useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await chatAPI.getSavedPrompts()
      setPrompts(data)
    } catch (err) {
      console.error('Failed to load prompts:', err)
      showToast('Failed to load prompts', 'error')
    } finally {
      setIsLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    loadPrompts()
  }, [loadPrompts])

  const handleCreate = async () => {
    if (!newName.trim() || !newContent.trim()) return
    try {
      await chatAPI.createSavedPrompt(newName.trim(), newContent.trim())
      setNewName('')
      setNewContent('')
      setIsAdding(false)
      showToast('Prompt saved successfully!', 'success')
      loadPrompts()
    } catch (err) {
      console.error('Failed to create prompt:', err)
      showToast('Failed to save prompt. Name might be taken.', 'error')
    }
  }

  const handleDelete = async (id) => {
    // Note: In a full polish, we would use a custom confirmation modal here too,
    // but for now we'll just use the toast for the result.
    if (!confirm('Are you sure you want to delete this prompt?')) return
    try {
      await chatAPI.deleteSavedPrompt(id)
      showToast('Prompt deleted', 'success')
      loadPrompts()
    } catch (err) {
      console.error('Failed to delete prompt:', err)
      showToast('Failed to delete prompt', 'error')
    }
  }

  const handleCopyCommand = (name) => {
    const cmd = buildPromptCommand(name)
    if (!cmd) return
    navigator.clipboard.writeText(cmd)
    setCopiedId(name)
    showToast('Command copied to clipboard!', 'success')
    setTimeout(() => setCopiedId(null), 2000)
  }

  const handleUseInChat = (prompt) => {
    const command = buildPromptCommand(prompt?.name)
    onInsert(command || prompt?.content || '')
    showToast('Inserted into chat', 'success')
  }

  const filteredPrompts = prompts.filter(p => 
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.content.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="prompts-view">
      <div className="prompts-container">
        <header className="prompts-header">
          <div className="header-left">
            <Bookmark size={28} className="header-icon" />
            <div>
              <h1>Saved Prompts</h1>
              <p>Store your favorite prompts and use them in chat with commands.</p>
            </div>
          </div>
          <button className="add-prompt-btn" onClick={() => setIsAdding(!isAdding)}>
            <Plus size={18} />
            <span>New Prompt</span>
          </button>
        </header>

        {isAdding && (
          <div className="add-prompt-card">
            <h3>Create New Saved Prompt</h3>
            <div className="form-group">
              <label>Name (Topic Name)</label>
              <input 
                type="text" 
                placeholder="e.g. CodeReview" 
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
              <small>You will use this as: {buildPromptCommand(newName || 'name')}</small>
            </div>
            <div className="form-group">
              <label>Prompt Content</label>
              <textarea 
                placeholder="Enter the full prompt text here..."
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
              />
            </div>
            <div className="form-actions">
              <button className="secondary-btn" onClick={() => setIsAdding(false)}>Cancel</button>
              <button className="primary-btn" onClick={handleCreate} disabled={!newName.trim() || !newContent.trim()}>Save Prompt</button>
            </div>
          </div>
        )}

        <div className="prompts-list-section">
          <div className="search-bar">
            <Search size={18} />
            <input 
              type="text" 
              placeholder="Search saved prompts..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div className="prompts-grid">
            {isLoading ? (
              <div className="loading-state">Loading prompts...</div>
            ) : filteredPrompts.length === 0 ? (
              <div className="empty-state">No prompts found.</div>
            ) : (
              filteredPrompts.map(prompt => (
                <div key={prompt.id} className="prompt-card">
                  <div className="prompt-card-header">
                    <h3>{prompt.name}</h3>
                    <div className="card-actions">
                      <button className="icon-btn highlight" onClick={() => handleUseInChat(prompt)} title="Use in Chat">
                        <MessageSquarePlus size={16} />
                      </button>
                      <button className="icon-btn" onClick={() => handleDelete(prompt.id)} title="Delete">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                  <p className="prompt-preview">{prompt.content}</p>
                  <div className="prompt-command-box">
                    <div className="command-text">
                      <Terminal size={14} />
                      <code>{buildPromptCommand(prompt.name)}</code>
                    </div>
                    <button className="copy-cmd-btn" onClick={() => handleCopyCommand(prompt.name)}>
                      {copiedId === prompt.name ? <Check size={14} /> : <Copy size={14} />}
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default SavedPromptsView

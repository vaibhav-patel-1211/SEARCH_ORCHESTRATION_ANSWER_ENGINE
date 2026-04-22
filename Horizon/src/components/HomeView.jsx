import { Paperclip, Globe, ArrowUp, Code, FileText, Lightbulb, Search, X } from 'lucide-react'
import { useRef, useState } from 'react'
import './HomeView.css'

function HomeView({
  onSendMessage,
  inputValue,
  setInputValue,
  pastedContent,
  onLargePaste,
  onClearPastedContent,
  longPasteThreshold = 220,
  onQuickStart,
  webSearchEnabled = false,
  onToggleWebSearch,
  onUploadFiles,
  isUploadingFiles = false,
  userName,
}) {
  const fileInputRef = useRef(null)
  const [isPastedPreviewOpen, setIsPastedPreviewOpen] = useState(false)
  const quickStarts = [
    { icon: <Code size={18} />, title: 'Write a script', desc: 'Write a TypeScript script that fetches data from an API and processes it.' },
    { icon: <FileText size={18} />, title: 'Analyze document', desc: 'Analyze this document and provide a comprehensive summary with key insights.' },
    { icon: <Lightbulb size={18} />, title: 'Brainstorm ideas', desc: 'Brainstorm 10 innovative product ideas for AI-powered tools in 2025.' },
    { icon: <Search size={18} />, title: 'Research topic', desc: 'Provide a comprehensive research overview on quantum computing and its applications.' },
  ]

  const handleFileClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = (event) => {
    const files = Array.from(event.target.files || [])
    if (files.length > 0 && typeof onUploadFiles === 'function') {
      onUploadFiles(files)
    }
    event.target.value = ''
  }

  const handleInputKeyDown = (event) => {
    if (event.key !== 'Enter') return
    if (event.shiftKey) return
    event.preventDefault()
    if (canSend) {
      onSendMessage()
    }
  }

  const hasPastedContent = Boolean(String(pastedContent || '').trim())
  const canSend = Boolean(inputValue.trim() || hasPastedContent)
  const pastedPreview = String(pastedContent || '').slice(0, 180)

  const handleInputPaste = (event) => {
    const pastedText = event.clipboardData?.getData('text') || ''
    if (pastedText.trim().length < longPasteThreshold) return
    event.preventDefault()
    onLargePaste?.(pastedText)
  }

  const openPastedPreview = () => {
    if (!hasPastedContent) return
    setIsPastedPreviewOpen(true)
  }

  return (
    <div className="home-view">
      <div className="home-header">
        <h1 className="greeting">Welcome, {userName || 'there'}</h1>
      </div>

      <div className="input-section">
        <div className="input-container">
          {hasPastedContent && (
            <div className="pasted-preview-wrapper">
              <div
                className="pasted-preview-card clickable"
                onClick={openPastedPreview}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    openPastedPreview()
                  }
                }}
                role="button"
                tabIndex={0}
                title="Open pasted content"
              >
                <div className="pasted-preview-text">{pastedPreview}</div>
                <div className="pasted-preview-footer">
                  <span className="pasted-preview-badge">PASTED</span>
                  <button
                    className="pasted-preview-clear"
                    onClick={(event) => {
                      event.stopPropagation()
                      onClearPastedContent()
                    }}
                    title="Clear pasted content"
                  >
                    <X size={12} />
                  </button>
                </div>
              </div>
            </div>
          )}
          <div className="input-row">
            <textarea
              className="chat-input"
              placeholder="How can I help you today? (Shift+Enter for new line)"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleInputKeyDown}
              onPaste={handleInputPaste}
              rows={3}
            />
          </div>
          <div className="input-actions">
            <div className="action-buttons">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                style={{ display: 'none' }}
                multiple
              />
              <button className="icon-btn" onClick={handleFileClick} disabled={isUploadingFiles}>
                <Paperclip size={18} />
              </button>
              <button
                className={`icon-btn ${webSearchEnabled ? 'active' : ''}`}
                onClick={onToggleWebSearch}
                title={webSearchEnabled ? 'Web search on' : 'Web search off'}
              >
                <Globe size={18} />
              </button>
            </div>
            <div className="right-actions">
              <button
                className={`send-btn ${canSend ? 'active' : ''}`}
                onClick={() => onSendMessage()}
                disabled={!canSend}
              >
                <ArrowUp size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {isPastedPreviewOpen && hasPastedContent && (
        <div className="pasted-panel-backdrop" onClick={() => setIsPastedPreviewOpen(false)}>
          <aside className="pasted-panel" onClick={(event) => event.stopPropagation()}>
            <div className="pasted-panel-header">
              <div className="pasted-panel-header-text">
                <div className="pasted-panel-title">Pasted Content</div>
                <div className="pasted-panel-subtitle">Text preview</div>
              </div>
              <button
                className="pasted-panel-close"
                onClick={() => setIsPastedPreviewOpen(false)}
                title="Close preview"
              >
                <X size={16} />
              </button>
            </div>
            <div className="pasted-panel-content">
              <article className="pasted-panel-page">
                <pre><code>{String(pastedContent || '')}</code></pre>
              </article>
            </div>
          </aside>
        </div>
      )}

      <div className="quick-start-section">
        <div className="section-label">QUICK START</div>
        <div className="quick-start-grid">
          {quickStarts.map((item, idx) => (
            <button
              key={idx}
              className="qs-card"
              onClick={() => onQuickStart(item.desc)}
            >
              <div className="qs-icon">{item.icon}</div>
              <div className="qs-content">
                <div className="qs-title">{item.title}</div>
                <div className="qs-desc">{item.desc}</div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

export default HomeView

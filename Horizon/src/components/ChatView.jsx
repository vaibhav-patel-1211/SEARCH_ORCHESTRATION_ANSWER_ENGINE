/**
 * ChatView.jsx - Main chat interface component.
 * 
 * Handles:
 * - Message display with markdown rendering (ReactMarkdown + GFM)
 * - Real-time streaming text display
 * - File upload UI (drag & drop, progress bar)
 * - Input area with auto-resize textarea
 * - Web search toggle
 * - Skill selection dropdown
 * - File preview modal
 * - Copy/export actions on messages
 * - Auto-scroll to bottom on new messages
 * 
 * Receives messages and callbacks from App.jsx (parent).
 * The actual WebSocket logic lives in App.jsx; this component
 * only handles the visual presentation.
 */

import { Paperclip, Globe, ArrowUp, Copy, RotateCcw, Download, Loader2, Square, X, Check, Info, Zap, Monitor, Smartphone, Tablet, RefreshCw, FileText } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { API_BASE, chatAPI } from '../services/api'
import './ChatView.css'

function ChatView({
  messages,
  onSendMessage,
  inputValue,
  setInputValue,
  pastedContent,
  onLargePaste,
  onClearPastedContent,
  longPasteThreshold = 220,
  isLoading,
  onStopGenerating,
  onRetry,
  onUploadFiles,
  onRemoveFile,
  onRemoveAllFiles,
  onOpenFilePreview,
  webSearchEnabled,
  onToggleWebSearch,
  uploadedFiles,
  isUploadingFiles,
  uploadProgress,
  removingFileIds,
  openingFileIds,
  showToast,
  skills = [],
  selectedSkillId,
  onSelectSkill,
}) {
  const messagesEndRef = useRef(null)
  const chatContentRef = useRef(null)
  const fileInputRef = useRef(null)
  const skillDropdownRef = useRef(null)
  const textareaRef = useRef(null)
  const [isAtBottom, setIsAtBottom] = useState(true)
  const [isFilePreviewOpen, setIsFilePreviewOpen] = useState(false)
  const [isFilePreviewLoading, setIsFilePreviewLoading] = useState(false)
  const [isPastedPreviewOpen, setIsPastedPreviewOpen] = useState(false)
  const [filePreview, setFilePreview] = useState(null)
  const [skillDropdownOpen, setSkillDropdownOpen] = useState(false)
  const [previewMsg, setPreviewMsg] = useState(null)
  const [previewDevice, setPreviewDevice] = useState('desktop')
  const [previewKey, setPreviewKey] = useState(0)
  const [exportingIdx, setExportingIdx] = useState(null)

  const selectedSkill = skills.find((s) => s.id === selectedSkillId) || null

  // Close skill dropdown on outside click
  useEffect(() => {
    if (!skillDropdownOpen) return
    const handler = (e) => {
      if (skillDropdownRef.current && !skillDropdownRef.current.contains(e.target)) {
        setSkillDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [skillDropdownOpen])

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [inputValue])
  const openingFileIdSet = new Set(openingFileIds || [])
  const hasPastedContent = Boolean(String(pastedContent || '').trim())
  const canSend = Boolean(inputValue.trim() || hasPastedContent)
  const pastedPreview = String(pastedContent || '').slice(0, 180)
  const previewPages = Array.isArray(filePreview?.pages) ? filePreview.pages : []
  const previewPageCount = Number(filePreview?.page_count || previewPages.length || 0)

  // Handle scroll detection
  const handleScroll = () => {
    if (!chatContentRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = chatContentRef.current
    const atBottom = scrollHeight - scrollTop - clientHeight < 100
    setIsAtBottom(atBottom)
  }

  useEffect(() => {
    if (!isAtBottom) return
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading, isAtBottom])

  const handleSend = () => {
    if (canSend) {
      onSendMessage()
    }
  }

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text)
    showToast('Copied to clipboard', 'success')
  }

  const handleAction = (action) => {
    showToast(`${action} coming soon`, 'info')
  }

  const handleFileClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = (e) => {
    if (e.target.files) {
      onUploadFiles(Array.from(e.target.files))
      e.target.value = ''
    }
  }

  const handleInputPaste = (event) => {
    const pastedText = event.clipboardData?.getData('text') || ''
    if (pastedText.trim().length < longPasteThreshold) return
    event.preventDefault()
    onLargePaste?.(pastedText)
  }

  const closeFilePreview = () => {
    setIsFilePreviewOpen(false)
    setIsFilePreviewLoading(false)
  }

  const openPastedPreview = () => {
    if (!hasPastedContent) return
    setIsPastedPreviewOpen(true)
  }

  const handleOpenUploadedFilePreview = async (file) => {
    if (!file || typeof onOpenFilePreview !== 'function') return
    if (openingFileIdSet.has(file.file_id)) return

    setIsFilePreviewOpen(true)
    setIsFilePreviewLoading(true)
    setFilePreview({
      file_id: file.file_id,
      filename: file.filename,
      content: '',
      chunk_count: file.chunk_count ?? 0,
    })

    const preview = await onOpenFilePreview(file)
    if (preview) {
      setFilePreview(preview)
      setIsFilePreviewLoading(false)
      return
    }

    closeFilePreview()
  }

  const handleRemoveUploadedFile = (fileId) => {
    if (!fileId) return
    if (filePreview?.file_id === fileId) {
      setFilePreview(null)
      closeFilePreview()
    }
    onRemoveFile(fileId)
  }

  const renderContextBadge = (activeFiles) => {
    if (!Array.isArray(activeFiles) || activeFiles.length === 0) return null
    const visibleFiles = activeFiles.slice(0, 3)
    const hiddenCount = activeFiles.length - visibleFiles.length

    return (
      <div className="message-context-badge">
        <span className="context-label">Context</span>
        {visibleFiles.map((fileName, index) => (
          <span key={`${fileName}-${index}`} className="context-file-chip" title={fileName}>
            {fileName}
          </span>
        ))}
        {hiddenCount > 0 && <span className="context-file-chip">+{hiddenCount} more</span>}
      </div>
    )
  }

  const resolveBackendUrl = (path) => {
    if (!path) return null
    if (/^https?:\/\//i.test(path)) return path
    return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
  }

  const getFileExtension = (filename) => {
    const value = String(filename || '')
    const lastDot = value.lastIndexOf('.')
    if (lastDot <= 0 || lastDot === value.length - 1) return 'FILE'
    return value.slice(lastDot + 1).toUpperCase()
  }

  const normalizeCitationLinks = (content) => {
    const raw = String(content || '')
    const segments = raw.split(/(```[\s\S]*?```)/g)
    return segments
      .map((segment) =>
        segment.startsWith('```')
          ? segment
          : segment.replace(/\[(https?:\/\/[^\]\s]+)\](?!\()/gi, (_, url) => `[${url}](${url})`),
      )
      .join('')
  }

  const thinkingLabelByName = {
    query_understanding: 'Query understanding',
    search_queries: 'Query expansion',
    web_search: 'Web search',
    retrieval_route: 'Retrieval route',
    retrieval_sources: 'Source retrieval',
    skill_match: 'Skill match',
  }

  const renderThinkingPayload = (step) => {
    const payload = step?.payload && typeof step.payload === 'object' ? step.payload : {}

    if (step.name === 'query_understanding') {
      const subQueries = Array.isArray(payload.sub_queries) ? payload.sub_queries : []
      return (
        <div className="thinking-step-body">
          <div className="thinking-meta-line">
            <span><strong>Intent:</strong> {payload.intent || 'unknown'}</span>
            {typeof payload.research_enabled === 'boolean' && (
              <span><strong>Web search:</strong> {payload.research_enabled ? 'On' : 'Off'}</span>
            )}
          </div>
          {payload.reasoning && <p className="thinking-reasoning">{payload.reasoning}</p>}
          {subQueries.length > 0 && (
            <ul className="thinking-list">
              {subQueries.slice(0, 4).map((query, index) => (
                <li key={`${query}-${index}`}>{query}</li>
              ))}
            </ul>
          )}
        </div>
      )
    }

    if (step.name === 'search_queries') {
      const queries = Array.isArray(payload.queries) ? payload.queries : []
      return (
        <div className="thinking-step-body">
          <div className="thinking-chip-list">
            {queries.slice(0, 6).map((query, index) => (
              <span key={`${query}-${index}`} className="thinking-chip">{query}</span>
            ))}
          </div>
        </div>
      )
    }

    if (step.name === 'web_search') {
      return (
        <div className="thinking-step-body">
          <div className="thinking-meta-line">
            <span><strong>Queries:</strong> {payload.query_count ?? 0}</span>
            <span><strong>Sources:</strong> {payload.url_count ?? 0}</span>
          </div>
        </div>
      )
    }

    if (step.name === 'retrieval_route') {
      return (
        <div className="thinking-step-body">
          <div className="thinking-meta-line">
            <span><strong>Route:</strong> {payload.route_source || 'web'}</span>
            {typeof payload.confidence === 'number' && (
              <span><strong>Confidence:</strong> {Math.round(payload.confidence * 100)}%</span>
            )}
          </div>
          {payload.reason && <p className="thinking-reasoning">{payload.reason}</p>}
        </div>
      )
    }

    if (step.name === 'retrieval_sources') {
      return (
        <div className="thinking-step-body">
          <div className="thinking-meta-line">
            <span><strong>Sources:</strong> {step?.payload?.source_count ?? 0}</span>
          </div>
        </div>
      )
    }

    if (step.name === 'skill_match') {
      const skills = Array.isArray(payload.skills) ? payload.skills : []
      return (
        <div className="thinking-step-body">
          <div className="thinking-chip-list">
            {skills.length > 0 ? (
              skills.map((skill, index) => (
                <span key={`${skill?.id || skill?.name || index}`} className="thinking-chip">
                  {skill?.name || 'Skill'}
                </span>
              ))
            ) : (
              <span className="thinking-chip">Matched skill</span>
            )}
          </div>
        </div>
      )
    }

    return null
  }

  const PREVIEW_LANGS = new Set(['html', 'css', 'js', 'javascript', 'jsx', 'tsx', 'react', 'typescript', 'ts'])

  const extractCodeBlocks = (content) => {
    const blocks = []
    const re = /```([\w-]*)\n([\s\S]*?)```/g
    let m
    while ((m = re.exec(content)) !== null) {
      const lang = (m[1] || '').toLowerCase()
      blocks.push({ lang, code: m[2] })
    }
    return blocks
  }

  const buildPreviewSrcdoc = (content) => {
    const blocks = extractCodeBlocks(content)
    let html = '', css = '', js = ''
    let isReact = false

    for (const { lang, code } of blocks) {
      if (lang === 'html') html = code
      else if (lang === 'css') css = code
      else if (['js', 'javascript'].includes(lang)) js = code
      else if (['jsx', 'tsx', 'react'].includes(lang)) { js = code; isReact = true }
    }

    // If single block with no explicit lang, try to detect
    if (!html && !js && blocks.length === 1) {
      const { lang, code } = blocks[0]
      if (!lang || PREVIEW_LANGS.has(lang)) {
        if (code.includes('<') && code.includes('>')) html = code
        else js = code
      }
    }

    const babelScript = isReact
      ? `<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>`
      : ''
    const scriptType = isReact ? 'type="text/babel"' : ''
    const reactImport = isReact
      ? `<script src="https://unpkg.com/react@18/umd/react.development.js"></script>
         <script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>`
      : ''

    return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
${reactImport}
${babelScript}
<style>*{box-sizing:border-box}body{margin:0;font-family:sans-serif}${css}</style>
</head>
<body>
${html || '<div id="root"></div>'}
${js ? `<script ${scriptType}>${js}</script>` : ''}
</body>
</html>`
  }

  const msgHasPreview = (content) => {
    const blocks = extractCodeBlocks(content)
    return blocks.some(({ lang }) => PREVIEW_LANGS.has(lang)) ||
      (blocks.length === 1 && !blocks[0].lang && blocks[0].code.includes('<'))
  }

  const renderSkillBadge = (msg) => {
    const steps = Array.isArray(msg?.thinkingSteps) ? msg.thinkingSteps : []
    const skillStep = steps.find((s) => s?.name === 'skill_match')
    if (!skillStep) return null
    const skillNames = (skillStep.payload?.skills || []).map((s) => s?.name).filter(Boolean)
    if (skillNames.length === 0) return null
    return (
      <div className="skill-used-badge">
        <span className="skill-used-label">Skill</span>
        {skillNames.map((name) => (
          <span key={name} className="skill-used-chip">{name}</span>
        ))}
      </div>
    )
  }

  const renderThinkingPanel = (msg) => {
    const steps = Array.isArray(msg?.thinkingSteps) ? msg.thinkingSteps : []
    if (steps.length === 0) return null

    const understandingStep = steps.find((step) => step?.name === 'query_understanding')
    const stepIntent = understandingStep?.payload?.intent
    const resolvedIntent =
      (typeof msg?.intent === 'string' && msg.intent) ||
      (typeof stepIntent === 'string' ? stepIntent : '')
    const hasSkillMatch = steps.some((step) => step?.name === 'skill_match')
    const showThinking = Boolean(msg?.researchEnabled) || resolvedIntent === 'coding' || hasSkillMatch
    if (!showThinking) return null
    if (resolvedIntent === 'general' && !hasSkillMatch) return null

    const codingMode = steps.some(
      (step) => step?.name === 'query_understanding' && step?.payload?.intent === 'coding',
    )

    return (
      <div className={`thinking-panel ${codingMode ? 'coding' : ''}`}>
        <div className="thinking-panel-title">{codingMode ? 'Coding thinking' : 'Thinking'}</div>
        {steps.map((step, index) => (
          <div key={`${step.name}-${index}`} className="thinking-step">
            <div className="thinking-step-header">
              <span className="thinking-step-name">{thinkingLabelByName[step.name] || step.name}</span>
              {step.status && <span className={`thinking-status ${step.status}`}>{step.status}</span>}
            </div>
            {renderThinkingPayload(step)}
          </div>
        ))}
      </div>
    )
  }

  const buildResearchProgress = (msg) => {
    const steps = Array.isArray(msg?.thinkingSteps) ? msg.thinkingSteps : []
    const documents = Array.isArray(msg?.documents) ? msg.documents : []
    const understandingStep = steps.find((step) => step?.name === 'query_understanding')
    const stepIntent = understandingStep?.payload?.intent
    const resolvedIntent =
      (typeof msg?.intent === 'string' && msg.intent) ||
      (typeof stepIntent === 'string' ? stepIntent : '')
    const showResearchProgress = Boolean(msg?.researchEnabled) && resolvedIntent !== 'general' && resolvedIntent !== 'coding'
    if (!showResearchProgress) return null

    const completedStatuses = new Set(['completed', 'generated', 'selected'])
    const stepsByName = new Map(steps.map((step) => [step.name, step]))

    const stageOrder = [
      { key: 'analyze', label: 'Understanding query' },
      { key: 'plan', label: 'Planning search' },
      { key: 'search', label: 'Searching web' },
      { key: 'retrieve', label: 'Reading sources' },
      { key: 'compose', label: 'Generating answer' },
    ]

    const completed = new Set()
    if (completedStatuses.has(stepsByName.get('query_understanding')?.status)) completed.add('analyze')
    if (completedStatuses.has(stepsByName.get('search_queries')?.status)) completed.add('plan')
    if (completedStatuses.has(stepsByName.get('web_search')?.status)) completed.add('search')

    const routeComplete = completedStatuses.has(stepsByName.get('retrieval_route')?.status)
    const retrievalComplete =
      completedStatuses.has(stepsByName.get('retrieval_sources')?.status) || documents.length > 0
    if (routeComplete || retrievalComplete) completed.add('retrieve')

    if (msg?.hasAnswerStarted || String(msg?.content || '').trim()) completed.add('compose')

    const completedCount = stageOrder.filter((stage) => completed.has(stage.key)).length
    const firstPending = stageOrder.find((stage) => !completed.has(stage.key))
    const activeLabel = !msg?.isStreaming
      ? 'Research complete'
      : firstPending?.label || 'Finalizing answer'

    let progress = Math.round((completedCount / stageOrder.length) * 100)
    if (msg?.isStreaming && !msg?.hasAnswerStarted) progress = Math.max(progress, 18)
    if (msg?.isStreaming && msg?.hasAnswerStarted) progress = Math.max(progress, 86)
    if (!msg?.isStreaming && String(msg?.content || '').trim()) progress = 100

    return {
      label: activeLabel,
      progress,
      stageOrder,
      completed,
      animating: Boolean(msg?.isStreaming),
    }
  }

  const renderResearchProgress = (progressState) => (
    <div className="research-progress">
      <div className="research-progress-head">
        <span className="research-progress-title">Research mode</span>
        <span className="research-progress-percent">{progressState.progress}%</span>
      </div>
      <div className="research-progress-track">
        <div
          className={`research-progress-fill ${progressState.animating ? 'animating' : ''}`}
          style={{ width: `${progressState.progress}%` }}
        />
      </div>
      <div className="research-progress-label">{progressState.label}</div>
      <div className="research-progress-stages">
        {progressState.stageOrder.map((stage) => (
          <span
            key={stage.key}
            className={`research-stage ${progressState.completed.has(stage.key) ? 'done' : ''}`}
          >
            {stage.label}
          </span>
        ))}
      </div>
    </div>
  )

  return (
    <div className="chat-view">
      <div 
        className="chat-content" 
        ref={chatContentRef}
        onScroll={handleScroll}
      >
        {messages.map((msg, idx) => {
          const progressState = msg.role === 'assistant' ? buildResearchProgress(msg) : null
          return (
            <div 
              key={idx} 
              className={`${msg.role}-message-wrapper ${msg.role === 'assistant' && idx === messages.length - 1 && isLoading ? 'streaming' : ''} ${msg.role === 'assistant' && idx === messages.length - 1 ? 'fade-in' : ''}`}
            >
              <div className={`${msg.role}-message`}>
                {renderContextBadge(msg.activeFiles)}
                {msg.role === 'assistant' && renderSkillBadge(msg)}
                {msg.role === 'assistant' && progressState && renderResearchProgress(progressState)}
                {msg.role === 'assistant' && renderThinkingPanel(msg)}
                <div className="message-text markdown-content">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: ({ href, children }) => {
                      if (!href) return <span>{children}</span>
                      return (
                        <a
                          className="citation-link"
                          href={href}
                          target="_blank"
                          rel="noreferrer noopener"
                          title={href}
                        >
                          {children}
                        </a>
                      )
                    },
                    pre: ({ children }) => {
                      const child = Array.isArray(children) ? children[0] : children
                      const className = child?.props?.className || ''
                      const codeText = String(child?.props?.children ?? '').replace(/\n$/, '')
                      const languageMatch = /language-([\w-]+)/i.exec(className)
                      const language = (languageMatch?.[1] || 'text').toUpperCase()

                      return (
                        <div className="vscode-code-block">
                          <div className="vscode-code-header">
                            <span className="vscode-code-lang">{language}</span>
                            <button
                              type="button"
                              className="vscode-copy-btn"
                              onClick={() => handleCopy(codeText)}
                            >
                              Copy
                            </button>
                          </div>
                          <pre className={className}>
                            <code>{codeText}</code>
                          </pre>
                        </div>
                      )
                    },
                  }}
                >
                  {normalizeCitationLinks(msg.content)}
                </ReactMarkdown>

                {msg.diagramUrl && (
                  <div className="message-diagram">
                    <img src={resolveBackendUrl(msg.diagramUrl)} alt="Generated diagram" loading="lazy" />
                  </div>
                )}

                {msg.downloadUrl && (
                  <a className="download-btn" href={resolveBackendUrl(msg.downloadUrl)} target="_blank" rel="noreferrer">
                    <Download size={14} /> Download PDF Report
                  </a>
                )}

                {msg.role === 'assistant' && msg.isStreaming && (
                  <div className="loading-indicator" style={{ marginTop: msg.content ? '16px' : '0' }}>
                    <Loader2 size={18} className="spin" />
                    <span>
                      {msg.hasAnswerStarted
                        ? 'Generating answer...'
                        : msg?.researchEnabled
                          ? 'Researching...'
                          : 'Thinking...'}
                    </span>
                  </div>
                )}
              </div>
              
              {msg.role === 'assistant' && !msg.isStreaming && (
                <div className="message-actions">
                  <button className="icon-btn" onClick={() => handleCopy(msg.content)} title="Copy"><Copy size={14} /></button>
                  <button className="icon-btn" onClick={() => onRetry ? onRetry(idx) : handleAction('Retry')} title="Retry"><RotateCcw size={14} /></button>
                  {msgHasPreview(msg.content) && (
                    <button className="icon-btn" onClick={() => setPreviewMsg(msg)} title="Preview"><Monitor size={14} /></button>
                  )}
                  <button
                    className="icon-btn"
                    disabled={exportingIdx === idx}
                    title="Export as PDF"
                    onClick={async () => {
                      setExportingIdx(idx)
                      try {
                        const { download_url } = await chatAPI.exportPdf(msg.content, messages.find((m, i) => i < idx && m.role === 'user')?.content?.slice(0, 60) || 'Report')
                        const a = document.createElement('a')
                        a.href = `${API_BASE}${download_url}`
                        a.download = download_url.split('/').pop()
                        document.body.appendChild(a)
                        a.click()
                        document.body.removeChild(a)
                      } catch (e) {
                        showToast('PDF export failed', 'info')
                      } finally {
                        setExportingIdx(null)
                      }
                    }}
                  >
                    {exportingIdx === idx ? <Loader2 size={14} className="spin" /> : <FileText size={14} />}
                  </button>
                </div>
              )}
            </div>
            </div>
          )
        })}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-container">
        <div className="chat-input-wrapper">
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
          {(uploadedFiles.length > 0 || isUploadingFiles) && (
            <div className="attached-files">
              {isUploadingFiles && (
                <div className="upload-progress-box">
                  <div className="upload-progress-row">
                    <span>Uploading files</span>
                    <span>{Math.max(1, uploadProgress || 0)}%</span>
                  </div>
                  <div className="upload-progress-track">
                    <div
                      className="upload-progress-fill"
                      style={{ width: `${Math.max(5, uploadProgress || 0)}%` }}
                    />
                  </div>
                </div>
              )}
              {uploadedFiles.length > 0 && (
                <button
                  className="remove-file"
                  onClick={onRemoveAllFiles}
                  disabled={isLoading || isUploadingFiles}
                  title="Remove all files"
                >
                  Remove all
                </button>
              )}
              {uploadedFiles.map((file) => (
                <div key={file.file_id} className="file-chip">
                  <span
                    className="file-name"
                    onClick={() => !openingFileIdSet.has(file.file_id) && handleOpenUploadedFilePreview(file)}
                  >
                    {openingFileIdSet.has(file.file_id) ? `Opening ${file.filename}...` : file.filename}
                  </span>
                  <button 
                    className="remove-file" 
                    onClick={() => handleRemoveUploadedFile(file.file_id)}
                    disabled={removingFileIds.includes(file.file_id)}
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="input-row">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              style={{ display: 'none' }}
              multiple
            />
            <button className="icon-btn" onClick={handleFileClick} disabled={isUploadingFiles}>
              <Paperclip size={20} />
            </button>
            <button 
              className={`icon-btn ${webSearchEnabled ? 'active' : ''}`}
              onClick={onToggleWebSearch}
            >
              <Globe size={20} />
            </button>
            {skills.length > 0 && (
              <div className="skill-selector" ref={skillDropdownRef}>
                <button
                  className={`icon-btn ${selectedSkillId ? 'active' : ''}`}
                  onClick={() => setSkillDropdownOpen((prev) => !prev)}
                  title={selectedSkill ? `Skill: ${selectedSkill.name}` : 'Select skill'}
                >
                  <Zap size={20} />
                </button>
                {skillDropdownOpen && (
                  <div className="skill-dropdown">
                    <div
                      className={`skill-dropdown-item ${!selectedSkillId ? 'active' : ''}`}
                      onClick={() => { onSelectSkill(null); setSkillDropdownOpen(false) }}
                    >
                      <span>None</span>
                      {!selectedSkillId && <Check size={12} />}
                    </div>
                    {skills.filter((s) => s.enabled !== false).map((skill) => (
                      <div
                        key={skill.id}
                        className={`skill-dropdown-item ${selectedSkillId === skill.id ? 'active' : ''}`}
                        onClick={() => { onSelectSkill(skill.id); setSkillDropdownOpen(false) }}
                      >
                        <span>{skill.name}</span>
                        {selectedSkillId === skill.id && <Check size={12} />}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
            {selectedSkill && (
              <div className="active-skill-badge">
                <Zap size={11} />
                <span>{selectedSkill.name}</span>
                <button
                  className="active-skill-clear"
                  onClick={() => onSelectSkill(null)}
                  title="Clear skill"
                >
                  <X size={10} />
                </button>
              </div>
            )}
            <textarea
              ref={textareaRef}
              placeholder="Ask anything..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onPaste={handleInputPaste}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              rows={1}
              style={{ overflowY: 'auto', maxHeight: '200px', resize: 'none' }}
            />
            <div className="input-actions">
              {isLoading ? (
                <button className="stop-btn" onClick={onStopGenerating}>
                  <Square size={14} fill="currentColor" />
                  <span>Stop</span>
                </button>
              ) : (
                <button 
                  className="send-btn" 
                  onClick={handleSend}
                  disabled={!canSend}
                >
                  <ArrowUp size={16} />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {isFilePreviewOpen && (
        <div className="file-preview-backdrop" onClick={closeFilePreview}>
          <aside className="file-preview-panel" onClick={(e) => e.stopPropagation()}>
            <div className="file-preview-header">
              <div className="file-preview-header-text">
                <div className="file-preview-title">{filePreview?.filename}</div>
                <div className="file-preview-subtitle">
                  {filePreview?.filename
                    ? `${getFileExtension(filePreview.filename)} preview${previewPageCount > 0 ? ` • ${previewPageCount} page${previewPageCount > 1 ? 's' : ''}` : ''}`
                    : 'Document preview'}
                </div>
              </div>
              <div className="file-preview-actions">
                <button
                  className="file-preview-icon-btn"
                  onClick={() => filePreview?.content && handleCopy(filePreview.content)}
                  disabled={!filePreview?.content}
                  title="Copy content"
                >
                  <Copy size={14} />
                </button>
                <button className="file-preview-icon-btn" onClick={closeFilePreview} title="Close preview">
                  <X size={16} />
                </button>
              </div>
            </div>
            <div className="file-preview-content">
              {isFilePreviewLoading ? (
                <div className="file-preview-loading">
                  <Loader2 size={24} className="spin" />
                  <span>Loading file content...</span>
                </div>
              ) : getFileExtension(filePreview?.filename) === 'PDF' && filePreview?.file_path ? (
                <div className="file-preview-pdf-wrapper">
                  <iframe
                    src={`${resolveBackendUrl(filePreview.file_path)}#toolbar=0`}
                    title={filePreview.filename}
                    className="file-preview-pdf-iframe"
                  />
                </div>
              ) : previewPages.length > 0 ? (
                <div className="file-preview-document">
                  {previewPages.map((page, index) => (
                    <article className="file-preview-page" key={`${page?.page_number || index}-${index}`}>
                      <h4>{`Page ${page?.page_number ?? index + 1}`}</h4>
                      <pre><code>{String(page?.content || '')}</code></pre>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="file-preview-document">
                  <article className="file-preview-page">
                    <pre><code>{filePreview?.content}</code></pre>
                  </article>
                </div>
              )}
            </div>
          </aside>
        </div>
      )}

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

      {previewMsg && (
        <div className="preview-backdrop" onClick={() => setPreviewMsg(null)}>
          <div className="preview-panel" onClick={(e) => e.stopPropagation()}>
            <div className="preview-panel-header">
              <div className="preview-header-left">
                <div className="preview-traffic-lights">
                  <span className="tl tl-red" onClick={() => setPreviewMsg(null)} />
                  <span className="tl tl-yellow" />
                  <span className="tl tl-green" />
                </div>
                <span className="preview-panel-title">Live Preview</span>
              </div>
              <div className="preview-device-switcher">
                <button className={`preview-device-btn ${previewDevice === 'desktop' ? 'active' : ''}`} onClick={() => setPreviewDevice('desktop')} title="Desktop"><Monitor size={14} /></button>
                <button className={`preview-device-btn ${previewDevice === 'tablet' ? 'active' : ''}`} onClick={() => setPreviewDevice('tablet')} title="Tablet"><Tablet size={14} /></button>
                <button className={`preview-device-btn ${previewDevice === 'mobile' ? 'active' : ''}`} onClick={() => setPreviewDevice('mobile')} title="Mobile"><Smartphone size={14} /></button>
              </div>
              <div className="preview-header-right">
                <button className="preview-device-btn" onClick={() => setPreviewKey((k) => k + 1)} title="Refresh"><RefreshCw size={13} /></button>
                <button className="preview-device-btn" onClick={() => setPreviewMsg(null)} title="Close"><X size={15} /></button>
              </div>
            </div>
            <div className="preview-canvas-area">
              <div className={`preview-frame-wrap preview-${previewDevice}`}>
                <iframe
                  key={previewKey}
                  className="preview-iframe"
                  sandbox="allow-scripts allow-same-origin"
                  srcDoc={buildPreviewSrcdoc(previewMsg.content)}
                  title="Live Preview"
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ChatView

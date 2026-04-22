import { useEffect, useRef, useState } from 'react'
import Sidebar from './components/Sidebar'
import CustomizePanel from './components/CustomizePanel'
import TopBar from './components/TopBar'
import HomeView from './components/HomeView'
import ChatView from './components/ChatView'
import SkillsView from './components/SkillsView'
import CustomizeView from './components/CustomizeView'
import PromptOptimizerView from './components/PromptOptimizerView'
import SavedPromptsView from './components/SavedPromptsView'
import Login from './components/login'
import Signup from './components/signup'
import { AUTH_SESSION_EXPIRED, authAPI, chatAPI, documentAPI, wsChatAPI } from './services/api'
import { buildPromptCommand, expandPromptCommands, toPromptCommandKey } from './services/promptCommands'
import { Check, Info } from 'lucide-react'
import './App.css'

const LONG_PASTE_THRESHOLD = 220

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(authAPI.isAuthenticated())
  const [authMode, setAuthMode] = useState('login') // 'login' | 'signup'
  const [activeView, setActiveView] = useState('home')
  const [isCustomizing, setIsCustomizing] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [messages, setMessages] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [pastedContent, setPastedContent] = useState('')
  const [activeChatId, setActiveChatId] = useState(null)
  const [recents, setRecents] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState([])
  const [isUploadingFiles, setIsUploadingFiles] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [removingFileIds, setRemovingFileIds] = useState([])
  const [openingFileIds, setOpeningFileIds] = useState([])
  const [savedPrompts, setSavedPrompts] = useState([])
  const [webSearchEnabled, setWebSearchEnabled] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [suggestionIndex, setSuggestionIndex] = useState(0)
  const [toast, setToast] = useState(null)
  const userEmail = authAPI.getUserEmail() || ''
  const showToast = (message, type = 'info') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3000)
  }
  const userName = authAPI.getUserName() || (userEmail ? userEmail.split('@')[0] : 'User')
  const wsRef = useRef(null)
  const activeRequestIdRef = useRef(null)
  const activeAssistantIndexRef = useRef(null)
  const activeChatIdRef = useRef(null)

  const resetSessionState = () => {
    setActiveView('home')
    setMessages([])
    setRecents([])
    setActiveChatId(null)
    activeChatIdRef.current = null
    setInputValue('')
    setPastedContent('')
    setIsLoading(false)
    setUploadedFiles([])
    setIsUploadingFiles(false)
    setUploadProgress(0)
    setRemovingFileIds([])
    setOpeningFileIds([])
    activeRequestIdRef.current = null
    activeAssistantIndexRef.current = null
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }

  const isAuthFailure = (err) => {
    if (!(err instanceof Error)) return false
    return err.message === AUTH_SESSION_EXPIRED || err.message === 'Missing auth token'
  }

  const handleSessionExpired = () => {
    authAPI.logout()
    setIsAuthenticated(false)
    resetSessionState()
  }

  useEffect(() => {
    if (isAuthenticated) {
      loadSessions()
      loadSavedPrompts()
    }
  }, [isAuthenticated]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    activeChatIdRef.current = activeChatId
  }, [activeChatId])

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [])

  const loadSessions = async () => {
    try {
      const data = await chatAPI.getSessions()
      const sessions = data.sessions || []
      setRecents(
        sessions.map((s) => ({
          id: s.id,
          title: s.title || 'New Chat',
          subtitle: s.messages?.[0]?.content?.slice(0, 50) || '',
        })),
      )
    } catch (err) {
      if (isAuthFailure(err)) {
        handleSessionExpired()
        return
      }
      console.error('Failed to load sessions:', err)
    }
  }

  const loadSavedPrompts = async () => {
    try {
      const data = await chatAPI.getSavedPrompts()
      setSavedPrompts(data)
    } catch (err) {
      if (isAuthFailure(err)) {
        handleSessionExpired()
        return
      }
      console.error('Failed to load saved prompts:', err)
    }
  }

  const handleNavigate = async (view) => {
    if (view === 'home') {
      setActiveView('home')
      setMessages([])
      setActiveChatId(null)
      activeChatIdRef.current = null
      setUploadedFiles([])
      setUploadProgress(0)
      setRemovingFileIds([])
      setOpeningFileIds([])
      setIsCustomizing(false)
    } else if (view === 'skills') {
      setActiveView('skills')
    } else if (view === 'optimizer') {
      setActiveView('optimizer')
      setIsCustomizing(false)
    } else if (view === 'prompts') {
      setActiveView('prompts')
      setIsCustomizing(false)
      loadSavedPrompts()
    } else {
      setActiveView('chat')
      setActiveChatId(view)
      activeChatIdRef.current = view
      setIsCustomizing(false)
      try {
        const session = await chatAPI.getSession(view)
        const fileResponse = await chatAPI.getSessionFiles(view)
        setMessages(
          session.messages?.map((m) => ({
            role: m.role,
            content: m.content,
          })) || [],
        )
        setUploadedFiles(fileResponse.files || [])
        setUploadProgress(0)
        setRemovingFileIds([])
        setOpeningFileIds([])
      } catch (err) {
        if (isAuthFailure(err)) {
          handleSessionExpired()
          return
        }
        console.error('Failed to load session:', err)
        setMessages([])
        setUploadedFiles([])
        setUploadProgress(0)
        setRemovingFileIds([])
        setOpeningFileIds([])
      }
    }
  }

  const handleToggleCustomize = () => {
    if (!isCustomizing) {
      setActiveView('customize')
      setIsCustomizing(true)
    } else {
      setActiveView('home')
      setIsCustomizing(false)
    }
  }

  const buildRequestId = () => {
    if (window.crypto?.randomUUID) {
      return window.crypto.randomUUID()
    }
    return `req_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
  }

  const updateStreamingAssistant = (mutator) => {
    const assistantIndex = activeAssistantIndexRef.current
    if (assistantIndex === null || assistantIndex === undefined) return

    setMessages((prev) => {
      if (!prev[assistantIndex]) return prev
      const next = [...prev]
      next[assistantIndex] = mutator(next[assistantIndex])
      return next
    })
  }

  const clearStreamingState = () => {
    activeRequestIdRef.current = null
    activeAssistantIndexRef.current = null
    setIsLoading(false)
  }

  const bindSocketHandlers = (socket) => {
    socket.onmessage = (event) => {
      let data
      try {
        data = JSON.parse(event.data)
      } catch (err) {
        console.error('Invalid WS message:', err)
        return
      }

      const activeRequestId = activeRequestIdRef.current
      if (data.request_id && activeRequestId && data.request_id !== activeRequestId) {
        return
      }

      if (data.type === 'token') {
        updateStreamingAssistant((assistant) => ({
          ...assistant,
          content: `${assistant.content || ''}${data.content || ''}`,
          hasAnswerStarted: true,
        }))
        return
      }

      if (data.type === 'tool_call') {
        if (data.name === 'generation' && data.status === 'cancelled') {
          updateStreamingAssistant((assistant) => ({
            ...assistant,
            isStreaming: false,
          }))
          clearStreamingState()
          return
        }

        updateStreamingAssistant((assistant) => {
          const existingSteps = Array.isArray(assistant.thinkingSteps) ? assistant.thinkingSteps : []
          const nextStep = {
            name: data.name || 'step',
            status: data.status || 'updated',
            payload: data.payload && typeof data.payload === 'object' ? data.payload : {},
            updatedAt: Date.now(),
          }
          const index = existingSteps.findIndex((step) => step.name === nextStep.name)
          if (index === -1) {
            return {
              ...assistant,
              thinkingSteps: [...existingSteps, nextStep],
            }
          }
          const merged = [...existingSteps]
          merged[index] = { ...merged[index], ...nextStep }
          return {
            ...assistant,
            thinkingSteps: merged,
          }
        })
        return
      }

      if (data.type === 'retrieval') {
        updateStreamingAssistant((assistant) => {
          const existingSteps = Array.isArray(assistant.thinkingSteps) ? assistant.thinkingSteps : []
          const retrievalStep = {
            name: 'retrieval_sources',
            status: 'completed',
            payload: {
              source_count: Array.isArray(data.documents) ? data.documents.length : 0,
            },
            updatedAt: Date.now(),
          }
          const stepIndex = existingSteps.findIndex((step) => step.name === retrievalStep.name)
          const mergedSteps = [...existingSteps]
          if (stepIndex === -1) mergedSteps.push(retrievalStep)
          else mergedSteps[stepIndex] = { ...mergedSteps[stepIndex], ...retrievalStep }

          return {
            ...assistant,
            documents: data.documents || [],
            thinkingSteps: mergedSteps,
          }
        })
        return
      }

      if (data.type === 'final_answer') {
        updateStreamingAssistant((assistant) => ({
          ...assistant,
          content: data.content || assistant.content || '',
          intent: data.intent,
          activeFiles: Array.isArray(data.active_files) ? data.active_files : [],
          diagramUrl: data.diagram_url,
          downloadUrl: data.download_url,
          hasAnswerStarted: true,
          isStreaming: false,
        }))

        if (data.session_id && !activeChatIdRef.current) {
          setActiveChatId(data.session_id)
          activeChatIdRef.current = data.session_id
          loadSessions()
        }

        clearStreamingState()
        return
      }

      if (data.type === 'error') {
        if (data.code === 'unauthorized') {
          handleSessionExpired()
          return
        }
        updateStreamingAssistant((assistant) => ({
          ...assistant,
          content: assistant.content || `Error: ${data.message || 'Request failed.'}`,
          isStreaming: false,
        }))

        if (activeRequestIdRef.current) {
          clearStreamingState()
        }
      }
    }

    socket.onerror = (event) => {
      console.error('WebSocket error:', event)
    }

    socket.onclose = () => {
      wsRef.current = null
      if (activeRequestIdRef.current) {
        updateStreamingAssistant((assistant) => ({
          ...assistant,
          content: assistant.content || 'Connection closed before completion.',
          isStreaming: false,
        }))
        clearStreamingState()
      }
    }
  }

  const waitForSocketOpen = (socket) => {
    if (socket.readyState === WebSocket.OPEN) {
      return Promise.resolve(socket)
    }

    if (socket.readyState !== WebSocket.CONNECTING) {
      return Promise.reject(new Error('WebSocket is not connectable'))
    }

    return new Promise((resolve, reject) => {
      const onOpen = () => {
        cleanup()
        resolve(socket)
      }
      const onError = () => {
        cleanup()
        reject(new Error('WebSocket connection failed'))
      }
      const onClose = () => {
        cleanup()
        reject(new Error('WebSocket connection closed'))
      }

      const cleanup = () => {
        socket.removeEventListener('open', onOpen)
        socket.removeEventListener('error', onError)
        socket.removeEventListener('close', onClose)
      }

      socket.addEventListener('open', onOpen)
      socket.addEventListener('error', onError)
      socket.addEventListener('close', onClose)
    })
  }

  const ensureSocket = async () => {
    let socket = wsRef.current
    if (!socket || socket.readyState === WebSocket.CLOSED) {
      socket = wsChatAPI.createSocket()
      bindSocketHandlers(socket)
      wsRef.current = socket
    }

    return waitForSocketOpen(socket)
  }

  const buildComposedInput = (text = '') => {
    const typed = String(text || '').trim()
    const pasted = String(pastedContent || '').trim()
    if (typed && pasted) return `${pasted}\n\n${typed}`
    return typed || pasted
  }

  const handleLargePaste = (rawText) => {
    const normalized = String(rawText || '').trim()
    if (!normalized) return false

    setPastedContent((prev) => {
      const existing = String(prev || '').trim()
      if (!existing) return normalized
      return `${existing}\n\n${normalized}`
    })
    showToast('Long text captured as pasted context.', 'info')
    return true
  }

  const handleClearPastedContent = () => {
    setPastedContent('')
  }

  const handleSendMessage = async (text) => {
    let content = buildComposedInput(typeof text === 'string' ? text : inputValue)
    if (!content.trim() || isLoading) return

    content = expandPromptCommands(content, savedPrompts)

    const requestId = buildRequestId()
    activeRequestIdRef.current = requestId
    const activeContextFiles = uploadedFiles
      .map((file) => file?.filename)
      .filter((name) => typeof name === 'string' && name.trim())

    setMessages((prev) => {
      const next = [
        ...prev,
        { role: 'user', content, activeFiles: activeContextFiles },
        {
          role: 'assistant',
          content: '',
          isStreaming: true,
          requestId,
          researchEnabled: webSearchEnabled,
          hasAnswerStarted: false,
          thinkingSteps: [],
        },
      ]
      activeAssistantIndexRef.current = next.length - 1
      return next
    })

    setInputValue('')
    setPastedContent('')
    setActiveView('chat')
    setIsLoading(true)

    try {
      const socket = await ensureSocket()
      socket.send(
        JSON.stringify({
          type: 'start',
          request_id: requestId,
          query: content,
          session_id: activeChatIdRef.current,
          create_new_session: !activeChatIdRef.current,
          research_enabled: webSearchEnabled,
        }),
      )
    } catch (err) {
      if (isAuthFailure(err)) {
        handleSessionExpired()
        return
      }
      console.error('Streaming failed:', err)
      updateStreamingAssistant((assistant) => ({
        ...assistant,
        content: `Error: ${err.message}. Please try again.`,
        isStreaming: false,
      }))
      clearStreamingState()
    }
  }

  const handleStopGenerating = () => {
    const socket = wsRef.current
    const requestId = activeRequestIdRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN || !requestId) return

    socket.send(
      JSON.stringify({
        type: 'cancel',
        request_id: requestId,
      }),
    )
  }

  const handleQuickStart = (prompt) => {
    setInputValue(prompt)
  }

  const handleToggleWebSearch = () => {
    setWebSearchEnabled((prev) => !prev)
  }

  // Suggestions Logic
  const lastWord = inputValue.split(/\s+/).pop() || ''
  const commandQuery = lastWord.startsWith('/') ? lastWord.slice(1).split(':')[0].toUpperCase() : ''
  const filteredSuggestions = commandQuery
    ? savedPrompts.filter((prompt) => {
        const commandKey = toPromptCommandKey(prompt.name)
        return (
          commandKey.includes(commandQuery) ||
          prompt.name.toUpperCase().includes(commandQuery)
        )
      })
    : []

  useEffect(() => {
    if (commandQuery.length > 0) {
      setShowSuggestions(true)
      setSuggestionIndex(0)
    } else {
      setShowSuggestions(false)
    }
  }, [commandQuery])

  const handleSelectSuggestion = (suggestion) => {
    const trimmed = inputValue.replace(/\s+$/, '')
    const command = buildPromptCommand(suggestion.name)
    if (!command) return
    const parts = trimmed.split(/\s+/)
    parts.pop()
    const prefix = parts.filter(Boolean).join(' ')
    const newValue = `${prefix ? `${prefix} ` : ''}${command} `
    setInputValue(newValue)
    setShowSuggestions(false)
  }

  const handleUploadFiles = async (files) => {
    if (!files || files.length === 0) return
    setIsUploadingFiles(true)
    setUploadProgress(0)

    try {
      const response = await documentAPI.upload(
        files,
        activeChatIdRef.current,
        !activeChatIdRef.current,
        (percentage) => setUploadProgress(percentage),
      )
      if (response.session_id && !activeChatIdRef.current) {
        setActiveChatId(response.session_id)
        activeChatIdRef.current = response.session_id
        setActiveView('chat')
        loadSessions()
      }

      setUploadedFiles((prev) => {
        const existingIds = new Set(prev.map((file) => file.file_id))
        const merged = [...prev]
        ;(response.files || []).forEach((file) => {
          if (!existingIds.has(file.file_id)) {
            merged.push(file)
          }
        })
        return merged
      })
    } catch (err) {
      console.error('Upload failed:', err)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${err.message}. File upload failed.`,
        },
      ])
      setActiveView('chat')
    } finally {
      setIsUploadingFiles(false)
      setUploadProgress(0)
    }
  }

  const handleRemoveUploadedFile = async (fileId) => {
    if (!fileId) return
    if (removingFileIds.includes(fileId)) return

    setRemovingFileIds((prev) => [...prev, fileId])

    try {
      await documentAPI.remove(fileId, activeChatIdRef.current)
      setUploadedFiles((prev) => prev.filter((item) => item.file_id !== fileId))
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${err.message}. Could not remove file.`,
        },
      ])
      setActiveView('chat')
    } finally {
      setRemovingFileIds((prev) => prev.filter((id) => id !== fileId))
    }
  }

  const handleRemoveAllUploadedFiles = async () => {
    if (uploadedFiles.length === 0) return

    const filesToRemove = uploadedFiles.filter((file) => file?.file_id)
    const fileIds = filesToRemove.map((file) => file.file_id)
    if (fileIds.length === 0) return

    setRemovingFileIds((prev) => [...new Set([...prev, ...fileIds])])

    const results = await Promise.allSettled(
      filesToRemove.map((file) => documentAPI.remove(file.file_id, activeChatIdRef.current)),
    )

    const removedIds = []
    const errors = []

    results.forEach((result, index) => {
      const fileId = fileIds[index]
      if (result.status === 'fulfilled') {
        removedIds.push(fileId)
      } else {
        const reason = result.reason instanceof Error ? result.reason.message : String(result.reason)
        errors.push(reason)
      }
    })

    if (removedIds.length > 0) {
      setUploadedFiles((prev) => prev.filter((file) => !removedIds.includes(file.file_id)))
    }

    setRemovingFileIds((prev) => prev.filter((id) => !fileIds.includes(id)))

    if (errors.length > 0) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${errors[0]}. Could not remove all files.`,
        },
      ])
      setActiveView('chat')
    }
  }

  const handleOpenUploadedFilePreview = async (file) => {
    const fileId = file?.file_id
    if (!fileId) return null
    if (openingFileIds.includes(fileId)) return null

    setOpeningFileIds((prev) => [...prev, fileId])
    try {
      const response = await documentAPI.getContent(fileId, activeChatIdRef.current)
      return response
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${err.message}. Could not open file preview.`,
        },
      ])
      setActiveView('chat')
      return null
    } finally {
      setOpeningFileIds((prev) => prev.filter((id) => id !== fileId))
    }
  }

  const handleLogout = () => {
    if (confirm('Are you sure you want to log out?')) {
      authAPI.logout()
      setIsAuthenticated(false)
      resetSessionState()
    }
  }

  const handleDeleteSession = async (sessionId) => {
    try {
      await chatAPI.deleteSession(sessionId)
      setRecents((prev) => prev.filter((s) => s.id !== sessionId))
      if (activeChatId === sessionId) {
        handleNavigate('home')
      }
    } catch (err) {
      console.error('Failed to delete session:', err)
      alert('Failed to delete session')
    }
  }

  const handleRenameSession = async (sessionId, newTitle) => {
    try {
      await chatAPI.updateSessionTitle(sessionId, newTitle)
      setRecents((prev) =>
        prev.map((s) => (s.id === sessionId ? { ...s, title: newTitle } : s)),
      )
    } catch (err) {
      console.error('Failed to rename session:', err)
      alert('Failed to rename session')
    }
  }

  const insertIntoChat = (content) => {
    setInputValue(content)
    if (activeView !== 'chat' && activeView !== 'home') {
      setActiveView(activeChatId ? 'chat' : 'home')
    }
  }

  if (!isAuthenticated) {
    if (authMode === 'login') {
      return (
        <Login 
          onSwitchToSignup={() => setAuthMode('signup')} 
          onLoginSuccess={() => setIsAuthenticated(true)} 
        />
      )
    } else {
      return (
        <Signup 
          onSwitchToLogin={() => setAuthMode('login')} 
          onSignupSuccess={() => setIsAuthenticated(true)} 
        />
      )
    }
  }

  return (
    <div className={`app-container ${(isCustomizing || !isSidebarOpen) ? 'sidebar-collapsed-mode' : ''}`}>
      {toast && (
        <div className={`toast ${toast.type}`}>
          {toast.type === 'success' ? <Check size={14} /> : <Info size={14} />}
          <span>{toast.message}</span>
        </div>
      )}
      <Sidebar 
        onNavigate={handleNavigate} 
        activeView={activeView}
        activeChatId={activeChatId}
        onToggleCustomize={handleToggleCustomize}
        recents={recents}
        isOpen={isCustomizing ? false : isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
        onLogout={handleLogout}
        onDeleteSession={handleDeleteSession}
        onRenameSession={handleRenameSession}
        userName={userName}
        userEmail={userEmail}
      />

      {isCustomizing && (
        <CustomizePanel 
          onClose={() => {
            setIsCustomizing(false)
            setActiveView('home')
          }} 
          onNavigate={handleNavigate}
        />
      )}
      
      <main className="main-content">
        <TopBar />
        <div className="view-container">
          {activeView === 'home' && (
            <HomeView 
              onSendMessage={handleSendMessage}
              inputValue={inputValue}
              setInputValue={setInputValue}
              pastedContent={pastedContent}
              onLargePaste={handleLargePaste}
              onClearPastedContent={handleClearPastedContent}
              longPasteThreshold={LONG_PASTE_THRESHOLD}
              onQuickStart={handleQuickStart}
              webSearchEnabled={webSearchEnabled}
              onToggleWebSearch={handleToggleWebSearch}
              onUploadFiles={handleUploadFiles}
              isUploadingFiles={isUploadingFiles}
              userName={userName}
            />
          )}
          {activeView === 'chat' && (
            <ChatView 
              messages={messages}
              onSendMessage={handleSendMessage}
              inputValue={inputValue}
              setInputValue={setInputValue}
              pastedContent={pastedContent}
              onLargePaste={handleLargePaste}
              onClearPastedContent={handleClearPastedContent}
              longPasteThreshold={LONG_PASTE_THRESHOLD}
              isLoading={isLoading}
              onStopGenerating={handleStopGenerating}
              onUploadFiles={handleUploadFiles}
              onRemoveFile={handleRemoveUploadedFile}
              onRemoveAllFiles={handleRemoveAllUploadedFiles}
              onOpenFilePreview={handleOpenUploadedFilePreview}
              webSearchEnabled={webSearchEnabled}
              onToggleWebSearch={handleToggleWebSearch}
              uploadedFiles={uploadedFiles}
              isUploadingFiles={isUploadingFiles}
              uploadProgress={uploadProgress}
              removingFileIds={removingFileIds}
              openingFileIds={openingFileIds}
              showToast={showToast}
            />
          )}
          {activeView === 'skills' && (
            <SkillsView />
          )}
          {activeView === 'customize' && (
            <CustomizeView />
          )}
          {activeView === 'optimizer' && (
            <PromptOptimizerView onInsert={insertIntoChat} showToast={showToast} />
          )}
          {activeView === 'prompts' && (
            <SavedPromptsView onInsert={insertIntoChat} showToast={showToast} />
          )}
        </div>

        {showSuggestions && filteredSuggestions.length > 0 && (
          <div className="command-suggestions">
            <div className="suggestions-header">Commands</div>
            {filteredSuggestions.map((s, idx) => (
              <div 
                key={s.id} 
                className={`suggestion-item ${idx === suggestionIndex ? 'active' : ''}`}
                onClick={() => handleSelectSuggestion(s)}
              >
                <div className="suggestion-icon">/</div>
                <div className="suggestion-info">
                  <span className="suggestion-name">{buildPromptCommand(s.name)}</span>
                  <span className="suggestion-preview">{s.content.slice(0, 60)}...</span>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="footer-warning">
          AXIOM can make mistakes. Verify important information.
        </div>
      </main>
    </div>
  )
}

export default App

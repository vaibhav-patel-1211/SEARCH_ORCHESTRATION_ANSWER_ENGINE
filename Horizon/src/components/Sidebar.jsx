import { Plus, MessagesSquare, Download, ChevronUp, Briefcase, PanelLeftClose, PanelLeftOpen, MessageSquare, LogOut, Search, Sparkles, Bookmark, Trash2, Pencil, Check, X, AlertCircle } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import './Sidebar.css'

function Sidebar({
  onNavigate,
  activeView,
  activeChatId,
  onToggleCustomize,
  recents,
  isOpen,
  onToggleSidebar,
  onLogout,
  onDeleteSession,
  onRenameSession,
  userName,
  userEmail,
}) {
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [activeSession, setActiveSession] = useState(null)
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false)
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false)
  const [editTitle, setEditTitle] = useState('')
  const menuRef = useRef(null)

  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setShowUserMenu(false)
      }
    }
    if (showUserMenu) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showUserMenu])

  const filteredRecents = recents.filter(item => 
    item.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const handleOpenRename = (e, item) => {
    e.stopPropagation()
    setActiveSession(item)
    setEditTitle(item.title)
    setIsRenameModalOpen(true)
  }

  const handleOpenDelete = (e, item) => {
    e.stopPropagation()
    setActiveSession(item)
    setIsDeleteModalOpen(true)
  }

  const confirmRename = () => {
    if (editTitle.trim() && activeSession) {
      onRenameSession(activeSession.id, editTitle.trim())
    }
    closeModals()
  }

  const confirmDelete = () => {
    if (activeSession) {
      onDeleteSession(activeSession.id)
    }
    closeModals()
  }

  const closeModals = () => {
    setIsRenameModalOpen(false)
    setIsDeleteModalOpen(false)
    setActiveSession(null)
    setEditTitle('')
  }

  return (
    <aside className={`sidebar ${!isOpen ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <button className="icon-btn toggle-sidebar" onClick={onToggleSidebar}>
          {isOpen ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
        </button>
      </div>

      <div className="sidebar-top">
        <button 
          className="nav-item new-chat" 
          onClick={() => onNavigate('home')}
          title="New chat"
        >
          <div className="plus-icon-wrapper">
            <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" style={{ flexShrink: 0 }}>
              <path d="M10 3a.75.75 0 0 1 .75.75v5.5h5.5a.75.75 0 0 1 .077 1.496l-.077.004h-5.5v5.5a.75.75 0 0 1-1.5 0v-5.5h-5.5a.75.75 0 0 1 0-1.5h5.5v-5.5A.75.75 0 0 1 10 3"></path>
            </svg>
          </div>
          {isOpen && <span>New chat</span>}
        </button>
        <button 
          className={`nav-item ${activeView === 'optimizer' ? 'active' : ''}`} 
          onClick={() => onNavigate('optimizer')} 
          title="Prompt Optimizer"
        >
          <Sparkles size={18} />
          {isOpen && <span>Prompt Optimizer</span>}
        </button>
        <button 
          className={`nav-item ${activeView === 'prompts' ? 'active' : ''}`} 
          onClick={() => onNavigate('prompts')} 
          title="Saved Prompts"
        >
          <Bookmark size={18} />
          {isOpen && <span>Saved Prompts</span>}
        </button>
        <button 
          className={`nav-item ${activeView === 'customize' ? 'active' : ''}`} 
          onClick={onToggleCustomize}
          title="Customize"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" style={{ flexShrink: 0 }}>
            <path d="M12.5 3A1.5 1.5 0 0 1 14 4.5V6h.5A3.5 3.5 0 0 1 18 9.5v6a1.5 1.5 0 0 1-1.5 1.5h-13a1.5 1.5 0 0 1-1.492-1.347L2 15.5v-6A3.5 3.5 0 0 1 5.5 6H6V4.5A1.5 1.5 0 0 1 7.5 3zM3 15.5l.01.1a.5.5 0 0 0 .49.4h13a.5.5 0 0 0 .5-.5V12h-4v.5a.5.5 0 0 1-1 0V12H8v.5a.5.5 0 0 1-1 0V12H3zM5.5 7A2.5 2.5 0 0 0 3 9.5V11h4v-.5a.5.5 0 0 1 1 0v.5h4v-.5a.5.5 0 0 1-1 0V12H3zM5.5 7A2.5 2.5 0 0 0 3 9.5V11h4v-.5a.5.5 0 0 1 1 0v.5h4v-.5a.5.5 0 0 1 1 0v.5h4V9.5A2.5 2.5 0 0 0 14.5 7zm2-3a.5.5 0 0 0-.5.5V6h6V4.5a.5.5 0 0 0-.5-.5z"></path>
          </svg>
          {isOpen && <span>Customize</span>}
        </button>
      </div>

      {isOpen && (
        <div className="sidebar-section">
          <div className="section-label-row">
            <span className="section-label">RECENTS</span>
            <div className="recent-search">
              <Search size={12} />
              <input 
                type="text" 
                placeholder="Search chats..." 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>
          <div className="recents-list">
            {filteredRecents.map((item) => (
              <div 
                key={item.id} 
                className={`recent-item-container ${activeChatId === item.id ? 'active' : ''}`}
              >
                <button 
                  className={`recent-item ${activeChatId === item.id ? 'active' : ''}`}
                  onClick={() => onNavigate(item.id)}
                  title={item.title}
                >
                  <MessageSquare size={14} className="recent-icon" />
                  <div className="recent-text">
                    <div className="recent-title">{item.title}</div>
                  </div>
                </button>
                {isOpen && (
                  <div className="recent-actions">
                    <button className="action-btn" onClick={(e) => handleOpenRename(e, item)} title="Rename">
                      <Pencil size={14} />
                    </button>
                    <button className="action-btn delete" onClick={(e) => handleOpenDelete(e, item)} title="Delete">
                      <Trash2 size={14} />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="sidebar-footer" ref={menuRef}>
        {showUserMenu && isOpen && (
          <div className="user-menu-popover">
            <button className="user-menu-item" onClick={onLogout}>
              <LogOut size={14} />
              <span>Log out</span>
            </button>
          </div>
        )}
        <div className="user-profile" title={`${userName || 'User'} (${userEmail || 'No email'})`}>
          <div className="avatar">{(userName || userEmail || 'U').charAt(0).toUpperCase()}</div>
          {isOpen && (
            <>
              <div className="user-info">
                <div className="user-name">{userName || 'User'}</div>
                <div className="user-email">{userEmail || 'No email'}</div>
              </div>
              <div className="footer-actions">
                <button 
                  className={`icon-btn ${showUserMenu ? 'active' : ''}`} 
                  onClick={() => setShowUserMenu(!showUserMenu)}
                >
                  <ChevronUp size={14} />
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Rename Modal */}
      {isRenameModalOpen && (
        <div className="modal-overlay" onClick={closeModals}>
          <div className="modal-card" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Rename Chat</h3>
              <button className="close-modal" onClick={closeModals}><X size={18} /></button>
            </div>
            <div className="modal-body">
              <p>Enter a new name for this conversation.</p>
              <input 
                autoFocus
                className="modal-input"
                value={editTitle}
                onChange={e => setEditTitle(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && confirmRename()}
              />
            </div>
            <div className="modal-footer">
              <button className="modal-btn secondary" onClick={closeModals}>Cancel</button>
              <button className="modal-btn primary" onClick={confirmRename} disabled={!editTitle.trim()}>Save</button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Modal */}
      {isDeleteModalOpen && (
        <div className="modal-overlay" onClick={closeModals}>
          <div className="modal-card delete" onClick={e => e.stopPropagation()}>
            <div className="modal-body align-center">
              <div className="warning-icon-wrapper">
                <AlertCircle size={32} color="#dc2626" />
              </div>
              <h3>Delete Chat?</h3>
              <p>This will permanently remove <strong>"{activeSession?.title}"</strong>. This action cannot be undone.</p>
            </div>
            <div className="modal-footer center">
              <button className="modal-btn secondary" onClick={closeModals}>Cancel</button>
              <button className="modal-btn danger" onClick={confirmDelete}>Delete Chat</button>
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}

export default Sidebar

import { useState } from 'react'
import { Sparkles, Copy, Check, RotateCcw, Loader2, MessageSquarePlus } from 'lucide-react'
import { chatAPI } from '../services/api'
import './PromptOptimizerView.css'

const normalizeOptimizedPrompt = (value) => {
  if (typeof value !== 'string') return ''

  let text = value.replace(/\r\n/g, '\n').trim()
  text = text.replace(/^```(?:markdown|md|text)?\s*/i, '').replace(/\s*```$/, '').trim()

  const lines = text.split('\n')
  const nonEmptyLines = lines.filter((line) => line.trim().length > 0)
  const blockQuoteLines = nonEmptyLines.filter((line) => line.trimStart().startsWith('>')).length

  if (nonEmptyLines.length > 0 && blockQuoteLines / nonEmptyLines.length >= 0.5) {
    text = lines.map((line) => line.replace(/^\s*>\s?/, '')).join('\n')
  }

  text = text
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/__(.*?)__/g, '$1')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/^\s*[-*]\s+/gm, '- ')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

  return text
}

function PromptOptimizerView({ onInsert, showToast }) {
  const [prompt, setPrompt] = useState('')
  const [optimizedPrompt, setOptimizedPrompt] = useState('')
  const [isOptimizing, setIsOptimizing] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleOptimize = async () => {
    if (!prompt.trim() || isOptimizing) return
    setIsOptimizing(true)
    try {
      const response = await chatAPI.optimizePrompt(prompt)
      const nextPrompt = normalizeOptimizedPrompt(response?.optimized_prompt)
      if (!nextPrompt) {
        setOptimizedPrompt('')
        showToast('Could not generate an optimized prompt. Please try again.', 'error')
        return
      }
      setOptimizedPrompt(nextPrompt)
    } catch (err) {
      console.error('Optimization failed:', err)
      showToast('Failed to optimize prompt. Please try again.', 'error')
    } finally {
      setIsOptimizing(false)
    }
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(optimizedPrompt)
    setCopied(true)
    showToast('Optimized prompt copied!', 'success')
    setTimeout(() => setCopied(false), 2000)
  }

  const handleReset = () => {
    setPrompt('')
    setOptimizedPrompt('')
  }

  const handleUseInChat = () => {
    onInsert(optimizedPrompt)
    showToast('Inserted into chat', 'success')
  }

  return (
    <div className="optimizer-view">
      <div className="optimizer-container">
        <header className="optimizer-header">
          <div className="header-icon">
            <Sparkles size={24} />
          </div>
          <h1>Prompt Optimizer</h1>
          <p>Transform your simple prompts into detailed, high-quality instructions.</p>
        </header>

        <div className={`optimizer-content ${optimizedPrompt ? 'has-result' : ''}`}>
          <div className="optimizer-input-section">
            <label>Your Prompt</label>
            <textarea
              placeholder="Enter your prompt here (e.g., 'Write a story about a cat')"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={isOptimizing}
            />
            {!optimizedPrompt && (
              <div className="optimizer-section-footer">
                <button 
                  className="optimizer-secondary-btn" 
                  onClick={handleReset}
                  disabled={isOptimizing || !prompt}
                >
                  <RotateCcw size={14} />
                  Reset
                </button>
                <button 
                  className="optimizer-primary-btn" 
                  onClick={handleOptimize}
                  disabled={isOptimizing || !prompt.trim()}
                >
                  {isOptimizing ? (
                    <>
                      <Loader2 size={16} className="spin" />
                      Optimizing...
                    </>
                  ) : (
                    <>
                      <Sparkles size={16} />
                      Optimize Prompt
                    </>
                  )}
                </button>
              </div>
            )}
          </div>

          {optimizedPrompt && (
            <div className="optimizer-output-section">
              <div className="optimizer-section-header">
                <label>Optimized Prompt</label>
                <div className="optimizer-header-actions">
                  <button className="optimizer-action-btn" onClick={handleCopy}>
                    {copied ? <Check size={14} /> : <Copy size={14} />}
                    <span>{copied ? 'Copied' : 'Copy'}</span>
                  </button>
                  <button className="optimizer-action-btn primary" onClick={handleUseInChat}>
                    <MessageSquarePlus size={14} />
                    <span>Use in Chat</span>
                  </button>
                </div>
              </div>
              <div className="optimized-output">
                {optimizedPrompt}
              </div>
              <div className="optimizer-section-footer">
                <button className="optimizer-secondary-btn" onClick={handleReset}>
                  <RotateCcw size={14} />
                  Start Over
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default PromptOptimizerView

import { useState, useRef, useEffect } from 'react'
import { PaperAirplaneIcon, DocumentTextIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import { useConversation, useChat } from '../hooks/useChat'

interface Source {
  doc_titulo: string
  doc_tipo: string
  documento_id: string
  similarity: number
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  sources?: Source[]
}

interface ChatWindowProps {
  conversationId: string
}

function SourcesList({ sources }: { sources: Source[] }) {
  if (!sources.length) return null

  return (
    <div className="mt-3 pt-3 border-t border-gray-200">
      <p className="text-xs font-medium text-gray-500 mb-2">Fontes:</p>
      <div className="space-y-1">
        {sources.slice(0, 3).map((source, idx) => (
          <div key={idx} className="flex items-center text-xs text-gray-600">
            <DocumentTextIcon className="w-3 h-3 mr-1 flex-shrink-0" />
            <span className="truncate">{source.doc_titulo}</span>
            <span className="ml-1 text-gray-400">
              ({(source.similarity * 100).toFixed(0)}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-primary-600 text-white'
            : 'bg-white border border-gray-200'
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
        {!isUser && message.sources && <SourcesList sources={message.sources} />}
      </div>
    </div>
  )
}

function StreamingIndicator({ phase }: { phase: string }) {
  if (phase === 'searching') {
    return (
      <div className="flex justify-start">
        <div className="bg-white border border-gray-200 rounded-lg px-4 py-3">
          <div className="flex items-center space-x-2 text-gray-500">
            <MagnifyingGlassIcon className="w-4 h-4 animate-pulse" />
            <span className="text-sm">Buscando nos documentos...</span>
          </div>
        </div>
      </div>
    )
  }

  return null
}

export default function ChatWindow({ conversationId }: ChatWindowProps) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { data, isLoading: isLoadingHistory } = useConversation(conversationId)
  const {
    sendMessage,
    isLoading: isSending,
    streamingContent,
    streamingPhase,
    streamingSources,
    pendingUserMessage,
  } = useChat(conversationId)

  const messages: Message[] = data?.messages || []

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent, streamingPhase, pendingUserMessage])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isSending) return

    sendMessage(input.trim())
    setInput('')
  }

  if (isLoadingHistory) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    )
  }

  const showEmptyState = messages.length === 0 && !pendingUserMessage

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {showEmptyState ? (
          <div className="text-center text-gray-500 py-12">
            <DocumentTextIcon className="w-12 h-12 mx-auto mb-4 text-gray-400" />
            <p>Inicie uma conversa para analisar os documentos do processo.</p>
            <p className="text-sm mt-2">
              Faca perguntas sobre os documentos, transacoes ou eventos.
            </p>
          </div>
        ) : (
          <>
            {/* Persisted messages */}
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}

            {/* Pending user message (optimistic — only show if server data doesn't already include it) */}
            {pendingUserMessage && !(
              messages.length > 0 &&
              messages[messages.length - 1].role === 'user' &&
              messages[messages.length - 1].content === pendingUserMessage
            ) && (
              <div className="flex justify-end">
                <div className="max-w-[80%] rounded-lg px-4 py-3 bg-primary-600 text-white">
                  <p className="whitespace-pre-wrap">{pendingUserMessage}</p>
                </div>
              </div>
            )}

            {/* Streaming phase indicator */}
            {streamingPhase === 'searching' && (
              <StreamingIndicator phase="searching" />
            )}

            {/* Streaming assistant response */}
            {streamingContent && (
              <div className="flex justify-start">
                <div className="max-w-[80%] rounded-lg px-4 py-3 bg-white border border-gray-200">
                  <p className="whitespace-pre-wrap">{streamingContent}</p>
                  <span className="inline-block w-1.5 h-4 bg-primary-500 animate-pulse ml-0.5 align-text-bottom" />
                  {streamingSources.length > 0 && (
                    <SourcesList sources={streamingSources} />
                  )}
                </div>
              </div>
            )}
          </>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 p-4 bg-white">
        <form onSubmit={handleSubmit} className="flex space-x-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Digite sua pergunta..."
            disabled={isSending}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isSending}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <PaperAirplaneIcon className="w-5 h-5" />
          </button>
        </form>
      </div>
    </div>
  )
}

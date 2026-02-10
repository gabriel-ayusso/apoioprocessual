import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { ArrowLeftIcon, PlusIcon, ChatBubbleLeftRightIcon, Bars3BottomLeftIcon, PencilIcon, CheckIcon, XMarkIcon, TrashIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { chatApi, processosApi } from '../api/client'
import ChatWindow from '../components/ChatWindow'

export default function ChatPage() {
  const { id } = useParams<{ id: string }>()
  const [selectedConversation, setSelectedConversation] = useState<string | null>(null)
  const [showConversations, setShowConversations] = useState(false)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const queryClient = useQueryClient()

  const { data: processoData } = useQuery(
    ['processo', id],
    () => processosApi.get(id!),
    { enabled: !!id }
  )

  const { data: conversationsData, isLoading } = useQuery(
    ['conversations', id],
    () => chatApi.listConversations(id),
    { enabled: !!id }
  )

  const createMutation = useMutation(
    () => chatApi.createConversation(id!, 'Nova conversa'),
    {
      onSuccess: (response) => {
        queryClient.invalidateQueries(['conversations', id])
        setSelectedConversation(response.data.id)
        setShowConversations(false)
      },
    }
  )

  const renameMutation = useMutation(
    ({ convId, titulo }: { convId: string; titulo: string }) =>
      chatApi.updateConversation(convId, titulo),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['conversations', id])
        setRenamingId(null)
      },
    }
  )

  const deleteMutation = useMutation(
    (convId: string) => chatApi.deleteConversation(convId),
    {
      onSuccess: (_data, deletedId) => {
        queryClient.invalidateQueries(['conversations', id])
        if (selectedConversation === deletedId) {
          setSelectedConversation(null)
        }
        toast.success('Conversa excluida')
      },
      onError: () => {
        toast.error('Erro ao excluir conversa')
      },
    }
  )

  const processo = processoData?.data
  const conversations = conversationsData?.data?.conversations || []

  const startRename = (conv: any, e: React.MouseEvent) => {
    e.stopPropagation()
    setRenamingId(conv.id)
    setRenameValue(conv.titulo || '')
  }

  const saveRename = () => {
    if (renamingId && renameValue.trim()) {
      renameMutation.mutate({ convId: renamingId, titulo: renameValue.trim() })
    }
  }

  const selectConversation = (convId: string) => {
    setSelectedConversation(convId)
    setShowConversations(false)
  }

  return (
    <div className="h-[calc(100vh-8rem)] lg:h-[calc(100vh-8rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 gap-2">
        <div className="flex items-center space-x-3 min-w-0">
          <Link to={`/processos/${id}`} className="p-2 hover:bg-gray-100 rounded-lg shrink-0">
            <ArrowLeftIcon className="w-5 h-5 text-gray-600" />
          </Link>
          <div className="min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">Chat</h1>
            <p className="text-gray-600 text-sm truncate">{processo?.titulo}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setShowConversations(!showConversations)}
            className="lg:hidden p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
            title="Conversas"
          >
            <Bars3BottomLeftIcon className="w-5 h-5" />
          </button>
          <button
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isLoading}
            className="flex items-center px-3 py-2 sm:px-4 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            <PlusIcon className="w-5 h-5 sm:mr-2" />
            <span className="hidden sm:inline">Nova Conversa</span>
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex gap-4 min-h-0 relative">
        {/* Conversations list — desktop: always visible, mobile: overlay */}
        <div
          className={`${
            showConversations ? 'fixed inset-0 z-40 flex' : 'hidden'
          } lg:relative lg:flex lg:z-auto`}
        >
          {/* Mobile backdrop */}
          {showConversations && (
            <div
              className="fixed inset-0 bg-black/30 lg:hidden"
              onClick={() => setShowConversations(false)}
            />
          )}
          <div className="relative z-10 w-64 bg-white rounded-lg shadow-sm border border-gray-200 flex flex-col max-h-full">
            <div className="p-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-900">Conversas</h2>
            </div>
            <div className="flex-1 overflow-y-auto">
              {isLoading ? (
                <div className="flex justify-center py-8">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600" />
                </div>
              ) : conversations.length === 0 ? (
                <div className="p-4 text-center text-gray-500 text-sm">
                  <ChatBubbleLeftRightIcon className="w-8 h-8 mx-auto mb-2 text-gray-400" />
                  <p>Nenhuma conversa ainda.</p>
                  <button
                    onClick={() => createMutation.mutate()}
                    className="mt-2 text-primary-600 hover:text-primary-700"
                  >
                    Iniciar conversa
                  </button>
                </div>
              ) : (
                <div className="divide-y divide-gray-200">
                  {conversations.map((conv: any) => (
                    <div
                      key={conv.id}
                      onClick={() => renamingId !== conv.id && selectConversation(conv.id)}
                      className={`w-full px-4 py-3 text-left hover:bg-gray-50 transition-colors cursor-pointer group ${
                        selectedConversation === conv.id ? 'bg-primary-50' : ''
                      }`}
                    >
                      {renamingId === conv.id ? (
                        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="text"
                            value={renameValue}
                            onChange={(e) => setRenameValue(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') saveRename()
                              if (e.key === 'Escape') setRenamingId(null)
                            }}
                            autoFocus
                            className="flex-1 min-w-0 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
                          />
                          <button onClick={saveRename} className="p-1 text-green-600 hover:text-green-700">
                            <CheckIcon className="w-4 h-4" />
                          </button>
                          <button onClick={() => setRenamingId(null)} className="p-1 text-gray-400 hover:text-gray-600">
                            <XMarkIcon className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center justify-between">
                          <div className="min-w-0 flex-1">
                            <p className="font-medium text-gray-900 truncate">
                              {conv.titulo || 'Nova conversa'}
                            </p>
                            <p className="text-xs text-gray-500">
                              {conv.message_count} mensagem(ns)
                            </p>
                          </div>
                          <div className="flex items-center shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={(e) => startRename(conv, e)}
                              className="p-1 text-gray-400 hover:text-primary-600"
                              title="Renomear"
                            >
                              <PencilIcon className="w-4 h-4" />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                if (confirm('Excluir esta conversa?')) {
                                  deleteMutation.mutate(conv.id)
                                }
                              }}
                              className="p-1 text-gray-400 hover:text-red-500"
                              title="Excluir"
                            >
                              <TrashIcon className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Chat window */}
        <div className="flex-1 bg-white rounded-lg shadow-sm border border-gray-200 flex flex-col min-h-0 min-w-0">
          {selectedConversation ? (
            <ChatWindow conversationId={selectedConversation} />
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-500">
              <div className="text-center px-4">
                <ChatBubbleLeftRightIcon className="w-12 h-12 sm:w-16 sm:h-16 mx-auto mb-4 text-gray-400" />
                <p className="text-base sm:text-lg font-medium">Selecione uma conversa</p>
                <p className="text-sm">
                  ou{' '}
                  <button
                    onClick={() => createMutation.mutate()}
                    className="text-primary-600 hover:text-primary-700"
                  >
                    inicie uma nova
                  </button>
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

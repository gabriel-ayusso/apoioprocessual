import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { ArrowLeftIcon, PlusIcon, ChatBubbleLeftRightIcon } from '@heroicons/react/24/outline'
import { chatApi, processosApi } from '../api/client'
import ChatWindow from '../components/ChatWindow'

export default function ChatPage() {
  const { id } = useParams<{ id: string }>()
  const [selectedConversation, setSelectedConversation] = useState<string | null>(null)
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
      },
    }
  )

  const processo = processoData?.data
  const conversations = conversationsData?.data?.conversations || []

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-4">
          <Link to={`/processos/${id}`} className="p-2 hover:bg-gray-100 rounded-lg">
            <ArrowLeftIcon className="w-5 h-5 text-gray-600" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Chat RAG</h1>
            <p className="text-gray-600">{processo?.titulo}</p>
          </div>
        </div>
        <button
          onClick={() => createMutation.mutate()}
          disabled={createMutation.isLoading}
          className="flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          <PlusIcon className="w-5 h-5 mr-2" />
          Nova Conversa
        </button>
      </div>

      {/* Main content */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* Conversations list */}
        <div className="w-64 bg-white rounded-lg shadow-sm border border-gray-200 flex flex-col">
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
                  <button
                    key={conv.id}
                    onClick={() => setSelectedConversation(conv.id)}
                    className={`w-full px-4 py-3 text-left hover:bg-gray-50 transition-colors ${
                      selectedConversation === conv.id ? 'bg-primary-50' : ''
                    }`}
                  >
                    <p className="font-medium text-gray-900 truncate">
                      {conv.titulo || 'Nova conversa'}
                    </p>
                    <p className="text-xs text-gray-500">
                      {conv.message_count} mensagem(ns)
                    </p>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Chat window */}
        <div className="flex-1 bg-white rounded-lg shadow-sm border border-gray-200 flex flex-col min-h-0">
          {selectedConversation ? (
            <ChatWindow conversationId={selectedConversation} />
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-500">
              <div className="text-center">
                <ChatBubbleLeftRightIcon className="w-16 h-16 mx-auto mb-4 text-gray-400" />
                <p className="text-lg font-medium">Selecione uma conversa</p>
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

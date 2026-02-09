import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import { chatApi } from '../api/client'

export function useConversations(processoId?: string) {
  return useQuery(
    ['conversations', processoId],
    async () => {
      const response = await chatApi.listConversations(processoId)
      return response.data
    },
    { enabled: !!processoId }
  )
}

export function useConversation(conversationId?: string) {
  return useQuery(
    ['conversation', conversationId],
    async () => {
      if (!conversationId) return null
      const response = await chatApi.getConversation(conversationId)
      return response.data
    },
    { enabled: !!conversationId }
  )
}

export function useChat(conversationId: string) {
  const queryClient = useQueryClient()
  const [isLoading, setIsLoading] = useState(false)

  const sendMessage = useMutation(
    async (content: string) => {
      setIsLoading(true)
      const response = await chatApi.sendMessage(conversationId, content)
      return response.data
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['conversation', conversationId])
        queryClient.invalidateQueries(['conversations'])
      },
      onSettled: () => {
        setIsLoading(false)
      },
    }
  )

  return {
    sendMessage: sendMessage.mutate,
    isLoading,
    error: sendMessage.error,
  }
}

export function useCreateConversation() {
  const queryClient = useQueryClient()

  return useMutation(
    async ({ processoId, titulo }: { processoId: string; titulo?: string }) => {
      const response = await chatApi.createConversation(processoId, titulo)
      return response.data
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['conversations'])
      },
    }
  )
}

import { useState, useCallback, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import { chatApi, sendMessageStream } from '../api/client'

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
    {
      enabled: !!conversationId,
      refetchOnWindowFocus: false,
    }
  )
}

interface Source {
  doc_titulo: string
  doc_tipo: string
  documento_id: string
  similarity: number
}

export function useChat(conversationId: string) {
  const queryClient = useQueryClient()
  const [isLoading, setIsLoading] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [streamingPhase, setStreamingPhase] = useState<string | null>(null)
  const [streamingSources, setStreamingSources] = useState<Source[]>([])
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null)
  const abortRef = useRef(false)

  const sendMessage = useCallback(async (content: string) => {
    if (isLoading) return

    setIsLoading(true)
    setPendingUserMessage(content)
    setStreamingContent('')
    setStreamingPhase('searching')
    setStreamingSources([])
    abortRef.current = false

    try {
      await sendMessageStream(conversationId, content, {
        onStatus: (phase) => {
          if (!abortRef.current) setStreamingPhase(phase)
        },
        onToken: (token) => {
          if (!abortRef.current) {
            setStreamingPhase('generating')
            setStreamingContent((prev) => prev + token)
          }
        },
        onSources: (sources) => {
          if (!abortRef.current) setStreamingSources(sources)
        },
        onDone: () => {
          // Stream complete — will clean up in finally
        },
        onError: (error) => {
          console.error('Stream error:', error)
        },
      })
    } catch (error) {
      console.error('Send message error:', error)
    } finally {
      setIsLoading(false)
      setStreamingPhase(null)
      setPendingUserMessage(null)
      setStreamingContent('')
      setStreamingSources([])

      // Refresh conversation from server to get persisted messages
      queryClient.invalidateQueries(['conversation', conversationId])
      queryClient.invalidateQueries(['conversations'])
    }
  }, [conversationId, isLoading, queryClient])

  return {
    sendMessage,
    isLoading,
    streamingContent,
    streamingPhase,
    streamingSources,
    pendingUserMessage,
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

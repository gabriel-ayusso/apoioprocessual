import { useParams, Link } from 'react-router-dom'
import { useQuery } from 'react-query'
import {
  DocumentTextIcon,
  ChatBubbleLeftRightIcon,
  CurrencyDollarIcon,
  ArrowLeftIcon,
} from '@heroicons/react/24/outline'
import { processosApi, documentsApi } from '../api/client'

export default function ProcessoDetailPage() {
  const { id } = useParams<{ id: string }>()

  const { data: processoData, isLoading } = useQuery(
    ['processo', id],
    () => processosApi.get(id!),
    { enabled: !!id }
  )

  const { data: docsData } = useQuery(
    ['documents', id],
    () => documentsApi.list(id!, undefined, 0, 5),
    { enabled: !!id }
  )

  const processo = processoData?.data
  const documents = docsData?.data?.documents || []

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    )
  }

  if (!processo) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Processo nao encontrado.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-4">
        <Link
          to="/processos"
          className="p-2 hover:bg-gray-100 rounded-lg"
        >
          <ArrowLeftIcon className="w-5 h-5 text-gray-600" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{processo.titulo}</h1>
          <p className="text-gray-600">
            {processo.numero || 'Sem numero'} -{' '}
            <span
              className={`px-2 py-1 text-xs rounded-full ${
                processo.status === 'ativo'
                  ? 'bg-green-100 text-green-800'
                  : 'bg-gray-100 text-gray-800'
              }`}
            >
              {processo.status}
            </span>
          </p>
        </div>
      </div>

      {/* Description */}
      {processo.descricao && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-500 uppercase mb-2">
            Descricao
          </h2>
          <p className="text-gray-700">{processo.descricao}</p>
        </div>
      )}

      {/* Quick actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link
          to={`/processos/${id}/documentos`}
          className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
        >
          <div className="flex items-center">
            <div className="p-3 bg-blue-100 rounded-lg">
              <DocumentTextIcon className="w-6 h-6 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="font-medium text-gray-900">Documentos</p>
              <p className="text-sm text-gray-500">
                {processo.document_count} documento(s)
              </p>
            </div>
          </div>
        </Link>

        <Link
          to={`/processos/${id}/chat`}
          className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
        >
          <div className="flex items-center">
            <div className="p-3 bg-purple-100 rounded-lg">
              <ChatBubbleLeftRightIcon className="w-6 h-6 text-purple-600" />
            </div>
            <div className="ml-4">
              <p className="font-medium text-gray-900">Chat RAG</p>
              <p className="text-sm text-gray-500">Conversar sobre o processo</p>
            </div>
          </div>
        </Link>

        <Link
          to={`/processos/${id}/transacoes`}
          className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
        >
          <div className="flex items-center">
            <div className="p-3 bg-yellow-100 rounded-lg">
              <CurrencyDollarIcon className="w-6 h-6 text-yellow-600" />
            </div>
            <div className="ml-4">
              <p className="font-medium text-gray-900">Transacoes</p>
              <p className="text-sm text-gray-500">Analise financeira</p>
            </div>
          </div>
        </Link>
      </div>

      {/* Recent documents */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            Documentos Recentes
          </h2>
          <Link
            to={`/processos/${id}/documentos`}
            className="text-sm text-primary-600 hover:text-primary-700"
          >
            Ver todos
          </Link>
        </div>

        <div className="divide-y divide-gray-200">
          {documents.length === 0 ? (
            <div className="p-6 text-center text-gray-500">
              <DocumentTextIcon className="w-12 h-12 mx-auto mb-3 text-gray-400" />
              <p>Nenhum documento ainda.</p>
              <Link
                to={`/processos/${id}/documentos`}
                className="mt-2 inline-block text-primary-600 hover:text-primary-700"
              >
                Adicionar documento
              </Link>
            </div>
          ) : (
            documents.map((doc: any) => (
              <div key={doc.id} className="px-6 py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <DocumentTextIcon className="w-8 h-8 text-gray-400 mr-3" />
                    <div>
                      <p className="font-medium text-gray-900">{doc.titulo}</p>
                      <p className="text-sm text-gray-500">
                        {doc.tipo} - {doc.arquivo_nome}
                      </p>
                    </div>
                  </div>
                  <span
                    className={`px-2 py-1 text-xs rounded-full ${
                      doc.status === 'processed'
                        ? 'bg-green-100 text-green-800'
                        : doc.status === 'error'
                        ? 'bg-red-100 text-red-800'
                        : 'bg-yellow-100 text-yellow-800'
                    }`}
                  >
                    {doc.status}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Shared users */}
      {processo.shared_users && processo.shared_users.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-500 uppercase mb-4">
            Compartilhado com
          </h2>
          <div className="space-y-2">
            {processo.shared_users.map((share: any) => (
              <div
                key={share.user_id}
                className="flex items-center justify-between"
              >
                <div>
                  <p className="font-medium text-gray-900">{share.user_name}</p>
                  <p className="text-sm text-gray-500">{share.user_email}</p>
                </div>
                <span className="px-2 py-1 text-xs bg-gray-100 text-gray-800 rounded-full">
                  {share.role}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

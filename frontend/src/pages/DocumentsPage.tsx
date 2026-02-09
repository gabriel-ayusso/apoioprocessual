import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from 'react-query'
import {
  ArrowLeftIcon,
  DocumentTextIcon,
  TrashIcon,
  ArrowDownTrayIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { documentsApi, processosApi } from '../api/client'
import DocumentUpload from '../components/DocumentUpload'

const DOC_TYPE_LABELS: Record<string, string> = {
  whatsapp_chat: 'Conversa WhatsApp',
  whatsapp_audio: 'Audio WhatsApp',
  email: 'E-mail',
  extrato_bancario: 'Extrato Bancario',
  processo_judicial: 'Documento Judicial',
  comprovante: 'Comprovante',
  contrato: 'Contrato',
  foto_print: 'Foto/Print',
  audio: 'Audio',
  outro: 'Outro',
}

export default function DocumentsPage() {
  const { id } = useParams<{ id: string }>()
  const [showUpload, setShowUpload] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [tipoFilter, setTipoFilter] = useState('')
  const queryClient = useQueryClient()

  const { data: processoData } = useQuery(
    ['processo', id],
    () => processosApi.get(id!),
    { enabled: !!id }
  )

  const { data: docsData, isLoading } = useQuery(
    ['documents', id, tipoFilter],
    () => documentsApi.list(id!, tipoFilter || undefined, 0, 100),
    { enabled: !!id }
  )

  const { data: searchData } = useQuery(
    ['documents-search', id, searchQuery],
    () => documentsApi.search(id!, searchQuery),
    { enabled: !!id && searchQuery.length >= 3 }
  )

  const processo = processoData?.data
  const documents = docsData?.data?.documents || []
  const searchResults = searchData?.data?.results || []

  const handleDelete = async (docId: string) => {
    if (!confirm('Tem certeza que deseja excluir este documento?')) return

    try {
      await documentsApi.delete(docId)
      queryClient.invalidateQueries(['documents', id])
      toast.success('Documento excluido')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Erro ao excluir')
    }
  }

  const handleDownload = async (docId: string) => {
    try {
      const response = await documentsApi.download(docId)
      window.open(response.data.download_url, '_blank')
    } catch (error: any) {
      toast.error('Erro ao baixar documento')
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link to={`/processos/${id}`} className="p-2 hover:bg-gray-100 rounded-lg">
            <ArrowLeftIcon className="w-5 h-5 text-gray-600" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Documentos</h1>
            <p className="text-gray-600">{processo?.titulo}</p>
          </div>
        </div>
        <button
          onClick={() => setShowUpload(!showUpload)}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
        >
          {showUpload ? 'Fechar' : 'Novo Documento'}
        </button>
      </div>

      {/* Upload form */}
      {showUpload && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Enviar Documento
          </h2>
          <DocumentUpload
            processoId={id!}
            onUploadComplete={() => {
              queryClient.invalidateQueries(['documents', id])
              setShowUpload(false)
            }}
          />
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1 relative">
          <MagnifyingGlassIcon className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Buscar texto nos documentos..."
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>
        <select
          value={tipoFilter}
          onChange={(e) => setTipoFilter(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        >
          <option value="">Todos os tipos</option>
          {Object.entries(DOC_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {/* Search results */}
      {searchQuery.length >= 3 && searchResults.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <h3 className="font-medium text-yellow-800 mb-2">
            Resultados da busca por &quot;{searchQuery}&quot;
          </h3>
          <div className="space-y-2">
            {searchResults.map((result: any) => (
              <div key={result.document_id} className="text-sm">
                <span className="font-medium text-gray-900">{result.titulo}</span>
                <span className="text-gray-500"> ({DOC_TYPE_LABELS[result.tipo]})</span>
                <p className="text-gray-600 mt-1 text-xs">{result.excerpt}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Documents list */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      ) : documents.length === 0 ? (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
          <DocumentTextIcon className="w-16 h-16 mx-auto mb-4 text-gray-400" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            Nenhum documento
          </h3>
          <p className="text-gray-500 mb-4">
            Adicione documentos para analise.
          </p>
          <button
            onClick={() => setShowUpload(true)}
            className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
          >
            Adicionar Documento
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Documento
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Tipo
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Data
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Acoes
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {documents.map((doc: any) => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div className="flex items-center">
                      <DocumentTextIcon className="w-8 h-8 text-gray-400 mr-3" />
                      <div>
                        <p className="font-medium text-gray-900">{doc.titulo}</p>
                        <p className="text-sm text-gray-500">{doc.arquivo_nome}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-sm text-gray-600">
                      {DOC_TYPE_LABELS[doc.tipo] || doc.tipo}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`px-2 py-1 text-xs rounded-full ${
                        doc.status === 'processed'
                          ? 'bg-green-100 text-green-800'
                          : doc.status === 'error'
                          ? 'bg-red-100 text-red-800'
                          : doc.status === 'processing'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-yellow-100 text-yellow-800'
                      }`}
                    >
                      {doc.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {doc.data_referencia || '-'}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex justify-end space-x-2">
                      <button
                        onClick={() => handleDownload(doc.id)}
                        className="p-1 text-gray-400 hover:text-primary-600 rounded"
                        title="Baixar"
                      >
                        <ArrowDownTrayIcon className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => handleDelete(doc.id)}
                        className="p-1 text-gray-400 hover:text-red-500 rounded"
                        title="Excluir"
                      >
                        <TrashIcon className="w-5 h-5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

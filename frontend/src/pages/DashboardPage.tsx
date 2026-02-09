import { useQuery } from 'react-query'
import { Link } from 'react-router-dom'
import {
  FolderIcon,
  DocumentTextIcon,
  ChatBubbleLeftRightIcon,
  CurrencyDollarIcon,
} from '@heroicons/react/24/outline'
import { processosApi } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

export default function DashboardPage() {
  const { user } = useAuth()
  const { data: processosData } = useQuery('processos', () =>
    processosApi.list('ativo', 0, 5)
  )

  const processos = processosData?.data?.processos || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Bem-vindo, {user?.name}!
        </h1>
        <p className="text-gray-600">
          Gerencie seus processos e documentos juridicos.
        </p>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center">
            <div className="p-3 bg-primary-100 rounded-lg">
              <FolderIcon className="w-6 h-6 text-primary-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-600">Processos Ativos</p>
              <p className="text-2xl font-semibold text-gray-900">
                {processosData?.data?.total || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center">
            <div className="p-3 bg-green-100 rounded-lg">
              <DocumentTextIcon className="w-6 h-6 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-600">Documentos</p>
              <p className="text-2xl font-semibold text-gray-900">
                {processos.reduce((acc: number, p: any) => acc + (p.document_count || 0), 0)}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center">
            <div className="p-3 bg-purple-100 rounded-lg">
              <ChatBubbleLeftRightIcon className="w-6 h-6 text-purple-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-600">Conversas</p>
              <p className="text-2xl font-semibold text-gray-900">-</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center">
            <div className="p-3 bg-yellow-100 rounded-lg">
              <CurrencyDollarIcon className="w-6 h-6 text-yellow-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-600">Transacoes</p>
              <p className="text-2xl font-semibold text-gray-900">-</p>
            </div>
          </div>
        </div>
      </div>

      {/* Recent processos */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            Processos Recentes
          </h2>
          <Link
            to="/processos"
            className="text-sm text-primary-600 hover:text-primary-700"
          >
            Ver todos
          </Link>
        </div>

        <div className="divide-y divide-gray-200">
          {processos.length === 0 ? (
            <div className="p-6 text-center text-gray-500">
              <FolderIcon className="w-12 h-12 mx-auto mb-3 text-gray-400" />
              <p>Nenhum processo encontrado.</p>
              <Link
                to="/processos"
                className="mt-2 inline-block text-primary-600 hover:text-primary-700"
              >
                Criar primeiro processo
              </Link>
            </div>
          ) : (
            processos.map((processo: any) => (
              <Link
                key={processo.id}
                to={`/processos/${processo.id}`}
                className="block px-6 py-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-900">{processo.titulo}</p>
                    <p className="text-sm text-gray-500">
                      {processo.numero || 'Sem numero'} -{' '}
                      {processo.document_count} documento(s)
                    </p>
                  </div>
                  <span
                    className={`px-2 py-1 text-xs rounded-full ${
                      processo.status === 'ativo'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {processo.status}
                  </span>
                </div>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

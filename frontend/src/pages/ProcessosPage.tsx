import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { Link } from 'react-router-dom'
import { PlusIcon, FolderIcon, TrashIcon } from '@heroicons/react/24/outline'
import { Dialog } from '@headlessui/react'
import toast from 'react-hot-toast'
import { processosApi } from '../api/client'

export default function ProcessosPage() {
  const [isOpen, setIsOpen] = useState(false)
  const [titulo, setTitulo] = useState('')
  const [numero, setNumero] = useState('')
  const [descricao, setDescricao] = useState('')
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery('processos', () =>
    processosApi.list(undefined, 0, 100)
  )

  const createMutation = useMutation(
    (data: { titulo: string; numero?: string; descricao?: string }) =>
      processosApi.create(data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('processos')
        setIsOpen(false)
        setTitulo('')
        setNumero('')
        setDescricao('')
        toast.success('Processo criado com sucesso!')
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Erro ao criar processo')
      },
    }
  )

  const deleteMutation = useMutation(
    (id: string) => processosApi.delete(id),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('processos')
        toast.success('Processo excluido')
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Erro ao excluir')
      },
    }
  )

  const processos = data?.data?.processos || []

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate({
      titulo,
      numero: numero || undefined,
      descricao: descricao || undefined,
    })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Processos</h1>
          <p className="text-gray-600">Gerencie seus processos judiciais.</p>
        </div>
        <button
          onClick={() => setIsOpen(true)}
          className="flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
        >
          <PlusIcon className="w-5 h-5 mr-2" />
          Novo Processo
        </button>
      </div>

      {/* List */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      ) : processos.length === 0 ? (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
          <FolderIcon className="w-16 h-16 mx-auto mb-4 text-gray-400" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            Nenhum processo
          </h3>
          <p className="text-gray-500 mb-4">
            Crie seu primeiro processo para comecar.
          </p>
          <button
            onClick={() => setIsOpen(true)}
            className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
          >
            <PlusIcon className="w-5 h-5 mr-2" />
            Criar Processo
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {processos.map((processo: any) => (
            <div
              key={processo.id}
              className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center">
                  <div className="p-2 bg-primary-100 rounded-lg mr-3">
                    <FolderIcon className="w-6 h-6 text-primary-600" />
                  </div>
                  <div>
                    <h3 className="font-medium text-gray-900">
                      {processo.titulo}
                    </h3>
                    <p className="text-sm text-gray-500">
                      {processo.numero || 'Sem numero'}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => {
                    if (confirm('Tem certeza que deseja excluir este processo?')) {
                      deleteMutation.mutate(processo.id)
                    }
                  }}
                  className="p-1 text-gray-400 hover:text-red-500 rounded"
                >
                  <TrashIcon className="w-5 h-5" />
                </button>
              </div>

              <p className="text-sm text-gray-600 mb-4 line-clamp-2">
                {processo.descricao || 'Sem descricao'}
              </p>

              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500">
                  {processo.document_count} documento(s)
                </span>
                <span
                  className={`px-2 py-1 rounded-full text-xs ${
                    processo.status === 'ativo'
                      ? 'bg-green-100 text-green-800'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {processo.status}
                </span>
              </div>

              <div className="mt-4 pt-4 border-t border-gray-200">
                <Link
                  to={`/processos/${processo.id}`}
                  className="text-primary-600 hover:text-primary-700 text-sm font-medium"
                >
                  Ver detalhes
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      <Dialog
        open={isOpen}
        onClose={() => setIsOpen(false)}
        className="relative z-50"
      >
        <div className="fixed inset-0 bg-black/30" aria-hidden="true" />

        <div className="fixed inset-0 flex items-center justify-center p-4">
          <Dialog.Panel className="mx-auto max-w-md w-full bg-white rounded-lg shadow-xl">
            <form onSubmit={handleSubmit}>
              <div className="p-6">
                <Dialog.Title className="text-lg font-semibold text-gray-900 mb-4">
                  Novo Processo
                </Dialog.Title>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Titulo *
                    </label>
                    <input
                      type="text"
                      value={titulo}
                      onChange={(e) => setTitulo(e.target.value)}
                      required
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      placeholder="Ex: Divorcio Silva x Santos"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Numero do Processo
                    </label>
                    <input
                      type="text"
                      value={numero}
                      onChange={(e) => setNumero(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      placeholder="Ex: 0001234-56.2024.8.26.0100"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Descricao
                    </label>
                    <textarea
                      value={descricao}
                      onChange={(e) => setDescricao(e.target.value)}
                      rows={3}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      placeholder="Descricao do processo"
                    />
                  </div>
                </div>
              </div>

              <div className="px-6 py-4 bg-gray-50 rounded-b-lg flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsOpen(false)}
                  className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isLoading}
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
                >
                  {createMutation.isLoading ? 'Criando...' : 'Criar'}
                </button>
              </div>
            </form>
          </Dialog.Panel>
        </div>
      </Dialog>
    </div>
  )
}

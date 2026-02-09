import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import {
  ArrowLeftIcon,
  CheckIcon,
  PencilIcon,
  CurrencyDollarIcon,
} from '@heroicons/react/24/outline'
import { Dialog } from '@headlessui/react'
import toast from 'react-hot-toast'
import { transacoesApi, processosApi } from '../api/client'

const CATEGORIAS = [
  'educacao',
  'saude',
  'moradia',
  'alimentacao',
  'transporte',
  'lazer',
  'vestuario',
  'servicos',
  'impostos',
  'outros',
]

export default function TransacoesPage() {
  const { id } = useParams<{ id: string }>()
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editData, setEditData] = useState({ pagador: '', categoria: '' })
  const [filterCategoria, setFilterCategoria] = useState('')
  const [filterPagador, setFilterPagador] = useState('')
  const queryClient = useQueryClient()

  const { data: processoData } = useQuery(
    ['processo', id],
    () => processosApi.get(id!),
    { enabled: !!id }
  )

  const { data: transacoesData, isLoading } = useQuery(
    ['transacoes', id, filterCategoria, filterPagador],
    () =>
      transacoesApi.list(id!, {
        categoria: filterCategoria || undefined,
        pagador: filterPagador || undefined,
      }),
    { enabled: !!id }
  )

  const { data: summaryData } = useQuery(
    ['transacoes-summary', id],
    () => transacoesApi.summary(id!),
    { enabled: !!id }
  )

  const updateMutation = useMutation(
    ({ transacaoId, data }: { transacaoId: string; data: any }) =>
      transacoesApi.update(transacaoId, data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['transacoes', id])
        queryClient.invalidateQueries(['transacoes-summary', id])
        setEditingId(null)
        toast.success('Transacao atualizada')
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Erro ao atualizar')
      },
    }
  )

  const confirmMutation = useMutation(
    (transacaoId: string) => transacoesApi.confirm(transacaoId),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['transacoes', id])
        toast.success('Transacao confirmada')
      },
    }
  )

  const processo = processoData?.data
  const transacoes = transacoesData?.data?.transacoes || []
  const summary = summaryData?.data

  const startEdit = (transacao: any) => {
    setEditingId(transacao.id)
    setEditData({
      pagador: transacao.pagador || '',
      categoria: transacao.categoria || '',
    })
  }

  const saveEdit = () => {
    if (editingId) {
      updateMutation.mutate({ transacaoId: editingId, data: editData })
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-4">
        <Link to={`/processos/${id}`} className="p-2 hover:bg-gray-100 rounded-lg">
          <ArrowLeftIcon className="w-5 h-5 text-gray-600" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Transacoes</h1>
          <p className="text-gray-600">{processo?.titulo}</p>
        </div>
      </div>

      {/* Summary */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center">
              <div className="p-3 bg-green-100 rounded-lg">
                <CurrencyDollarIcon className="w-6 h-6 text-green-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm text-gray-600">Total Geral</p>
                <p className="text-2xl font-semibold text-gray-900">
                  R$ {Number(summary.total_geral || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-600 mb-2">Por Categoria</p>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {summary.by_categoria?.slice(0, 5).map((cat: any) => (
                <div key={cat.categoria} className="flex justify-between text-sm">
                  <span className="text-gray-600">{cat.categoria || 'Sem categoria'}</span>
                  <span className="font-medium">
                    R$ {Number(cat.total || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-600 mb-2">Por Pagador</p>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {summary.by_pagador?.slice(0, 5).map((pag: any) => (
                <div key={pag.pagador} className="flex justify-between text-sm">
                  <span className="text-gray-600">{pag.pagador || 'Incerto'}</span>
                  <span className="font-medium">
                    R$ {Number(pag.total || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-4">
        <select
          value={filterCategoria}
          onChange={(e) => setFilterCategoria(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
        >
          <option value="">Todas as categorias</option>
          {CATEGORIAS.map((cat) => (
            <option key={cat} value={cat}>
              {cat.charAt(0).toUpperCase() + cat.slice(1)}
            </option>
          ))}
        </select>

        <input
          type="text"
          value={filterPagador}
          onChange={(e) => setFilterPagador(e.target.value)}
          placeholder="Filtrar por pagador..."
          className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
        />
      </div>

      {/* Transactions table */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      ) : transacoes.length === 0 ? (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
          <CurrencyDollarIcon className="w-16 h-16 mx-auto mb-4 text-gray-400" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            Nenhuma transacao
          </h3>
          <p className="text-gray-500">
            As transacoes serao extraidas automaticamente dos extratos bancarios.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Data
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Descricao
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Valor
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Pagador
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Categoria
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Confianca
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  Acoes
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {transacoes.map((t: any) => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {t.data || '-'}
                  </td>
                  <td className="px-6 py-4">
                    <p className="text-sm text-gray-900">{t.descricao}</p>
                  </td>
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">
                    R$ {Number(t.valor || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {t.pagador || '-'}
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-1 text-xs bg-gray-100 text-gray-800 rounded-full">
                      {t.categoria || 'Sem categoria'}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center">
                      <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${
                            (t.confianca || 0) >= 0.7
                              ? 'bg-green-500'
                              : (t.confianca || 0) >= 0.4
                              ? 'bg-yellow-500'
                              : 'bg-red-500'
                          }`}
                          style={{ width: `${(t.confianca || 0) * 100}%` }}
                        />
                      </div>
                      <span className="ml-2 text-xs text-gray-500">
                        {((t.confianca || 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex justify-end space-x-2">
                      <button
                        onClick={() => startEdit(t)}
                        className="p-1 text-gray-400 hover:text-primary-600 rounded"
                        title="Editar"
                      >
                        <PencilIcon className="w-5 h-5" />
                      </button>
                      {!t.revisado_humano && (
                        <button
                          onClick={() => confirmMutation.mutate(t.id)}
                          className="p-1 text-gray-400 hover:text-green-600 rounded"
                          title="Confirmar"
                        >
                          <CheckIcon className="w-5 h-5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Edit modal */}
      <Dialog
        open={!!editingId}
        onClose={() => setEditingId(null)}
        className="relative z-50"
      >
        <div className="fixed inset-0 bg-black/30" aria-hidden="true" />

        <div className="fixed inset-0 flex items-center justify-center p-4">
          <Dialog.Panel className="mx-auto max-w-md w-full bg-white rounded-lg shadow-xl">
            <div className="p-6">
              <Dialog.Title className="text-lg font-semibold text-gray-900 mb-4">
                Editar Transacao
              </Dialog.Title>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Pagador
                  </label>
                  <input
                    type="text"
                    value={editData.pagador}
                    onChange={(e) =>
                      setEditData({ ...editData, pagador: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Categoria
                  </label>
                  <select
                    value={editData.categoria}
                    onChange={(e) =>
                      setEditData({ ...editData, categoria: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                  >
                    <option value="">Selecione...</option>
                    {CATEGORIAS.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat.charAt(0).toUpperCase() + cat.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="px-6 py-4 bg-gray-50 rounded-b-lg flex justify-end space-x-3">
              <button
                onClick={() => setEditingId(null)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
              >
                Cancelar
              </button>
              <button
                onClick={saveEdit}
                disabled={updateMutation.isLoading}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                {updateMutation.isLoading ? 'Salvando...' : 'Salvar'}
              </button>
            </div>
          </Dialog.Panel>
        </div>
      </Dialog>
    </div>
  )
}

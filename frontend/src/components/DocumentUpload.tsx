import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { CloudArrowUpIcon, XMarkIcon, DocumentIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { documentsApi } from '../api/client'

interface DocumentUploadProps {
  processoId: string
  onUploadComplete: () => void
}

const DOC_TYPES = [
  { value: 'whatsapp_chat', label: 'Conversa WhatsApp' },
  { value: 'whatsapp_audio', label: 'Audio WhatsApp' },
  { value: 'email', label: 'E-mail' },
  { value: 'extrato_bancario', label: 'Extrato Bancario' },
  { value: 'processo_judicial', label: 'Documento Judicial' },
  { value: 'comprovante', label: 'Comprovante' },
  { value: 'contrato', label: 'Contrato' },
  { value: 'foto_print', label: 'Foto/Print' },
  { value: 'audio', label: 'Audio' },
  { value: 'outro', label: 'Outro' },
]

export default function DocumentUpload({ processoId, onUploadComplete }: DocumentUploadProps) {
  const [file, setFile] = useState<File | null>(null)
  const [tipo, setTipo] = useState('outro')
  const [titulo, setTitulo] = useState('')
  const [descricao, setDescricao] = useState('')
  const [participantes, setParticipantes] = useState('')
  const [dataReferencia, setDataReferencia] = useState('')
  const [uploading, setUploading] = useState(false)

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const f = acceptedFiles[0]
      setFile(f)
      if (!titulo) {
        setTitulo(f.name.replace(/\.[^/.]+$/, ''))
      }
    }
  }, [titulo])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024, // 50MB
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file || !titulo || !tipo) {
      toast.error('Preencha todos os campos obrigatorios')
      return
    }

    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('processo_id', processoId)
      formData.append('tipo', tipo)
      formData.append('titulo', titulo)
      if (descricao) formData.append('descricao', descricao)
      if (participantes) formData.append('participantes', participantes)
      if (dataReferencia) formData.append('data_referencia', dataReferencia)

      await documentsApi.upload(formData)
      toast.success('Documento enviado! Processamento em andamento.')

      // Reset form
      setFile(null)
      setTipo('outro')
      setTitulo('')
      setDescricao('')
      setParticipantes('')
      setDataReferencia('')

      onUploadComplete()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Erro ao enviar documento')
    } finally {
      setUploading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-primary-500 bg-primary-50'
            : 'border-gray-300 hover:border-gray-400'
        }`}
      >
        <input {...getInputProps()} />
        {file ? (
          <div className="flex items-center justify-center space-x-3">
            <DocumentIcon className="w-10 h-10 text-gray-400" />
            <div className="text-left">
              <p className="font-medium text-gray-900">{file.name}</p>
              <p className="text-sm text-gray-500">
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                setFile(null)
              }}
              className="p-1 rounded-full hover:bg-gray-100"
            >
              <XMarkIcon className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        ) : (
          <>
            <CloudArrowUpIcon className="w-12 h-12 mx-auto text-gray-400" />
            <p className="mt-2 text-sm text-gray-600">
              {isDragActive
                ? 'Solte o arquivo aqui...'
                : 'Arraste um arquivo ou clique para selecionar'}
            </p>
            <p className="mt-1 text-xs text-gray-500">
              PDF, imagens, audio, documentos ate 50MB
            </p>
          </>
        )}
      </div>

      {/* Form fields */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Tipo de Documento *
          </label>
          <select
            value={tipo}
            onChange={(e) => setTipo(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          >
            {DOC_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Titulo *
          </label>
          <input
            type="text"
            value={titulo}
            onChange={(e) => setTitulo(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            placeholder="Nome do documento"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Participantes
          </label>
          <input
            type="text"
            value={participantes}
            onChange={(e) => setParticipantes(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            placeholder="Ex: Maria, Joao (separados por virgula)"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Data de Referencia
          </label>
          <input
            type="date"
            value={dataReferencia}
            onChange={(e) => setDataReferencia(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>

        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Descricao
          </label>
          <textarea
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
            rows={2}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            placeholder="Descricao opcional do documento"
          />
        </div>
      </div>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={!file || !titulo || uploading}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
        >
          {uploading ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
              <span>Enviando...</span>
            </>
          ) : (
            <>
              <CloudArrowUpIcon className="w-5 h-5" />
              <span>Enviar Documento</span>
            </>
          )}
        </button>
      </div>
    </form>
  )
}

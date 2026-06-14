import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '@/context/AuthContext'
import { integrationsApi } from '@/lib/api/os'

const keys = {
  all: ['integrations'] as const,
  dashboard: ['integrations', 'dashboard'] as const,
}

export function useIntegrationsDashboard() {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: keys.dashboard,
    queryFn: async () => {
      const [connections, providers, status] = await Promise.all([
        integrationsApi.list(authFetch).catch(() => ({ connections: [] })),
        integrationsApi.providers(authFetch).catch(() => ({ providers: [] })),
        integrationsApi.status(authFetch).catch(() => ({ status: {} })),
      ])
      return {
        connections: connections.connections,
        providers: providers.providers,
        status: status.status,
      }
    },
    staleTime: 30_000,
  })
}

export function useCreateIntegration() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { provider: string; label?: string; config?: Record<string, unknown> }) =>
      integrationsApi.create(authFetch, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  })
}

export function useUpdateIntegrationConfig() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, config }: { id: string; config: Record<string, unknown> }) =>
      integrationsApi.updateConfig(authFetch, id, config),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  })
}

export function useTestIntegration() {
  const { authFetch } = useAuth()
  return useMutation({
    mutationFn: (id: string) => integrationsApi.test(authFetch, id),
  })
}

export function useSyncIntegration() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => integrationsApi.sync(authFetch, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  })
}

export function useDeleteIntegration() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => integrationsApi.delete(authFetch, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  })
}

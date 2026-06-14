import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '@/context/AuthContext'
import { productsApi, riskApi, type ProductCreateBody, type ProductLifecycle } from '@/lib/api/os'

const productKeys = {
  all: ['products'] as const,
  dashboard: ['products', 'dashboard'] as const,
}

export function useProductsDashboard() {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: productKeys.dashboard,
    queryFn: async () => {
      const products = await productsApi.list(authFetch)
      const [events, alertResult] = await Promise.all([
        Promise.all(
          products.map(async (product) => {
            const res = await productsApi.events(authFetch, product.id).catch(() => ({ events: [] }))
            return [product.id, res.events] as const
          }),
        ),
        riskApi.alerts(authFetch, { size: 100 }).catch(() => ({ alerts: [], page: 1, size: 100 })),
      ])
      return {
        products,
        eventsByProduct: Object.fromEntries(events),
        alerts: alertResult.alerts,
      }
    },
    staleTime: 30_000,
  })
}

export function useCreateProduct() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: ProductCreateBody) => productsApi.create(authFetch, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: productKeys.all }),
  })
}

export function useUpdateProductLifecycle() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ productId, stage, reason }: { productId: string; stage: ProductLifecycle; reason?: string }) =>
      productsApi.updateLifecycle(authFetch, productId, stage, reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: productKeys.all }),
  })
}

export function useDeleteProduct() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (productId: string) => productsApi.delete(authFetch, productId, true),
    onSuccess: () => qc.invalidateQueries({ queryKey: productKeys.all }),
  })
}

export function useProductComplianceCheck() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ productId, market }: { productId: string; market: string }) =>
      productsApi.complianceCheck(authFetch, productId, market),
    onSuccess: () => qc.invalidateQueries({ queryKey: productKeys.all }),
  })
}

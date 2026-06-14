import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '@/context/AuthContext'
import { schedulerApi } from '@/lib/api/os'

const keys = {
  all: ['scheduler'] as const,
  dashboard: ['scheduler', 'dashboard'] as const,
}

export function useSchedulerDashboard() {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: keys.dashboard,
    queryFn: async () => {
      const [grouped, config] = await Promise.all([
        schedulerApi.grouped(authFetch),
        schedulerApi.tasksWithWorkers(authFetch).catch(() => null),
      ])
      return { grouped, config }
    },
    staleTime: 20_000,
  })
}

export function useSchedulerJobAction() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ jobId, action }: { jobId: string; action: 'pause' | 'resume' | 'trigger' | 'delete' }) => {
      if (action === 'pause') return schedulerApi.pause(authFetch, jobId)
      if (action === 'resume') return schedulerApi.resume(authFetch, jobId)
      if (action === 'trigger') return schedulerApi.trigger(authFetch, jobId)
      return schedulerApi.delete(authFetch, jobId)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  })
}

export function useCreateSchedulerJob() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      task: string
      trigger_type: 'interval' | 'cron'
      trigger_args: Record<string, unknown>
      job_id?: string
      replace_existing?: boolean
    }) => schedulerApi.create(authFetch, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  })
}

export function useSchedulerBinding() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ taskName, workerCode }: { taskName: string; workerCode: string }) =>
      schedulerApi.updateBinding(authFetch, taskName, workerCode),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  })
}

/**
 * 通知渠道 TanStack Query hooks。
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '@/context/AuthContext'
import {
  changePassword,
  createNotifyChannel,
  deleteNotifyChannel,
  listNotifyChannels,
  testNotifyChannel,
  toggleNotifyChannel,
  updateNotifyChannel,
} from '@/lib/api/notify'
import type { ChannelBody } from '@/lib/api/notify'

const KEYS = {
  channels: ['notify', 'channels'] as const,
}

export function useNotifyChannels() {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.channels,
    queryFn: () => listNotifyChannels(authFetch),
    staleTime: 60_000,
  })
}

export function useCreateChannel() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: ChannelBody) => createNotifyChannel(authFetch, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.channels }),
  })
}

export function useUpdateChannel() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ChannelBody }) =>
      updateNotifyChannel(authFetch, id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.channels }),
  })
}

export function useDeleteChannel() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteNotifyChannel(authFetch, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.channels }),
  })
}

export function useToggleChannel() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      toggleNotifyChannel(authFetch, id, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.channels }),
  })
}

export function useTestChannel() {
  const { authFetch } = useAuth()
  return useMutation({
    mutationFn: (id: string) => testNotifyChannel(authFetch, id),
  })
}

export function useChangePassword() {
  const { authFetch } = useAuth()
  return useMutation({
    mutationFn: ({ oldPw, newPw }: { oldPw: string; newPw: string }) =>
      changePassword(authFetch, oldPw, newPw),
  })
}

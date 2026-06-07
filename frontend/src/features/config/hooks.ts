import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../lib/api'
import type { RuntimeConfigUpdateRequest } from '../../types'

export const runtimeConfigKey = ['runtime-config'] as const

export function useRuntimeConfig() {
  return useQuery({
    queryKey: runtimeConfigKey,
    queryFn: () => api.getRuntimeConfig(),
    staleTime: 10_000,
  })
}

export function useUpdateRuntimeConfig() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (payload: RuntimeConfigUpdateRequest) => api.updateRuntimeConfig(payload),
    onSuccess: (config) => {
      client.setQueryData(runtimeConfigKey, config)
    },
  })
}

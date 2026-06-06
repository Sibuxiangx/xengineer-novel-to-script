import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../lib/api'
import type { ChatSession, ChatSessionDetail, ScriptUserEditRequest } from '../../types'

export const sessionsKey = ['chat-sessions'] as const
export const archivedSessionsKey = ['chat-sessions', 'archived'] as const
export const sessionDetailKey = (sessionId: string | null) =>
  ['chat-session', sessionId] as const

export function useSessions() {
  return useQuery({
    queryKey: sessionsKey,
    queryFn: () => api.listSessions(),
    staleTime: 5_000,
  })
}

export function useArchivedSessions(enabled = true) {
  return useQuery({
    queryKey: archivedSessionsKey,
    queryFn: async () => {
      const sessions = await api.listSessions({ includeArchived: true })
      return sessions.filter((session) => session.status === 'archived')
    },
    enabled,
    staleTime: 5_000,
  })
}

export function useSessionDetail(sessionId: string | null) {
  return useQuery({
    queryKey: sessionDetailKey(sessionId),
    queryFn: () => api.getSession(sessionId ?? ''),
    enabled: Boolean(sessionId),
  })
}

export function useCreateSession() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (title?: string) => api.createSession(title),
    onSuccess: (session: ChatSession) => {
      client.setQueryData<ChatSession[]>(sessionsKey, (existing) => {
        if (!existing) return [session]
        return [session, ...existing.filter((item) => item.id !== session.id)]
      })
    },
  })
}

export function useArchiveSession() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (sessionId: string) => api.archiveSession(sessionId),
    onSuccess: (session: ChatSession) => {
      client.setQueryData<ChatSession[]>(sessionsKey, (existing) =>
        existing?.filter((item) => item.id !== session.id) ?? [],
      )
      void client.invalidateQueries({ queryKey: sessionsKey })
      void client.invalidateQueries({ queryKey: archivedSessionsKey })
      void client.invalidateQueries({ queryKey: sessionDetailKey(session.id) })
    },
  })
}

export function useRestoreSession() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (sessionId: string) => api.restoreSession(sessionId),
    onSuccess: (session: ChatSession) => {
      client.setQueryData<ChatSession[]>(sessionsKey, (existing) => {
        if (!existing) return [session]
        return [session, ...existing.filter((item) => item.id !== session.id)]
      })
      client.setQueryData<ChatSession[]>(archivedSessionsKey, (existing) =>
        existing?.filter((item) => item.id !== session.id) ?? [],
      )
      void client.invalidateQueries({ queryKey: sessionsKey })
      void client.invalidateQueries({ queryKey: archivedSessionsKey })
      void client.invalidateQueries({ queryKey: sessionDetailKey(session.id) })
    },
  })
}

export function useChapters(sessionId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ['chapters', sessionId],
    queryFn: () => api.listChapters(sessionId ?? ''),
    enabled: Boolean(sessionId) && enabled,
  })
}

export function useBookIndex(sessionId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ['book-index', sessionId],
    queryFn: () => api.getBookIndex(sessionId ?? ''),
    enabled: Boolean(sessionId) && enabled,
    retry: false,
  })
}

export function useScriptVersions(sessionId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ['script-versions', sessionId],
    queryFn: () => api.listVersions(sessionId ?? ''),
    enabled: Boolean(sessionId) && enabled,
  })
}

export function useScriptVersionDetail(
  sessionId: string | null,
  versionId: string | null,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ['script-version-detail', sessionId, versionId],
    queryFn: () => api.getVersion(sessionId ?? '', versionId ?? ''),
    enabled: Boolean(sessionId) && Boolean(versionId) && enabled,
  })
}

export function useSaveScriptYaml() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({
      sessionId,
      payload,
    }: {
      sessionId: string
      payload: ScriptUserEditRequest
    }) => api.saveScriptYaml(sessionId, payload),
    onSuccess: (_response, variables) => {
      void client.invalidateQueries({ queryKey: sessionsKey })
      void client.invalidateQueries({
        queryKey: sessionDetailKey(variables.sessionId),
      })
      void client.invalidateQueries({
        queryKey: ['script-versions', variables.sessionId],
      })
      void client.invalidateQueries({
        queryKey: ['script-version-detail', variables.sessionId],
      })
    },
  })
}

export async function refreshSessionAssets(
  client: ReturnType<typeof useQueryClient>,
  sessionId: string,
): Promise<ChatSessionDetail | null> {
  await client.invalidateQueries({ queryKey: sessionsKey })
  await client.invalidateQueries({ queryKey: sessionDetailKey(sessionId) })
  await client.invalidateQueries({ queryKey: ['chapters', sessionId] })
  await client.invalidateQueries({ queryKey: ['book-index', sessionId] })
  await client.invalidateQueries({ queryKey: ['script-versions', sessionId] })
  try {
    return await api.getSession(sessionId)
  } catch {
    return null
  }
}

export type IntakeSession = {
  session_id: string;
  status: string;
  schema_version: string;
};

export type IntakeFieldState = {
  field_key: string;
  mandatory: boolean;
  human_only: boolean;
  value?: string;
  origin?: 'ai_extracted' | 'human_entered';
};

export type IntakeResult = {
  request_id: string;
  field_updates: Array<{ field_key: string; value: string; origin: 'ai_extracted' }>;
  clarification: { field_key: string; question: string } | null;
  status: string;
};

type FieldResponse = {
  session_id: string;
  schema_version: string;
  sections: Array<{ section_key: string; fields: IntakeFieldState[] }>;
  status: string;
};

type FetchOptions = Parameters<typeof fetch>[1];

const apiOrigin = import.meta.env.VITE_API_ORIGIN ?? '';

async function request<T>(path: string, init?: FetchOptions): Promise<T> {
  const response = await fetch(`${apiOrigin}${path}`, {
    ...init,
    credentials: 'include',
    headers: { ...(init?.headers ?? {}) },
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body?.error?.message ?? 'Request could not be processed.');
  return body as T;
}

export function createSession(): Promise<IntakeSession> {
  return request('/api/v1/sessions', { method: 'POST' });
}

export function getFieldState(sessionId: string): Promise<FieldResponse> {
  return request(`/api/v1/sessions/${encodeURIComponent(sessionId)}/fields`);
}

export function sendMessage(sessionId: string, text: string): Promise<IntakeResult> {
  return request(`/api/v1/sessions/${encodeURIComponent(sessionId)}/messages`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ request_id: crypto.randomUUID(), text }),
  });
}

function sourceType(file: File): string {
  const extension = file.name.split('.').pop()?.toLowerCase();
  if (extension && ['pdf', 'docx', 'pptx', 'wav', 'mp3', 'webm'].includes(extension)) return extension;
  const mimeTypes: Record<string, string> = {
    'application/pdf': 'pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
    'audio/wav': 'wav',
    'audio/mpeg': 'mp3',
    'audio/webm': 'webm',
  };
  return mimeTypes[file.type] ?? '';
}

export function uploadSource(sessionId: string, file: File): Promise<IntakeResult> {
  const type = sourceType(file);
  if (!type) return Promise.reject(new Error('Unsupported source.'));
  return request(`/api/v1/sessions/${encodeURIComponent(sessionId)}/sources/${type}`, {
    method: 'POST',
    headers: {
      'content-type': file.type || 'application/octet-stream',
      'x-source-name': file.name,
      'x-request-id': crypto.randomUUID(),
    },
    body: file,
  });
}

export function connectIntakeSocket(sessionId: string): Promise<{
  sendMessage: (text: string) => Promise<IntakeResult>;
  close: () => void;
} | null> {
  const origin = apiOrigin || window.location.origin;
  const socketUrl = new URL(`/api/v1/sessions/${encodeURIComponent(sessionId)}/stream`, origin);
  socketUrl.protocol = socketUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  return new Promise((resolve) => {
    let socket: WebSocket;
    try {
      socket = new WebSocket(socketUrl, 'aimplify.intake.v1');
    } catch {
      resolve(null);
      return;
    }
    const timeout = window.setTimeout(() => {
      socket.close();
      resolve(null);
    }, 1200);
    socket.addEventListener('open', () => {
      window.clearTimeout(timeout);
      resolve({
        sendMessage: (text) => new Promise((complete, fail) => {
          const requestId = crypto.randomUUID();
          const updates: IntakeResult['field_updates'] = [];
          let clarification: IntakeResult['clarification'] = null;
          let timeout: number;
          const cleanup = () => {
            window.clearTimeout(timeout);
            socket.removeEventListener('message', onEvent);
            socket.removeEventListener('close', onClose);
          };
          const failRequest = () => {
            cleanup();
            fail(new Error('Message could not be processed.'));
          };
          const onEvent = (event: MessageEvent<string>) => {
            const data = JSON.parse(event.data);
            if (data.request_id !== requestId) return;
            if (data.type === 'server.field.updated') updates.push(data.payload);
            if (data.type === 'server.clarification') clarification = data.payload;
            if (data.type === 'server.error') {
              failRequest();
            }
            if (data.type === 'server.submission.status') {
              cleanup();
              complete({ request_id: requestId, field_updates: updates, clarification, status: data.payload.status });
            }
          };
          const onClose = () => failRequest();
          timeout = window.setTimeout(failRequest, 15000);
          socket.addEventListener('message', onEvent);
          socket.addEventListener('close', onClose, { once: true });
          socket.send(JSON.stringify({ type: 'client.message', request_id: requestId, payload: { text } }));
        }),
        close: () => socket.close(),
      });
    });
    socket.addEventListener('error', () => {
      window.clearTimeout(timeout);
      socket.close();
      resolve(null);
    }, { once: true });
  });
}
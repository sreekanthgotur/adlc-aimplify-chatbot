import { useEffect, useState } from 'react';
import { IntakeChat } from './components/IntakeChat';
import { SourcePicker } from './components/SourcePicker';
import {
  connectIntakeSocket,
  createSession,
  getFieldState,
  IntakeFieldState,
  IntakeResult,
  sendMessage,
  uploadSource,
} from './services/intake';

export default function App() {
  const [sessionId, setSessionId] = useState<string>();
  const [fields, setFields] = useState<IntakeFieldState[]>([]);
  const [status, setStatus] = useState('Starting secure session');
  const [error, setError] = useState('');
  const [sendOverSocket, setSendOverSocket] = useState<((text: string) => Promise<IntakeResult>)>();

  useEffect(() => {
    let active = true;
    let closeSocket: (() => void) | undefined;
    createSession()
      .then(async (session) => {
        const state = await getFieldState(session.session_id);
        if (!active) return;
        setSessionId(session.session_id);
        setFields(state.sections.flatMap((section) => section.fields));
        setStatus(state.status);
        if (import.meta.env.MODE !== 'test') {
          const connection = await connectIntakeSocket(session.session_id);
          if (active && connection) {
            setSendOverSocket(() => connection.sendMessage);
            closeSocket = connection.close;
          } else {
            connection?.close();
          }
        }
      })
      .catch(() => {
        if (active) {
          setError('Your session could not be opened. Please try again.');
          setStatus('Unavailable');
        }
      });
    return () => {
      active = false;
      closeSocket?.();
    };
  }, []);

  async function handleMessage(text: string): Promise<IntakeResult> {
    if (!sessionId) throw new Error('Session is unavailable.');
    setError('');
    try {
      const result = sendOverSocket ? await sendOverSocket(text) : await sendMessage(sessionId, text);
      applyResult(result);
      return result;
    } catch {
      setSendOverSocket(undefined);
      try {
        const result = await sendMessage(sessionId, text);
        applyResult(result);
        return result;
      } catch {
        setError('Your message could not be processed. Please try again.');
        throw new Error('Message could not be processed.');
      }
    }
  }

  async function handleSource(file: File): Promise<void> {
    if (!sessionId) return;
    setError('');
    try {
      const result = await uploadSource(sessionId, file);
      applyResult(result);
    } catch {
      setError('This source could not be processed.');
    }
  }

  function applyResult(result: IntakeResult) {
    setStatus(result.status);
    setFields((current) => {
      const next = new Map(current.map((field) => [field.field_key, field]));
      for (const update of result.field_updates) {
        const existing = next.get(update.field_key);
        if (existing) next.set(update.field_key, { ...existing, value: update.value, origin: update.origin });
      }
      return [...next.values()];
    });
  }

  return (
    <main className="workspace">
      <header className="topbar">
        <a className="brand" href="#intake" aria-label="AIMPLIFY home">
          <span className="brand-mark" aria-hidden="true">A</span>
          <span>AIMPLIFY <small>IDEA INTAKE</small></span>
        </a>
        <div className="session-status"><span className="status-dot" />{status.replace(/_/g, ' ')}</div>
      </header>

      <div className="work-area" id="intake">
        <section className="conversation-column" aria-label="Idea conversation">
          <div className="conversation-heading">
            <div>
              <p className="eyebrow">NEW SUBMISSION</p>
              <h1>Tell us about your idea</h1>
              <p className="subheading">Start with the problem you want to solve. Add a document or audio note whenever it helps.</p>
            </div>
            <span className="step-marker"><span>01</span> / 03</span>
          </div>

          <IntakeChat onSend={handleMessage} disabled={!sessionId} />
          <SourcePicker disabled={!sessionId} onSelect={handleSource} />
          {error && <p className="error-message" role="alert">{error}</p>}
          <p className="privacy-note"><span aria-hidden="true">*</span> Source files and conversation text are processed temporarily.</p>
        </section>

        <aside className="details-column" aria-label="Submission details">
          <div className="details-title">
            <div>
              <p className="eyebrow">LIVE INTAKE</p>
              <h2>Captured details</h2>
            </div>
            <span className="count-badge">{fields.filter((field) => field.value).length} / {fields.length || 27}</span>
          </div>
          {fields.length ? (
            <div className="field-list">
              {fields.filter((field) => field.value).map((field) => (
                <div className="field-row" key={field.field_key}>
                  <span>{field.field_key.replace(/_/g, ' ')}</span>
                  <strong>{field.value}</strong>
                </div>
              ))}
              {!fields.some((field) => field.value) && <p className="empty-state">Your accepted details will appear here as you go.</p>}
            </div>
          ) : <p className="empty-state">Preparing your submission…</p>}
          <div className="section-progress">
            <div className="progress-caption"><span>Submission progress</span><strong>{fields.length ? Math.round((fields.filter((field) => field.value).length / fields.length) * 100) : 0}%</strong></div>
            <div className="progress-track"><span style={{ width: `${fields.length ? (fields.filter((field) => field.value).length / fields.length) * 100 : 0}%` }} /></div>
            <p>Declarations stay under your control and are completed at review.</p>
          </div>
        </aside>
      </div>
      <footer className="page-footer"><span>IDEA INTAKE</span><span>Secure employee workspace</span></footer>
    </main>
  );
}

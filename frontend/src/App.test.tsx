import { render, screen } from '@testing-library/react';
import { afterEach, vi } from 'vitest';
import App from './App';

describe('App', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('renders the intake application heading', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ session_id: 'session-test', status: 'in_progress', schema_version: 'active' }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ session_id: 'session-test', schema_version: 'active', sections: [], status: 'in_progress' }))));
    render(<App />);

    await screen.findByRole('textbox', { name: /message/i });
    expect(screen.getByRole('heading', { name: /tell us about your idea/i })).toBeInTheDocument();
  });

  it('offers organization sign-in when the API requires authentication', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        error: { code: 'UNAUTHENTICATED', message: 'Authentication is required.' },
      }), { status: 401 }),
    ));
    render(<App />);

    expect(await screen.findByRole('link', { name: /sign in with your organization/i }))
      .toHaveAttribute('href', '/auth/login');
  });
});

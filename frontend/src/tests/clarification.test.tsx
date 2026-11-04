import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { IntakeChat } from '../components/IntakeChat';

describe('clarification pacing', () => {
  it('renders one focused prompt per turn and sends its answer as the next message', async () => {
    const onSend = vi.fn()
      .mockResolvedValueOnce({
        request_id: 'turn-1',
        field_updates: [{ field_key: 'problem_statement', value: 'A safe update', origin: 'ai_extracted' }],
        clarification: { field_key: 'idea_title', question: 'What is the idea title?' },
        status: 'in_progress',
      })
      .mockResolvedValueOnce({
        request_id: 'turn-2',
        field_updates: [],
        clarification: { field_key: 'idea_category', question: 'Which category fits the idea?' },
        status: 'in_progress',
      });
    render(<IntakeChat disabled={false} onSend={onSend} />);

    fireEvent.change(screen.getByRole('textbox', { name: /message/i }), {
      target: { value: 'Start with the problem' },
    });
    fireEvent.click(screen.getByRole('button', { name: /send/i }));

    const firstPrompt = await screen.findByRole('group', { name: 'Clarification' });
    expect(within(firstPrompt).getByText('What is the idea title?')).toBeInTheDocument();
    expect(within(firstPrompt).queryByText('A safe update')).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole('textbox', { name: /message/i }), {
      target: { value: 'A thoughtful idea title' },
    });
    fireEvent.click(screen.getByRole('button', { name: /send/i }));

    expect(await screen.findByText('Which category fits the idea?')).toBeInTheDocument();
    expect(onSend).toHaveBeenNthCalledWith(2, 'A thoughtful idea title');
    expect(screen.getAllByRole('group', { name: 'Clarification' })).toHaveLength(2);
  });
});
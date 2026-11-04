type Props = {
  question: string;
};

export function ClarificationPrompt({ question }: Props) {
  return (
    <div className="clarification-prompt" role="group" aria-label="Clarification">
      <p>{question}</p>
    </div>
  );
}
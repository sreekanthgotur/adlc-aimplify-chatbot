type Props = {
  disabled: boolean;
  onSelect: (file: File) => void;
};

export function SourcePicker({ disabled, onSelect }: Props) {
  return (
    <div className="source-picker">
      <div className="source-icon" aria-hidden="true">+</div>
      <div className="source-copy">
        <strong>Add a source</strong>
        <span>PDF, Word, PowerPoint, WAV, MP3 or WebM</span>
      </div>
      <label className="source-button" htmlFor="intake-source">Choose file</label>
      <input
        id="intake-source"
        aria-label="Choose a document or audio file"
        type="file"
        accept=".pdf,.docx,.pptx,.wav,.mp3,.webm,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation,audio/wav,audio/mpeg,audio/webm"
        disabled={disabled}
        onChange={(event) => {
          const file = event.currentTarget.files?.[0];
          if (file) onSelect(file);
          event.currentTarget.value = '';
        }}
      />
    </div>
  );
}
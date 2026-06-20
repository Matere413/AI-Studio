export function StatusBar() {
  return (
    <div
      className="absolute right-6 top-6 flex items-center gap-2 font-mono text-[11px] leading-none tracking-caps text-accent"
      role="status"
      aria-live="polite"
    >
      <span className="pulse-status size-2 rounded-full bg-accent" />
      GENERATING...
    </div>
  );
}

/** ProofLab's mark: a summation sign (Σ), drawn as a path so it looks the same everywhere. */
export function SigmaMark({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden focusable="false">
      <path
        d="M24 10.5V6.5H8.5L17 16L8.5 25.5H24V21.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="3.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

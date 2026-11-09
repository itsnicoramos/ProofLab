import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md space-y-3 py-16 text-center">
      <h1 className="text-2xl">Not found</h1>
      <p className="text-muted">
        This site is now one page about the ProofLab tutor. The practice pages have moved into your
        coding agent.
      </p>
      <Link href="/" className="inline-flex h-11 items-center text-accent hover:underline">
        See what /tutor does
      </Link>
    </div>
  );
}

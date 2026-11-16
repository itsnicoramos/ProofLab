import Link from "next/link";

export default function NotFound() {
  return (
    <div className="max-w-xl space-y-3 py-16">
      <h1 className="text-2xl">Not found</h1>
      <p className="text-muted">
        This site is now one page about the ProofLab tutor. The practice pages have moved into your
        coding agent.
      </p>
      <Link href="/" className="link inline-flex h-11 items-center">
        See what /tutor does
      </Link>
    </div>
  );
}

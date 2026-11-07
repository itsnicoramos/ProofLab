import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md space-y-3 py-16 text-center">
      <h1 className="text-2xl font-semibold">Not found</h1>
      <p className="text-muted">That course or problem doesn&apos;t exist (or has been retired).</p>
      <Link href="/" className="inline-block text-accent hover:underline">
        Back to courses
      </Link>
    </div>
  );
}

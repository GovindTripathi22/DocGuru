import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col items-center justify-center gap-4 px-6 text-center text-zinc-100">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="text-sm text-zinc-400">The requested page does not exist.</p>
      <Link
        href="/"
        className="rounded-lg border border-zinc-700 px-4 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
      >
        Return to DocGuru
      </Link>
    </main>
  );
}

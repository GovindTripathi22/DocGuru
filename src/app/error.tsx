"use client";

export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col items-center justify-center gap-4 px-6 text-center text-zinc-100">
      <h1 className="text-2xl font-semibold">Something went wrong</h1>
      <p role="alert" className="text-sm text-zinc-400">
        The page could not finish loading. Your uploaded files remain on the server until their retention period expires.
      </p>
      <button
        type="button"
        onClick={reset}
        className="rounded-lg border border-zinc-700 px-4 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
      >
        Try again
      </button>
    </main>
  );
}

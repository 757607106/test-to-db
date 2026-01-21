"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html>
      <body>
        <div className="flex min-h-screen flex-col items-center justify-center p-4">
          <div className="text-center">
            <h2 className="mb-4 text-2xl font-bold text-red-600">
              应用发生严重错误
            </h2>
            <p className="mb-4 text-gray-600">
              {error.message || "发生了一个意外错误"}
            </p>
            <button
              onClick={reset}
              className="rounded-md bg-blue-500 px-4 py-2 text-white hover:bg-blue-600"
            >
              重试
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}

import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-4">
      <div className="text-center">
        <h2 className="mb-4 text-2xl font-bold text-gray-800">404 - 页面未找到</h2>
        <p className="mb-4 text-gray-600">您访问的页面不存在</p>
        <Link
          href="/"
          className="rounded-md bg-blue-500 px-4 py-2 text-white hover:bg-blue-600"
        >
          返回首页
        </Link>
      </div>
    </div>
  );
}

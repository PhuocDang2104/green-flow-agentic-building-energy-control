/** @type {import('next').NextConfig} */
const API_ORIGIN = process.env.API_ORIGIN || "http://localhost:8000";

const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  webpack: (config, { isServer }) => {
    if (!isServer) {
      // @xeokit/xeokit-sdk references node builtins it never uses in browser
      config.resolve.fallback = { ...config.resolve.fallback, fs: false, path: false };
    }
    return config;
  },
  async rewrites() {
    // In production Caddy routes /api,/ws,/storage to the backend; these
    // rewrites give the same topology in `next dev`.
    return [
      { source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` },
      { source: "/storage/:path*", destination: `${API_ORIGIN}/storage/:path*` },
    ];
  },
};

export default nextConfig;

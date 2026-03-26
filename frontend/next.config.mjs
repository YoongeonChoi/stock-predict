/** @type {import('next').NextConfig} */
const backendProxyUrl = (process.env.BACKEND_PROXY_URL || "http://localhost:8000").replace(/\/+$/, "");

const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendProxyUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;

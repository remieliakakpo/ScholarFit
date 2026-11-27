/** @type {import('next').NextConfig} */
// Le navigateur appelle /api/... sur le même port que le site ; Next.js relaie vers FastAPI.
// Pas de CORS, pas de souci localhost / IPv6 sous Windows, et ça marche aussi si le site
// est ouvert par 127.0.0.1 ou depuis un autre port.
const API = process.env.API_URL_INTERNAL || "http://127.0.0.1:8000";
const nextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};
export default nextConfig;

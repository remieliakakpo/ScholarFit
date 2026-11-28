/** @type {import('next').NextConfig} */
// Le navigateur appelle /api/... sur le même port que le site ; Next.js relaie vers FastAPI.
// Pas de CORS, pas de souci localhost / IPv6 sous Windows, et ça marche aussi si le site
// est ouvert par 127.0.0.1 ou depuis un autre port.
const API = process.env.API_URL_INTERNAL || "http://127.0.0.1:8000";
const nextConfig = {
  output: "standalone",
  // Dossier de compilation séparé possible (ex. tester une compilation de production pendant que
  // « npm run dev » tourne) : NEXT_DIST_DIR=.next-prod npm run build
  distDir: process.env.NEXT_DIST_DIR || ".next",
  poweredByHeader: false,
  // En-têtes de sécurité du navigateur (le site ne peut pas être affiché dans la page d'un autre site, etc.)
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Frame-Options", value: "SAMEORIGIN" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
      ],
    }];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};
export default nextConfig;

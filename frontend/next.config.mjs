/** @type {import('next').NextConfig} */
// Le navigateur appelle /api/... sur le même port que le site ; Next.js relaie vers FastAPI.
// Pas de CORS, pas de souci localhost / IPv6 sous Windows, et ça marche aussi si le site
// est ouvert par 127.0.0.1 ou depuis un autre port.
const API = process.env.API_URL_INTERNAL || "http://127.0.0.1:8000";
// En-têtes de sécurité sur toutes les pages : pas d'affichage dans un cadre d'un autre site
// (clickjacking), pas de devinette du type de fichier, adresse de la page non transmise aux autres sites.
const SECURITY_HEADERS = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  ...(process.env.NODE_ENV === "production" ? [{ key: "Strict-Transport-Security", value: "max-age=31536000" }] : []),
];
const nextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};
export default nextConfig;

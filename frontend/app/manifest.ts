import type { MetadataRoute } from "next";

// Application installable (« Ajouter à l'écran d'accueil ») : servie sur /manifest.webmanifest.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ScholarFit : les bourses d'études qui vous correspondent",
    short_name: "ScholarFit",
    description: "Bourses, stages et conférences auxquels vous avez droit, votre dossier préparé et le suivi de vos candidatures.",
    lang: "fr",
    start_url: "/mes-bourses?source=app",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#0a1016",
    theme_color: "#0a1016",
    categories: ["education"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Mes bourses", url: "/mes-bourses", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
      { name: "Suivi des candidatures", url: "/suivi", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
    ],
  };
}

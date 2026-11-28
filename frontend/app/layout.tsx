import type { Metadata } from "next";
import { Montserrat, Poppins } from "next/font/google";
import "./globals.css";
import { LangProvider } from "@/components/LangProvider";
import Shell from "@/components/Shell";
import { getLang, getT } from "@/lib/i18n-server";
import { THEME_SCRIPT } from "@/lib/theme";
import AppRuntime from "@/components/AppRuntime";
import { LITE_SCRIPT } from "@/lib/pwa";

// Polices servies par le site lui-même (pas d'appel bloquant à Google Fonts au chargement)
const montserrat = Montserrat({ subsets: ["latin", "latin-ext"], weight: ["500", "600", "700", "800"], style: ["normal", "italic"], display: "swap", variable: "--font-montserrat" });
const poppins = Poppins({ subsets: ["latin", "latin-ext"], weight: ["400", "500", "600"], display: "swap", variable: "--font-poppins" });

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getT();
  return {
    // Adresse publique du site : sert aux liens absolus des aperçus (Open Graph) et au manifeste
    metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"),
    applicationName: "ScholarFit",
    title: { default: t("ScholarFit : les bourses d'études qui vous correspondent"), template: "%s · ScholarFit" },
    description: t("Trouvez les bourses d'études, stages et conférences auxquels vous avez droit, du bac au doctorat, avec votre dossier préparé et le suivi de vos candidatures."),
  };
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const lang = await getLang();
  return (
    <html lang={lang} suppressHydrationWarning className={`${montserrat.variable} ${poppins.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT + LITE_SCRIPT }} />
        <meta name="theme-color" content="#0a1016" />
      </head>
      <body className="min-h-screen">
        <LangProvider lang={lang}>
          <Shell>{children}</Shell>
          <AppRuntime />
        </LangProvider>
      </body>
    </html>
  );
}

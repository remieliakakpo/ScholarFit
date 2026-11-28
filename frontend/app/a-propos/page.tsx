import type { Metadata } from "next";
import Link from "next/link";
import LegalPage, { Section } from "@/components/LegalPage";
import { COMPANY } from "@/lib/legal";
import { getLang } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> {
  const en = (await getLang()) === "en";
  return {
    title: en ? "About ScholarFit" : "À propos de ScholarFit",
    description: en ? "Who we are, how we find scholarships and how we help applicants." : "Qui nous sommes, comment nous trouvons les bourses et comment nous aidons les candidats.",
  };
}

const FR: Section[] = [
  { h: "Notre mission", p: [
    "Chaque année, des milliers de bourses restent sans candidat faute d'être connues, pendant que des étudiants brillants renoncent devant des dossiers complexes. ScholarFit rassemble les bourses d'études, les stages et les conférences du monde entier, du bac au doctorat, et vous montre celles auxquelles vous avez réellement droit.",
  ] },
  { h: "Comment nous trouvons les offres", p: [[
    "Les sites officiels et les grands sites d'annonces de bourses, relus automatiquement chaque semaine.",
    "Une recherche ciblée sur 46 zones du monde pour trouver les programmes moins connus.",
    "Les stages des organisations internationales, via l'API ReliefWeb.",
  ], "Chaque semaine, les liens officiels sont testés et les offres closes sont retirées. La date de mise à jour figure sur chaque fiche."] },
  { h: "Ce que nous faisons pour vous", p: [[
    "Un score de compatibilité pour chaque offre, calculé sur votre nationalité, votre niveau, votre domaine, vos langues et votre âge.",
    "Les conditions, les pièces à fournir et les étapes de chaque candidature, au même endroit.",
    "Un CV et une lettre de motivation adaptés au pays et à la bourse visés.",
    "Des rappels avant chaque date limite.",
    "Si vous le souhaitez, un expert qui prépare et dépose votre candidature.",
  ]] },
  { h: "Nos engagements", p: [[
    "Vos données servent uniquement à votre candidature. Elles ne sont ni vendues ni utilisées pour de la publicité.",
    "Les prix sont affichés avant tout paiement, sans frais cachés.",
    "Postuler seul reste gratuit : la recherche, le matching, les fiches détaillées et le suivi sont accessibles à tous.",
  ]] },
  { h: "Nous contacter", p: [
    `${COMPANY.name} · ${COMPANY.address}`,
    `E-mail : ${COMPANY.email} · Téléphone et WhatsApp : ${COMPANY.phone}`,
  ] },
];

const EN: Section[] = [
  { h: "Our mission", p: [
    "Every year, thousands of scholarships go without applicants because nobody knows about them, while brilliant students give up in front of complex applications. ScholarFit brings together scholarships, internships and conferences from around the world, from secondary school to PhD, and shows you the ones you are actually eligible for.",
  ] },
  { h: "How we find opportunities", p: [[
    "Official websites and the main scholarship listing sites, read automatically every week.",
    "A targeted search across 46 regions of the world to find lesser-known programmes.",
    "Internships at international organisations, through the ReliefWeb API.",
  ], "Every week, official links are tested and closed listings are removed. The update date appears on every listing."] },
  { h: "What we do for you", p: [[
    "A fit score for each opportunity, based on your nationality, level, field, languages and age.",
    "Conditions, required documents and application steps, all in one place.",
    "A CV and cover letter tailored to the target country and scholarship.",
    "Reminders before every deadline.",
    "If you wish, an expert who prepares and submits your application.",
  ]] },
  { h: "Our commitments", p: [[
    "Your data is used only for your application. It is never sold or used for advertising.",
    "Prices are shown before any payment, with no hidden fees.",
    "Applying on your own stays free: search, matching, detailed listings and tracking are open to everyone.",
  ]] },
  { h: "Contact us", p: [
    `${COMPANY.name} · ${COMPANY.address}`,
    `Email: ${COMPANY.email} · Phone and WhatsApp: ${COMPANY.phone}`,
  ] },
];

export default async function Page() {
  const en = (await getLang()) === "en";
  return (
    <>
      <LegalPage
        eyebrow={en ? "About" : "À propos"}
        title={en ? "Scholarships that fit you, wherever they are in the world" : "Les bourses qui vous correspondent, où qu'elles soient dans le monde"}
        intro={en ? "ScholarFit helps students in Africa and around the world find funding for their studies and build strong applications." : "ScholarFit aide les étudiants d'Afrique et du monde entier à trouver un financement pour leurs études et à monter des dossiers solides."}
        sections={en ? EN : FR}
        links={en ? [["/conditions", "Terms of use"], ["/confidentialite", "Privacy policy"], ["/destinations", "Destinations"]] : [["/conditions", "Conditions d'utilisation"], ["/confidentialite", "Confidentialité"], ["/destinations", "Destinations"]]}
      />
      <div className="mx-auto mb-16 flex max-w-3xl flex-wrap gap-3 px-4 sm:px-6">
        <Link href="/bourses" className="btn-primary">{en ? "Browse scholarships" : "Voir les bourses"}</Link>
        <Link href="/questionnaire" className="btn-ghost">{en ? "Find my scholarships in 5 steps" : "Trouver mes bourses en 5 étapes"}</Link>
      </div>
    </>
  );
}

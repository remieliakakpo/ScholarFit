import type { Metadata } from "next";
import Link from "next/link";
import { getT } from "@/lib/i18n-server";

// Texte de départ, à faire relire avant la mise en ligne (loi applicable dans le pays de l'éditeur,
// coordonnées du responsable du traitement, durée de conservation retenue).
export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getT();
  return { title: t("Politique de confidentialité"), description: t("Quelles données ScholarFit garde, pourquoi, et comment les récupérer ou les effacer.") };
}

const SECTIONS: { h: string; p: string[] }[] = [
  {
    h: "Ce que nous gardons",
    p: [
      "Votre compte : adresse e-mail, mot de passe chiffré (nous ne pouvons pas le lire), langue choisie et dates d'inscription, de confirmation de l'adresse et d'acceptation de cette politique.",
      "Votre profil : identité, parcours, projet, langues, pays souhaités, coordonnées pour l'en-tête de vos CV et lettres, et le texte du CV que vous importez.",
      "Vos candidatures, CV adaptés, lettres, échanges avec votre conseiller et déclarations de paiement.",
      "Si vous les cochez, des situations sensibles (réfugié, handicap, revenus modestes…) : seulement pour trouver les bourses qui vous sont réservées, avec la date de votre accord.",
    ],
  },
  {
    h: "Pourquoi",
    p: [
      "Trouver les bourses auxquelles vous avez droit, préparer vos documents, suivre vos candidatures, vous accompagner si vous le demandez et vous prévenir des dates limites.",
      "Nous ne vendons pas vos données et n'affichons pas de publicité.",
    ],
  },
  {
    h: "Qui peut les voir",
    p: [
      "Vous. Le conseiller qui vous accompagne, seulement si vous avez demandé un accompagnement et accepté de partager votre dossier. Les administrateurs de ScholarFit, pour le support et la validation des paiements.",
      "Quand l'assistant IA est activé, le texte nécessaire (critères de recherche, CV, réponses pour la lettre) est envoyé à notre fournisseur d'IA pour produire la réponse, sans être utilisé pour entraîner ses modèles.",
    ],
  },
  {
    h: "Vos droits",
    p: [
      "Depuis votre profil, vous pouvez télécharger toutes vos données (fichier JSON), corriger vos informations, retirer votre accord pour les situations sensibles en les décochant, et supprimer définitivement votre compte avec tout ce qui s'y rattache.",
      "Pour toute autre demande, écrivez à l'équipe ScholarFit depuis l'adresse de votre compte.",
    ],
  },
  {
    h: "Sécurité",
    p: [
      "Connexion par cookie protégé (illisible par les scripts de la page), mots de passe chiffrés, tentatives de connexion limitées, déconnexion de tous vos appareils quand vous changez de mot de passe.",
    ],
  },
];

export default async function Page() {
  const { t } = await getT();
  return (
    <div className="mx-auto max-w-3xl space-y-8 py-6">
      <div>
        <p className="eyebrow">{t("Vos données")}</p>
        <h1 className="mt-2 text-[1.65rem] sm:text-3xl">{t("Politique de confidentialité")}</h1>
      </div>
      {SECTIONS.map((s) => (
        <section key={s.h} className="card space-y-3 p-6">
          <h2 className="text-lg font-semibold">{t(s.h)}</h2>
          {s.p.map((x) => <p key={x} className="text-sm leading-relaxed text-muted">{t(x)}</p>)}
        </section>
      ))}
      <p className="text-center text-sm"><Link href="/profil" className="text-brand hover:underline">{t("Gérer mes données depuis mon profil")}</Link></p>
    </div>
  );
}

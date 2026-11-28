import type { Metadata } from "next";
import LegalPage, { Section } from "@/components/LegalPage";
import { COMPANY } from "@/lib/legal";
import { getLang } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> {
  const en = (await getLang()) === "en";
  return { title: en ? "Terms of use" : "Conditions d'utilisation" };
}

const FR: Section[] = [
  { h: "1. Objet", p: [
    `Les présentes conditions encadrent l'utilisation du site ScholarFit, édité par ${COMPANY.name} (${COMPANY.address}). ScholarFit recense des bourses d'études, des stages et des conférences dans le monde entier, calcule leur compatibilité avec votre profil, vous aide à préparer votre CV et vos lettres de motivation et propose un accompagnement par des experts.`,
    "En créant un compte, vous acceptez ces conditions. Si vous n'êtes pas d'accord, n'utilisez pas le service.",
  ] },
  { h: "2. Votre compte", p: [
    "Un compte est nécessaire pour voir vos scores de compatibilité, préparer vos documents, suivre vos candidatures et demander un accompagnement. Vous vous engagez à fournir des informations exactes et à garder votre mot de passe confidentiel.",
    "Vous pouvez fermer votre compte à tout moment en écrivant à l'adresse de contact. Nous pouvons suspendre un compte utilisé de manière frauduleuse ou contraire à ces conditions.",
  ] },
  { h: "3. Les offres présentées", p: [
    "Les bourses, stages et conférences sont publiés par leurs organismes (gouvernements, universités, fondations, organisations internationales). ScholarFit les rassemble et les présente, vérifie chaque semaine que les liens officiels répondent et retire du site les offres closes ou dont le lien ne fonctionne plus.",
    "La décision d'attribution appartient uniquement à l'organisme qui finance. ScholarFit n'est pas mandaté par ces organismes et ne promet aucune admission ni aucun financement.",
  ] },
  { h: "4. CV et lettres de motivation", p: [
    "Le premier dossier (un CV et une lettre adaptés à une bourse) est offert. Ensuite, l'abonnement mensuel permet de préparer jusqu'à dix dossiers par période de trente jours. Le diagnostic du CV, les modifications manuelles et les téléchargements restent gratuits.",
    "Vous restez l'auteur de vos documents. Relisez-les avant de les envoyer : vous êtes responsable de l'exactitude des informations qu'ils contiennent.",
  ] },
  { h: "5. Accompagnement par un expert", p: [
    "L'offre Standard couvre une bourse, l'offre Premium trois bourses, selon le détail affiché sur la page Accompagnement au moment de la commande. L'expert commence la préparation de votre dossier dès la confirmation du paiement et dépose la candidature avec vous, avec une preuve de dépôt.",
    "Vous vous engagez à transmettre à temps les pièces demandées. Un dossier incomplet à la date limite ne peut pas être déposé ; dans ce cas, l'expert vous propose une autre bourse de même niveau.",
  ] },
  { h: "6. Prix et paiement", p: [
    "Les prix sont indiqués en francs CFA (XOF), toutes taxes comprises. Le paiement en ligne est traité par CinetPay (Mobile Money et cartes bancaires) ; ScholarFit ne reçoit ni ne conserve vos coordonnées bancaires ou votre code Mobile Money. Vous pouvez aussi payer par transfert sur nos numéros ; l'accès est alors activé après vérification par notre équipe.",
    "Chaque paiement confirmé donne lieu à un reçu envoyé par e-mail.",
  ] },
  { h: "7. Remboursement", p: [
    [
      "Abonnement : remboursable dans les sept jours suivant le paiement si aucun dossier n'a été préparé pendant la période.",
      "Accompagnement : remboursable intégralement tant que l'expert n'a pas commencé le travail, puis à hauteur de 50 % tant qu'aucune candidature n'a été déposée.",
      "Un refus de l'organisme qui finance ne donne pas lieu à remboursement : le service payé est la préparation et le dépôt du dossier.",
    ],
    "Pour demander un remboursement, écrivez à l'adresse de contact avec la référence du paiement. Le remboursement est fait sur le moyen de paiement utilisé, sous quatorze jours.",
  ] },
  { h: "8. Utilisation correcte du service", p: [
    "Il est interdit de copier massivement le contenu du site, de contourner les limites techniques, de déposer des documents qui ne vous appartiennent pas ou de fournir de fausses informations à un organisme par l'intermédiaire de ScholarFit.",
  ] },
  { h: "9. Responsabilité", p: [
    "ScholarFit met tout en œuvre pour que les informations publiées soient exactes et à jour. Les conditions, montants et dates de chaque programme sont fixés par l'organisme qui le finance et peuvent être modifiés par lui à tout moment.",
    "Notre responsabilité est limitée au montant que vous nous avez payé au cours des douze derniers mois.",
  ] },
  { h: "10. Données personnelles", p: [
    "Le traitement de vos données est décrit dans la politique de confidentialité, qui fait partie de ces conditions.",
  ] },
  { h: "11. Modification et droit applicable", p: [
    "Nous pouvons modifier ces conditions ; la date de mise à jour figure en haut de la page et vous êtes prévenu par e-mail de tout changement important. Ces conditions sont régies par le droit togolais. En cas de différend, une solution amiable est recherchée avant toute action devant les tribunaux de Lomé.",
    `Contact : ${COMPANY.email} · ${COMPANY.phone}`,
  ] },
];

const EN: Section[] = [
  { h: "1. Purpose", p: [
    `These terms govern the use of the ScholarFit website, published by ${COMPANY.name} (${COMPANY.address}). ScholarFit lists scholarships, internships and conferences worldwide, scores how well they fit your profile, helps you prepare your CV and cover letters and offers support from experts.`,
    "By creating an account, you accept these terms. If you do not agree, please do not use the service.",
  ] },
  { h: "2. Your account", p: [
    "An account is required to see your fit scores, prepare your documents, track your applications and request support. You agree to provide accurate information and to keep your password confidential.",
    "You may close your account at any time by writing to the contact address. We may suspend an account used fraudulently or in breach of these terms.",
  ] },
  { h: "3. Listed opportunities", p: [
    "Scholarships, internships and conferences are published by their providers (governments, universities, foundations, international organisations). ScholarFit gathers and presents them, checks every week that official links respond, and removes listings that are closed or whose link no longer works.",
    "The award decision belongs solely to the funding body. ScholarFit is not appointed by these bodies and does not promise any admission or funding.",
  ] },
  { h: "4. CVs and cover letters", p: [
    "Your first application pack (a CV and a letter tailored to one scholarship) is free. After that, the monthly subscription lets you prepare up to ten packs per thirty-day period. The CV review, manual edits and downloads remain free.",
    "You remain the author of your documents. Read them carefully before sending: you are responsible for the accuracy of the information they contain.",
  ] },
  { h: "5. Expert support", p: [
    "The Standard offer covers one scholarship and the Premium offer three scholarships, as detailed on the Support page at the time of ordering. The expert starts preparing your application as soon as payment is confirmed and submits it with you, with proof of submission.",
    "You agree to send the requested documents on time. An application that is incomplete on the deadline cannot be submitted; in that case, the expert offers you another scholarship at the same level.",
  ] },
  { h: "6. Prices and payment", p: [
    "Prices are shown in CFA francs (XOF), all taxes included. Online payment is processed by CinetPay (Mobile Money and bank cards); ScholarFit never receives or stores your card details or Mobile Money PIN. You can also pay by transfer to our numbers; access is then activated once our team has checked the payment.",
    "Every confirmed payment comes with a receipt sent by email.",
  ] },
  { h: "7. Refunds", p: [
    [
      "Subscription: refundable within seven days of payment if no pack was prepared during the period.",
      "Support: fully refundable until the expert has started work, then 50% refundable as long as no application has been submitted.",
      "A rejection by the funding body does not give rise to a refund: the paid service is the preparation and submission of the application.",
    ],
    "To request a refund, write to the contact address with the payment reference. Refunds are made to the original payment method within fourteen days.",
  ] },
  { h: "8. Fair use", p: [
    "You may not copy the site's content in bulk, bypass technical limits, upload documents that do not belong to you, or give false information to a provider through ScholarFit.",
  ] },
  { h: "9. Liability", p: [
    "ScholarFit does its utmost to keep published information accurate and up to date. The conditions, amounts and dates of each programme are set by its funding body, which may change them at any time.",
    "Our liability is limited to the amount you paid us over the last twelve months.",
  ] },
  { h: "10. Personal data", p: [
    "How we process your data is described in the privacy policy, which forms part of these terms.",
  ] },
  { h: "11. Changes and governing law", p: [
    "We may change these terms; the update date appears at the top of the page and you will be notified by email of any significant change. These terms are governed by Togolese law. Any dispute will first be settled amicably before any action before the courts of Lomé.",
    `Contact: ${COMPANY.email} · ${COMPANY.phone}`,
  ] },
];

export default async function Page() {
  const en = (await getLang()) === "en";
  return (
    <LegalPage
      eyebrow={en ? "Legal" : "Informations légales"}
      title={en ? "Terms of use" : "Conditions d'utilisation"}
      intro={en ? "What ScholarFit offers, what it costs, and what each party commits to." : "Ce que propose ScholarFit, ce que cela coûte, et ce à quoi chacun s'engage."}
      updated={en ? `Last updated: ${COMPANY.updatedEn}` : `Dernière mise à jour : ${COMPANY.updated}`}
      sections={en ? EN : FR}
      links={en ? [["/a-propos", "About"], ["/confidentialite", "Privacy policy"]] : [["/a-propos", "À propos"], ["/confidentialite", "Confidentialité"]]}
    />
  );
}

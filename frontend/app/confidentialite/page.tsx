import type { Metadata } from "next";
import LegalPage, { Section } from "@/components/LegalPage";
import { COMPANY } from "@/lib/legal";
import { getLang } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> {
  const en = (await getLang()) === "en";
  return { title: en ? "Privacy policy" : "Politique de confidentialité" };
}

const FR: Section[] = [
  { h: "Responsable du traitement", p: [
    `${COMPANY.name}, ${COMPANY.address}. Pour toute question sur vos données : ${COMPANY.email}.`,
    "Vos données sont traitées conformément à la loi togolaise n° 2019-014 du 29 octobre 2019 relative à la protection des données à caractère personnel, et au règlement européen (RGPD) pour les personnes qui résident dans l'Union européenne.",
  ] },
  { h: "Les données que nous recueillons", p: [[
    "Compte : adresse e-mail, mot de passe (enregistré sous forme chiffrée, jamais en clair), langue du site.",
    "Profil : nom, date de naissance, nationalités, pays de résidence, téléphone, ville, niveau d'études, domaine, moyenne, langues et scores de tests, expériences, projet, situations particulières que vous choisissez d'indiquer, genre si vous le précisez.",
    "CV et lettres : le texte de votre CV, les versions adaptées et les lettres préparées sur le site.",
    "Candidatures : les bourses suivies, leur statut, vos notes.",
    "Accompagnement : vos échanges avec l'expert, les rendez-vous et les documents envoyés ou livrés.",
    "Paiements : montant, date, référence et moyen de paiement. Vos coordonnées bancaires et votre code Mobile Money sont saisis chez CinetPay et ne nous sont jamais transmis.",
  ]] },
  { h: "Pourquoi nous les utilisons", p: [[
    "Calculer votre compatibilité avec chaque bourse et vous montrer celles auxquelles vous avez droit.",
    "Préparer votre CV et vos lettres de motivation.",
    "Vous envoyer les rappels avant les dates limites et les nouvelles bourses qui vous correspondent (désactivable depuis votre profil).",
    "Permettre à votre expert de préparer et de déposer votre candidature, si vous demandez un accompagnement.",
    "Encaisser vos paiements, envoyer vos reçus et tenir notre comptabilité.",
  ], "Nous ne vendons pas vos données et ne les utilisons pas pour de la publicité."] },
  { h: "Qui y a accès", p: [[
    "L'équipe ScholarFit, pour le support et la vérification des paiements.",
    "Votre expert, uniquement si vous demandez un accompagnement et donnez votre accord : il voit alors votre profil, votre CV et les candidatures concernées.",
    "CinetPay, pour traiter les paiements en ligne.",
    "Notre prestataire d'envoi d'e-mails, pour vous adresser les messages du site.",
    "Anthropic (modèle Claude), lorsque vous demandez la préparation d'un CV, d'une lettre ou un diagnostic : le texte nécessaire est transmis pour être rédigé, sans être utilisé pour entraîner leurs modèles.",
  ]] },
  { h: "Durée de conservation", p: [[
    "Compte, profil, CV et candidatures : tant que votre compte est ouvert, puis supprimés dans les trente jours suivant sa fermeture.",
    "Documents d'accompagnement : un an après la fin de l'accompagnement.",
    "Paiements et reçus : dix ans, comme l'exige la réglementation comptable.",
    "Journaux d'envoi d'e-mails : douze mois.",
  ]] },
  { h: "Vos droits", p: [
    "Vous pouvez à tout moment consulter, corriger ou supprimer vos données, vous opposer à leur utilisation, demander une copie dans un format lisible et retirer votre accord pour l'accompagnement. Vous corrigez votre profil et vos documents directement sur le site ; pour toute autre demande, écrivez-nous et nous répondons sous trente jours.",
    "Si vous estimez que vos droits ne sont pas respectés, vous pouvez saisir l'Instance de protection des données à caractère personnel (IPDCP) du Togo, ou l'autorité de protection des données de votre pays.",
  ] },
  { h: "Sécurité", p: [
    "Le site fonctionne uniquement en HTTPS. Les mots de passe sont chiffrés, la base de données est sauvegardée régulièrement et l'accès aux données est réservé aux personnes qui en ont besoin.",
  ] },
  { h: "Cookies", p: [
    "ScholarFit utilise seulement les éléments nécessaires au fonctionnement du site : votre session de connexion, la langue et le thème clair ou sombre. Aucun cookie publicitaire ni de mesure d'audience tierce.",
  ] },
];

const EN: Section[] = [
  { h: "Data controller", p: [
    `${COMPANY.name}, ${COMPANY.address}. For any question about your data: ${COMPANY.email}.`,
    "Your data is processed in accordance with Togolese Law No. 2019-014 of 29 October 2019 on the protection of personal data, and with the EU General Data Protection Regulation (GDPR) for people living in the European Union.",
  ] },
  { h: "The data we collect", p: [[
    "Account: email address, password (stored encrypted, never in plain text), site language.",
    "Profile: name, date of birth, nationalities, country of residence, phone, city, level of study, field, grade average, languages and test scores, experience, project, any specific circumstances you choose to share, gender if you specify it.",
    "CVs and letters: the text of your CV, tailored versions and letters prepared on the site.",
    "Applications: the scholarships you track, their status and your notes.",
    "Support: your messages with the expert, meetings and documents sent or delivered.",
    "Payments: amount, date, reference and payment method. Your card details and Mobile Money PIN are entered with CinetPay and are never passed to us.",
  ]] },
  { h: "Why we use it", p: [[
    "To score how well you fit each scholarship and show you the ones you are eligible for.",
    "To prepare your CV and cover letters.",
    "To send you reminders before deadlines and new matching scholarships (you can turn this off in your profile).",
    "To let your expert prepare and submit your application, if you request support.",
    "To collect payments, send receipts and keep our accounts.",
  ], "We do not sell your data and do not use it for advertising."] },
  { h: "Who can access it", p: [[
    "The ScholarFit team, for support and payment checks.",
    "Your expert, only if you request support and give your consent: they then see your profile, your CV and the applications concerned.",
    "CinetPay, to process online payments.",
    "Our email provider, to send you the site's messages.",
    "Anthropic (Claude model), when you ask for a CV, a letter or a review: the necessary text is sent to be written, and is not used to train their models.",
  ]] },
  { h: "How long we keep it", p: [[
    "Account, profile, CV and applications: as long as your account is open, then deleted within thirty days of closure.",
    "Support documents: one year after the support ends.",
    "Payments and receipts: ten years, as required by accounting rules.",
    "Email sending logs: twelve months.",
  ]] },
  { h: "Your rights", p: [
    "You can access, correct or delete your data at any time, object to its use, ask for a copy in a readable format and withdraw your consent for support. You can correct your profile and documents directly on the site; for any other request, write to us and we will reply within thirty days.",
    "If you believe your rights are not respected, you can contact Togo's personal data protection authority (IPDCP) or the data protection authority of your country.",
  ] },
  { h: "Security", p: [
    "The site runs on HTTPS only. Passwords are encrypted, the database is backed up regularly and access to data is limited to the people who need it.",
  ] },
  { h: "Cookies", p: [
    "ScholarFit only uses what the site needs to work: your sign-in session, language and light or dark theme. No advertising cookies and no third-party analytics.",
  ] },
];

export default async function Page() {
  const en = (await getLang()) === "en";
  return (
    <LegalPage
      eyebrow={en ? "Legal" : "Informations légales"}
      title={en ? "Privacy policy" : "Politique de confidentialité"}
      intro={en ? "Your profile and your CV are personal. Here is exactly what we do with them." : "Votre profil et votre CV sont personnels. Voici précisément ce que nous en faisons."}
      updated={en ? `Last updated: ${COMPANY.updatedEn}` : `Dernière mise à jour : ${COMPANY.updated}`}
      sections={en ? EN : FR}
      links={en ? [["/a-propos", "About"], ["/conditions", "Terms of use"]] : [["/a-propos", "À propos"], ["/conditions", "Conditions d'utilisation"]]}
    />
  );
}

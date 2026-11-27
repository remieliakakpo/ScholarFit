// Identité de l'éditeur, affichée dans les pages À propos, Conditions et Confidentialité.
// À renseigner dans frontend/.env (ou les variables du serveur) avant la mise en ligne.
export const COMPANY = {
  name: process.env.NEXT_PUBLIC_COMPANY_NAME || "ScholarFit",
  address: process.env.NEXT_PUBLIC_COMPANY_ADDRESS || "Lomé, Togo",
  email: process.env.NEXT_PUBLIC_CONTACT_EMAIL || "contact@scholarfit.org",
  phone: process.env.NEXT_PUBLIC_CONTACT_PHONE || "+228 98 64 55 43",
  updated: "26 novembre 2026",
  updatedEn: "26 November 2026",
};

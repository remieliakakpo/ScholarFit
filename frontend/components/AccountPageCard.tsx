import { Logo } from "./Icon";

/** Cadre commun des pages de compte (mot de passe oublié, réinitialisation, confirmation). */
export default function AccountPageCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-[70vh] items-center justify-center py-6">
      <div className="bg-grid pointer-events-none absolute inset-0 -z-10" />
      <div className="card w-full max-w-md p-6 shadow-[0_40px_120px_-30px_rgba(0,0,0,0.7)] sm:p-9">
        <Logo className="mb-6 h-7" />
        {children}
      </div>
    </div>
  );
}

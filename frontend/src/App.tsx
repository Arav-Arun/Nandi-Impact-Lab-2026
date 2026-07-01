import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useT, LanguageSwitcher } from "./lib/i18n";
import Overview from "./pages/Overview";
import Intake from "./pages/Intake";
import Operator from "./pages/Operator";
import Blast from "./pages/Blast";

function Tab({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `rounded-md px-3 py-1.5 text-[13px] font-semibold transition ${
          isActive
            ? "bg-[var(--ink)] text-white"
            : "text-[var(--ink-soft)] hover:bg-[var(--surface-2)] hover:text-[var(--ink)]"
        }`
      }
    >
      {label}
    </NavLink>
  );
}

export default function App() {
  const t = useT();
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-[var(--line)] bg-[var(--surface)]">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2.5 sm:px-4">
          <div className="flex items-center gap-2.5">
            <img src="/nandi-logo.png" alt="NANDI" className="h-8 w-8 shrink-0 object-contain sm:h-9 sm:w-9" />
            <div className="leading-tight">
              <div className="text-[15px] font-extrabold leading-none tracking-tight sm:text-[16px]">{t("app.name")}</div>
              <div className="mt-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--ink-faint)] sm:text-[10.5px]">
                {t("app.tagline")}
              </div>
            </div>
          </div>

          <nav className="order-3 -mx-3 flex w-[calc(100%+1.5rem)] items-center gap-1 overflow-x-auto px-3 sm:order-none sm:mx-0 sm:ml-2 sm:w-auto sm:overflow-visible sm:px-0">
            <Tab to="/overview" label={t("nav.overview")} />
            <Tab to="/intake" label={t("nav.report")} />
            <Tab to="/operator" label={t("nav.operator")} />
            <Tab to="/blast" label={t("nav.blast")} />
          </nav>

          <div className="ml-auto flex items-center gap-2.5">
            <span className="hidden items-center gap-1.5 rounded-md border border-[var(--line)] bg-[var(--surface-2)] px-2.5 py-1.5 text-[11px] font-semibold text-[var(--ink-soft)] md:inline-flex">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="text-[var(--accent)]">
                <path d="M12 21s-7-6-7-11a7 7 0 0 1 14 0c0 5-7 11-7 11z" /><circle cx="12" cy="10" r="2.5" />
              </svg>
              {t("app.place")}
            </span>
            <LanguageSwitcher />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1400px] px-4 py-5">
        <Routes>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/intake" element={<Intake />} />
          <Route path="/operator" element={<Operator />} />
          <Route path="/blast" element={<Blast />} />
        </Routes>
      </main>
    </div>
  );
}

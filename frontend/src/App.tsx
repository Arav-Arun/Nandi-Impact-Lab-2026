import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { Lotus } from "./design/Lotus";
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
        `rounded-full px-4 py-2 text-[13px] font-semibold transition ${
          isActive ? "bg-[var(--color-ink)] text-white" : "text-[var(--color-ink-soft)] hover:text-[var(--color-ink)]"
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
      <header className="sticky top-0 z-30 border-b border-[var(--color-line)] bg-white/75 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-5 py-3.5">
          <Lotus size={32} className="text-[var(--color-saffron)]" />
          <div className="leading-none">
            <div className="flex items-baseline gap-1.5">
              <span className="serif text-[19px] font-semibold tracking-tight">NANDI</span>
              <span className="deva text-[12px] font-semibold text-[var(--color-ink-soft)]">नंदी</span>
            </div>
            <div className="mt-1 text-[11px] text-[var(--color-ink-soft)]">{t("app.tagline")}</div>
          </div>
          <nav className="ml-auto flex items-center gap-0.5 rounded-full border border-[var(--color-line)] bg-white/80 p-1">
            <Tab to="/overview" label={t("nav.overview")} />
            <Tab to="/intake" label={t("nav.report")} />
            <Tab to="/operator" label={t("nav.operator")} />
            <Tab to="/blast" label={t("nav.blast")} />
          </nav>
          <LanguageSwitcher />
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-8">
        <Routes>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/intake" element={<Intake />} />
          <Route path="/operator" element={<Operator />} />
          <Route path="/blast" element={<Blast />} />
        </Routes>
      </main>

      <footer className="mx-auto max-w-6xl px-5 py-10 text-center">
        <p className="serif text-[15px] text-[var(--color-ink-soft)]">
          NANDI, the one who waits at the gate until everyone has come home.
        </p>
        <p className="mt-1 text-[11px] text-[var(--color-ink-soft)]">{t("app.place")}</p>
      </footer>
    </div>
  );
}

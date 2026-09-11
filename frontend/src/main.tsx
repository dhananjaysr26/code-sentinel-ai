import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";

import { ReviewPage }        from "./features/reviews/ReviewPage";
import { ReviewResultsPage } from "./features/reviews/ReviewResultsPage";
import { ReviewsListPage }   from "./features/reviews/ReviewsListPage";
import { OverviewPage }      from "./features/overview/OverviewPage";
import { ToastContainer }    from "./components/Toast";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});

// ── Top nav link ──────────────────────────────────────────────────────────────
function NavItem({ to, label, end }: { to: string; label: string; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `relative px-4 py-2 rounded-[8px] text-[13px] font-semibold transition-all duration-200 ease-out ${
          isActive
            ? "bg-[#f0effe] text-[#5b4de8]"
            : "text-slate-500 hover:text-slate-900 hover:bg-slate-100/80 active:bg-slate-200/60"
        }`
      }
    >
      {label}
    </NavLink>
  );
}

// ── Shield logo mark ──────────────────────────────────────────────────────────
function Logo() {
  return (
    <NavLink to="/" className="flex items-center gap-2.5 flex-shrink-0" aria-label="CodeSentinel AI home">
      <div className="w-8 h-8 rounded-lg bg-[#6d5dfb] flex items-center justify-center shadow-sm flex-shrink-0">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M8 1.5L3 4v4.5C3 11.6 5.2 14.4 8 15c2.8-.6 5-3.4 5-6.5V4L8 1.5z" fill="white" fillOpacity="0.95"/>
          <path d="M5.5 8l2 2 3-3.5" stroke="white" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
        </svg>
      </div>
      <div className="leading-tight">
        <span className="text-[15px] font-bold text-slate-900 tracking-tight">CodeSentinel</span>
        <span className="text-[15px] font-bold text-[#6d5dfb] tracking-tight"> AI</span>
      </div>
    </NavLink>
  );
}

// ── Persistent top navigation ─────────────────────────────────────────────────
function TopNav() {
  return (
    <header className="h-[60px] border-b border-slate-200 bg-white sticky top-0 z-40 shadow-[0_1px_3px_0_rgba(15,23,42,0.04)]">
      <div className="max-w-[1200px] mx-auto px-8 h-full flex items-center justify-between">
        {/* Logo */}
        <Logo />

        {/* Nav links (moved to right) */}
        <nav className="flex items-center gap-2 ml-auto" aria-label="Main navigation">
          <NavItem to="/" label="Overview" end />
          <NavItem to="/reviews" label="Reviews" />
          <NavItem to="/new" label="New review" />
        </nav>
      </div>
    </header>
  );
}

// ── Root app shell ─────────────────────────────────────────────────────────────
function AppShell() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col">
      <TopNav />

      {/* Page content — flex-1 lets the main area fill the remaining screen space */}
      <main className="flex-1 w-full max-w-[1200px] mx-auto px-6 md:px-8 py-10 md:py-14 flex flex-col">
        <Routes>
          <Route path="/"          element={<OverviewPage />} />
          <Route path="/reviews"   element={<ReviewsListPage />} />
          <Route path="/new"       element={<ReviewPage />} />
          <Route path="/review/:id" element={<ReviewResultsPage />} />
        </Routes>
      </main>

      <ToastContainer />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);

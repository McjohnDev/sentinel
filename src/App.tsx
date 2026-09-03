/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider, useApp } from './context/AppContext';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { ToastContainer } from './components/common/ToastContainer';
import { CommandPalette } from './components/layout/CommandPalette';

import { LoginView } from './views/LoginView';
import { DashboardView } from './views/DashboardView';
import { AgentsListView } from './views/AgentsListView';
import { AgentDetailView } from './views/AgentDetailView';
import { AlertsListView } from './views/AlertsListView';
import { SettingsView } from './views/SettingsView';
import { UsersView } from './views/UsersView';
import { IntegrationsView } from './views/IntegrationsView';
import { AuditView } from './views/AuditView';
import { ProfileView } from './views/ProfileView';
import { I18nProvider } from './i18n';

const LoginRoute: React.FC = () => {
  const { currentUser } = useApp();
  if (currentUser) return <Navigate to="/dashboard" replace />;
  return <LoginView />;
};

const MainLayout: React.FC = () => {
  const { currentUser } = useApp();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Un seul geste, deux points d'entree : la barre laterale et l'en-tete
  // ouvrent la meme palette plutot que d'en gerer chacun une copie.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  if (!currentUser) {
    return (
      <div className="min-h-screen font-sans antialiased">
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
        <ToastContainer />
      </div>
    );
  }

  return (
    <div
      className="flex min-h-screen font-sans antialiased"
      style={{
        // Une teinte de contenu personnalisee n'est jamais qu'un lavis a 14%
        // sur le fond du theme : au-dela, tout le texte courant de
        // l'application -- qui suppose un fond neutre -- deviendrait
        // difficile a lire loin de ce seul reglage.
        background: 'color-mix(in srgb, var(--content-tint, var(--color-bg)) 14%, var(--color-bg))',
        color: 'var(--color-tx)',
      }}
    >
      <Sidebar
        isMobileOpen={mobileSidebarOpen}
        onCloseMobile={() => setMobileSidebarOpen(false)}
        onOpenPalette={() => setPaletteOpen(true)}
      />

      <div className="flex-1 min-w-0 flex flex-col">
        <Header
          onToggleSidebarMobile={() => setMobileSidebarOpen(true)}
          onOpenPalette={() => setPaletteOpen(true)}
        />

        <main className="flex-1 px-4 sm:px-5 pt-4 pb-8 overflow-y-auto animate-fade-in">
          {/* Pas de centrage (`mx-auto`) : sur un ecran large, une colonne
              centree a 1280px laissait un vide symetrique enorme entre le
              contenu et la sidebar comme le bandeau. Le contenu s'appuie
              desormais contre la marge, plafonne pour rester lisible sur
              tres grand ecran. */}
          <div className="max-w-[1680px] space-y-6">
            <Routes>
              <Route path="/dashboard" element={<DashboardView />} />
              <Route path="/agents" element={<AgentsListView />} />
              <Route path="/fleet" element={<AgentsListView />} />
              <Route path="/agents/:id" element={<AgentDetailView />} />
              <Route path="/fleet/:id" element={<AgentDetailView />} />
              <Route path="/alerts" element={<AlertsListView />} />
              <Route path="/integrations" element={<IntegrationsView />} />
              <Route path="/settings" element={<SettingsView />} />
              <Route path="/users" element={<UsersView />} />
              <Route path="/audit" element={<AuditView />} />
              <Route path="/profile" element={<ProfileView />} />
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </div>
        </main>
      </div>

      <ToastContainer />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
};

export default function App() {
  return (
    <BrowserRouter>
      <I18nProvider>
        <AppProvider>
          <MainLayout />
        </AppProvider>
      </I18nProvider>
    </BrowserRouter>
  );
}

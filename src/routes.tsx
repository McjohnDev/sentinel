/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Navigate } from 'react-router-dom';
import { AppProvider, useApp } from './context/AppContext';

import { LoginView } from './views/LoginView';
import { DashboardView } from './views/DashboardView';
import { AgentsListView } from './views/AgentsListView';
import { AgentDetailView } from './views/AgentDetailView';
import { AlertsListView } from './views/AlertsListView';
import { SettingsView } from './views/SettingsView';
import { UsersView } from './views/UsersView';

// Protected Route Component
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { currentUser } = useApp();

  if (!currentUser) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

// Login Route Component
const LoginRoute: React.FC = () => {
  const { currentUser } = useApp();

  if (currentUser) {
    return <Navigate to="/dashboard" replace />;
  }

  return <LoginView />;
};

export const AppRoutes = () => {
  return (
    <>
      <LoginRoute />
      <ProtectedRoute>
        <DashboardView />
      </ProtectedRoute>
      <ProtectedRoute>
        <AgentsListView />
      </ProtectedRoute>
      <ProtectedRoute>
        <AgentDetailView />
      </ProtectedRoute>
      <ProtectedRoute>
        <AlertsListView />
      </ProtectedRoute>
      <ProtectedRoute>
        <SettingsView />
      </ProtectedRoute>
      <ProtectedRoute>
        <UsersView />
      </ProtectedRoute>
    </>
  );
};

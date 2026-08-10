/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Agent,
  Alert,
  User,
  Role,
  GlobalThresholds,
  MessagingNotificationConfig,
  ServicesMonitoringConfig,
  FilesMonitoringConfig,
  AvailabilityPolicy,
  DataRetentionConfig,
  EnrollmentToken,
  Toast,
  CustomThresholds,
} from '../types';
import { authService } from '../services/api/auth.service';
import { agentsService } from '../services/api/agents.service';
import { alertsService } from '../services/api/alerts.service';
import { usersService } from '../services/api/users.service';
import { settingsService } from '../services/api/settings.service';
import { DataMapper } from '../services/mappers/data.mapper';

interface AppContextType {
  currentUser: User | null;
  currentRole: Role;
  setCurrentRole: (role: Role) => void;
  selectedAgentId: string | null;
  setSelectedAgentId: (id: string | null) => void;
  agents: Agent[];
  alerts: Alert[];
  users: User[];
  globalThresholds: GlobalThresholds;
  messagingConfig: MessagingNotificationConfig;
  servicesMonitoringConfig: ServicesMonitoringConfig;
  filesMonitoringConfig: FilesMonitoringConfig;
  availabilityPolicy: AvailabilityPolicy;
  retentionConfig: DataRetentionConfig;
  enrollmentTokens: EnrollmentToken[];
  toasts: Toast[];
  autoRefresh: boolean;
  toggleAutoRefresh: () => void;
  refreshData: () => void;
  acknowledgeAlert: (alertId: string, comment?: string, operatorName?: string) => void;
  acknowledgeAllAlerts: (operatorName?: string, comment?: string) => void;
  revokeAgent: (agentId: string) => void;
  deleteAgent: (agentId: string) => void;
  updateAgentThresholds: (agentId: string, thresholds: CustomThresholds) => void;
  resetAgentThresholds: (agentId: string) => void;
  updateGlobalThresholds: (thresholds: GlobalThresholds) => void;
  updateMessagingConfig: (config: MessagingNotificationConfig) => void;
  updateServicesMonitoringConfig: (config: ServicesMonitoringConfig) => void;
  updateFilesMonitoringConfig: (config: FilesMonitoringConfig) => void;
  updateAvailabilityPolicy: (policy: AvailabilityPolicy) => void;
  updateRetentionConfig: (config: DataRetentionConfig) => void;
  generateEnrollmentToken: () => EnrollmentToken;
  createUser: (userData: { name: string; email: string; role: Role }) => void;
  updateUser: (userId: string, updates: Partial<User>) => void;
  deleteUser: (userId: string) => void;
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
  exportCSV: (type: 'agents' | 'alerts') => void;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  navigateToAgentDetail: (agentId: string) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

const STORAGE_KEY_PREFIX = 'cbc_supervision_v1_';

export const AppProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const navigate = useNavigate();

  // Load from LocalStorage or Fallback to null
  const [currentUser, setCurrentUser] = useState<User | null>(() => {
    const saved = localStorage.getItem(`${STORAGE_KEY_PREFIX}currentUser`);
    return saved ? JSON.parse(saved) : null;
  });

  const [currentRole, setCurrentRoleState] = useState<Role>(() => {
    return currentUser?.role || 'Admin';
  });

  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

  const [agents, setAgents] = useState<Agent[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [globalThresholds, setGlobalThresholds] = useState<GlobalThresholds>({
    cpuWarning: 80,
    cpuCritical: 90,
    ramWarning: 80,
    ramCritical: 90,
    diskWarning: 85,
    diskCritical: 95,
  });
  const [messagingConfig, setMessagingConfig] = useState<MessagingNotificationConfig>({
    recipients: [],
    apiEndpoint: '',
    apiKey: '',
    apiTimeout: 30,
    enabled: true,
  });
  const [servicesMonitoringConfig, setServicesMonitoringConfig] = useState<ServicesMonitoringConfig>({
    enabled: false,
    services: [],
    interval: 60,
  });
  const [filesMonitoringConfig, setFilesMonitoringConfig] = useState<FilesMonitoringConfig>({
    enabled: false,
    files: [],
    interval: 300,
  });
  const [availabilityPolicy, setAvailabilityPolicy] = useState<AvailabilityPolicy>({
    enabled: false,
    timeWindows: {},
    offlineThresholdSeconds: undefined,
  });
  const [retentionConfig, setRetentionConfig] = useState<DataRetentionConfig>({
    alertsDays: 30,
    heartbeatsDays: 7,
  });
  const [enrollmentTokens, setEnrollmentTokens] = useState<EnrollmentToken[]>([]);

  const [toasts, setToasts] = useState<Toast[]>([]);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(false);

  // Load data from API on mount if user is logged in
  useEffect(() => {
    const loadInitialData = async () => {
      if (!currentUser) return;

      setLoading(true);
      try {
        // Load agents
        const agentsData = await agentsService.getAgents();
        setAgents(agentsData);

        // Load alerts
        const alertsData = await alertsService.getAlerts();
        setAlerts(alertsData);

        // Load users
        const usersData = await usersService.getUsers();
        setUsers(usersData);

        // Load global thresholds
        const thresholdsData = await settingsService.getGlobalThresholds();
        setGlobalThresholds(thresholdsData);

        // Load email config
        const emailData = await settingsService.getEmailConfig();
        setEmailConfig(emailData);

        // Load retention config
        const retentionData = await settingsService.getRetentionConfig();
        setRetentionConfig(retentionData);

        // Load enrollment tokens
        const tokensData = await settingsService.getEnrollmentTokens();
        setEnrollmentTokens(tokensData);
      } catch (error) {
        console.error('Error loading initial data:', error);
      } finally {
        setLoading(false);
      }
    };

    loadInitialData();
  }, [currentUser]);

  // Sync states to localStorage
  useEffect(() => {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}agents`, JSON.stringify(agents));
  }, [agents]);

  useEffect(() => {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}alerts`, JSON.stringify(alerts));
  }, [alerts]);

  useEffect(() => {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}users`, JSON.stringify(users));
  }, [users]);

  useEffect(() => {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}globalThresholds`, JSON.stringify(globalThresholds));
  }, [globalThresholds]);

  useEffect(() => {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}emailConfig`, JSON.stringify(emailConfig));
  }, [emailConfig]);

  useEffect(() => {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}retentionConfig`, JSON.stringify(retentionConfig));
  }, [retentionConfig]);

  useEffect(() => {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}enrollmentTokens`, JSON.stringify(enrollmentTokens));
  }, [enrollmentTokens]);

  const addToast = (toast: Omit<Toast, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substring(2, 5)}`;
    const newToast: Toast = { ...toast, id };
    setToasts((prev) => [...prev, newToast]);

    // Auto dismiss after 5s
    setTimeout(() => {
      removeToast(id);
    }, 5000);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const setCurrentRole = (role: Role) => {
    setCurrentRoleState(role);
    if (currentUser) {
      const updatedUser = { ...currentUser, role };
      setCurrentUser(updatedUser);
      localStorage.setItem(`${STORAGE_KEY_PREFIX}currentUser`, JSON.stringify(updatedUser));
    }
    addToast({
      type: 'info',
      title: 'Changement de rôle',
      message: `Perspective changée pour: ${role === 'Admin' ? 'Administrateur' : role === 'Operator' ? 'Opérateur' : 'Lecture seule'}`,
    });
  };

  // Live Auto-Refresh ticker (simulates real-time CPU/RAM telemetries)
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      setAgents((prevAgents) =>
        prevAgents.map((ag) => {
          if (ag.status !== 'online') return ag;

          // Slightly shift CPU and RAM to create live realistic heartbeat feel
          const cpuDelta = (Math.random() - 0.5) * 6;
          const ramDelta = (Math.random() - 0.5) * 3;

          const newCpu = Math.min(99, Math.max(5, Math.round(ag.metrics.cpu + cpuDelta)));
          const newRam = Math.min(98, Math.max(10, Math.round(ag.metrics.ram + ramDelta)));

          const newCpuHistory = [...ag.metrics.cpuHistory.slice(1), newCpu];
          const newRamHistory = [...ag.metrics.ramHistory.slice(1), newRam];

          return {
            ...ag,
            lastHeartbeat: 'Il y a 2s',
            metrics: {
              ...ag.metrics,
              cpu: newCpu,
              ram: newRam,
              cpuHistory: newCpuHistory,
              ramHistory: newRamHistory,
            },
          };
        })
      );
    }, 10000);

    return () => clearInterval(interval);
  }, [autoRefresh]);

  const toggleAutoRefresh = () => {
    setAutoRefresh(!autoRefresh);
    addToast({
      type: 'info',
      title: 'Rafraîchissement automatique',
      message: !autoRefresh ? 'Télémétrie en temps réel activée (10s)' : 'Télémétrie automatique désactivée',
    });
  };

  const refreshData = () => {
    setAgents((prev) =>
      prev.map((ag) => ({
        ...ag,
        lastHeartbeat: ag.status === 'online' ? 'À l\'instant' : ag.lastHeartbeat,
      }))
    );
    addToast({
      type: 'success',
      title: 'Données actualisées',
      message: 'L\'état de santé et les métriques des agents ont été rafraîchis.',
    });
  };

  const navigateToAgentDetail = (agentId: string) => {
    setSelectedAgentId(agentId);
    navigate(`/agents/${agentId}`);
  };

  const acknowledgeAlert = (alertId: string, comment?: string, operatorName?: string) => {
    const operator = operatorName?.trim() || currentUser?.name || 'Opérateur CBC';
    setAlerts((prev) =>
      prev.map((alt) => {
        if (alt.id === alertId) {
          return {
            ...alt,
            status: 'acknowledged',
            acknowledgedBy: operator,
            acknowledgedAt: new Date().toISOString().replace('T', ' ').substring(0, 16),
            comment: comment?.trim() || alt.comment || 'Alerte prise en charge par l\'opérateur',
          };
        }
        return alt;
      })
    );

    // Update active alerts count on target agent
    const targetAlert = alerts.find((a) => a.id === alertId);
    if (targetAlert) {
      setAgents((prev) =>
        prev.map((ag) => {
          if (ag.id === targetAlert.agentId) {
            return {
              ...ag,
              activeAlertsCount: Math.max(0, ag.activeAlertsCount - 1),
            };
          }
          return ag;
        })
      );
    }

    addToast({
      type: 'success',
      title: 'Alerte acquittée',
      message: `L'alerte #${alertId} a été acquittée avec succès.`,
    });
  };

  const acknowledgeAllAlerts = (operatorName?: string, comment?: string) => {
    if (currentRole !== 'Admin') {
      addToast({
        type: 'error',
        title: 'Permission refusée',
        message: 'Seul un Administrateur peut acquitter toutes les alertes en lot.',
      });
      return;
    }

    const openCount = alerts.filter((a) => a.status === 'open').length;
    if (openCount === 0) {
      addToast({
        type: 'info',
        title: 'Aucune alerte ouverte',
        message: 'Toutes les alertes sont déjà acquittées ou résolues.',
      });
      return;
    }

    const now = new Date().toISOString().replace('T', ' ').substring(0, 16);
    const finalOperator = operatorName?.trim() || currentUser?.name || 'Administrateur CBC';
    const finalComment = comment?.trim() || 'Acquittement global en lot par l\'administrateur.';

    setAlerts((prev) =>
      prev.map((alt) =>
        alt.status === 'open'
          ? {
              ...alt,
              status: 'acknowledged',
              acknowledgedBy: finalOperator,
              acknowledgedAt: now,
              comment: finalComment,
            }
          : alt
      )
    );

    setAgents((prev) =>
      prev.map((ag) => ({
        ...ag,
        activeAlertsCount: 0,
      }))
    );

    addToast({
      type: 'success',
      title: 'Acquittement collectif',
      message: `${openCount} alerte(s) ont été acquittées simultanément.`,
    });
  };

  const revokeAgent = (agentId: string) => {
    if (currentRole !== 'Admin') {
      addToast({
        type: 'error',
        title: 'Permission refusée',
        message: 'Seul un Administrateur peut révoquer un agent.',
      });
      return;
    }

    setAgents((prev) =>
      prev.map((ag) => (ag.id === agentId ? { ...ag, status: 'revoked' } : ag))
    );

    addToast({
      type: 'warning',
      title: 'Agent révoqué',
      message: `L'agent #${agentId} a été révoqué. Il recevra un code 401 lors de sa prochaine tentative de connexion.`,
    });
  };

  const deleteAgent = (agentId: string) => {
    if (currentRole !== 'Admin') {
      addToast({
        type: 'error',
        title: 'Permission refusée',
        message: 'Seul un Administrateur peut supprimer un agent.',
      });
      return;
    }

    setAgents((prev) => prev.filter((ag) => ag.id !== agentId));
    setAlerts((prev) => prev.filter((alt) => alt.agentId !== agentId));

    if (selectedAgentId === agentId) {
      setSelectedAgentId(null);
      navigate('/agents');
    }

    addToast({
      type: 'success',
      title: 'Agent supprimé',
      message: `L'agent et tout son historique ont été retirés du système.`,
    });
  };

  const updateAgentThresholds = (agentId: string, thresholds: CustomThresholds) => {
    setAgents((prev) =>
      prev.map((ag) => (ag.id === agentId ? { ...ag, customThresholds: thresholds } : ag))
    );
    addToast({
      type: 'success',
      title: 'Seuils mis à jour',
      message: `Seuils d'alerte personnalisés enregistrés pour l'agent.`,
    });
  };

  const resetAgentThresholds = (agentId: string) => {
    setAgents((prev) =>
      prev.map((ag) => {
        if (ag.id === agentId) {
          const { customThresholds, ...rest } = ag;
          return rest;
        }
        return ag;
      })
    );
    addToast({
      type: 'info',
      title: 'Seuils réinitialisés',
      message: `L'agent utilise désormais les seuils globaux du système.`,
    });
  };

  const updateGlobalThresholds = (thresholds: GlobalThresholds) => {
    setGlobalThresholds(thresholds);
    addToast({
      type: 'success',
      title: 'Paramètres enregistrés',
      message: 'Les seuils d\'alerte globaux ont été appliqués.',
    });
  };

  const updateMessagingConfig = (config: MessagingNotificationConfig) => {
    setMessagingConfig(config);
    addToast({
      type: 'success',
      title: 'Configuration mise à jour',
      message: 'La configuration de messagerie a été mise à jour avec succès.',
    });
  };

  const updateServicesMonitoringConfig = (config: ServicesMonitoringConfig) => {
    setServicesMonitoringConfig(config);
    addToast({
      type: 'success',
      title: 'Configuration mise à jour',
      message: 'La configuration de supervision des services a été mise à jour avec succès.',
    });
  };

  const updateFilesMonitoringConfig = (config: FilesMonitoringConfig) => {
    setFilesMonitoringConfig(config);
    addToast({
      type: 'success',
      title: 'Configuration mise à jour',
      message: 'La configuration de supervision des fichiers a été mise à jour avec succès.',
    });
  };

  const updateAvailabilityPolicy = (policy: AvailabilityPolicy) => {
    setAvailabilityPolicy(policy);
    addToast({
      type: 'success',
      title: 'Configuration mise à jour',
      message: 'La politique de disponibilité a été mise à jour avec succès.',
    });
  };

  const updateRetentionConfig = (config: DataRetentionConfig) => {
    setRetentionConfig(config);
    addToast({
      type: 'success',
      title: 'Politique de rétention mise à jour',
      message: 'La durée de conservation des données a été modifiée.',
    });
  };

  const generateEnrollmentToken = (): EnrollmentToken => {
    const randomHex = Math.random().toString(36).substring(2, 7).toUpperCase();
    const tokenString = `CBC-ENROLL-${randomHex}-${new Date().getFullYear()}`;
    const now = new Date();
    const expires = new Date(now.getTime() + 24 * 60 * 60 * 1000);

    const newToken: EnrollmentToken = {
      id: `tok-${Date.now()}`,
      token: tokenString,
      createdAt: now.toISOString().replace('T', ' ').substring(0, 16),
      expiresAt: expires.toISOString().replace('T', ' ').substring(0, 16),
      status: 'active',
      createdBy: currentUser?.name || 'Administrateur',
    };

    setEnrollmentTokens((prev) => [newToken, ...prev]);
    addToast({
      type: 'success',
      title: 'Jeton d\'enrôlement généré',
      message: `Jeton valide pendant 24 heures: ${tokenString}`,
    });

    return newToken;
  };

  const createUser = (userData: { name: string; email: string; role: Role }) => {
    const newUser: User = {
      id: `usr-${Date.now().toString().substring(8)}`,
      name: userData.name,
      email: userData.email,
      role: userData.role,
      createdAt: new Date().toISOString().substring(0, 10),
      status: 'active',
    };

    setUsers((prev) => [...prev, newUser]);
    addToast({
      type: 'success',
      title: 'Utilisateur créé',
      message: `Le compte pour ${userData.name} (${userData.role}) a été ajouté.`,
    });
  };

  const updateUser = (userId: string, updates: Partial<User>) => {
    setUsers((prev) =>
      prev.map((u) => (u.id === userId ? { ...u, ...updates } : u))
    );
    addToast({
      type: 'success',
      title: 'Utilisateur mis à jour',
      message: 'Les modifications de l\'utilisateur ont été enregistrées.',
    });
  };

  const deleteUser = (userId: string) => {
    setUsers((prev) => prev.filter((u) => u.id !== userId));
    addToast({
      type: 'success',
      title: 'Utilisateur supprimé',
      message: 'Le compte utilisateur a été supprimé.',
    });
  };

  const exportCSV = (type: 'agents' | 'alerts') => {
    let csvContent = '';
    let fileName = '';

    if (type === 'agents') {
      fileName = `cbc_agents_export_${new Date().toISOString().substring(0, 10)}.csv`;
      csvContent = 'ID,Nom,Hostname,OS,VersionOS,VersionAgent,IP,Statut,CPU(%),RAM(%),Disque(%),Uptime,Alertes,Emplacement\n';
      agents.forEach((ag) => {
        csvContent += `"${ag.id}","${ag.name}","${ag.hostname}","${ag.os}","${ag.osVersion}","${ag.agentVersion || 'CBC Agent v1.0'}","${ag.ipAddress}","${ag.status}",${ag.metrics.cpu},${ag.metrics.ram},${ag.metrics.disk},"${ag.metrics.uptime}",${ag.activeAlertsCount},"${ag.location}"\n`;
      });
    } else {
      fileName = `cbc_alertes_export_${new Date().toISOString().substring(0, 10)}.csv`;
      csvContent = 'ID,Agent,Type,Gravite,Statut,Date,Message,AcquittePar,Commentaire\n';
      alerts.forEach((alt) => {
        csvContent += `"${alt.id}","${alt.agentName}","${alt.type}","${alt.severity}","${alt.status}","${alt.timestamp}","${alt.message.replace(/"/g, '""')}","${alt.acknowledgedBy || ''}","${alt.comment || ''}"\n`;
      });
    }

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', fileName);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    addToast({
      type: 'success',
      title: 'Exportation terminée',
      message: `Fichier CSV généré: ${fileName}`,
    });
  };

  const login = async (username: string, password: string) => {
    try {
      const user = await authService.login(username, password);
      setCurrentUser(user);
      setCurrentRoleState(user.role);
      localStorage.setItem(`${STORAGE_KEY_PREFIX}currentUser`, JSON.stringify(user));
      navigate('/dashboard');
      addToast({
        type: 'success',
        title: 'Connexion réussie',
        message: `Bienvenue, ${user.name}. Session active en tant que ${user.role}.`,
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Erreur de connexion',
        message: 'Identifiants invalides ou erreur serveur.',
      });
    }
  };

  const logout = async () => {
    await authService.logout();
    setCurrentUser(null);
    localStorage.removeItem(`${STORAGE_KEY_PREFIX}currentUser`);
    navigate('/login');
    addToast({
      type: 'info',
      title: 'Déconnexion',
      message: 'Vous avez été déconnecté avec succès.',
    });
  };

  return (
    <AppContext.Provider
      value={{
        currentUser,
        currentRole,
        setCurrentRole,
        selectedAgentId,
        setSelectedAgentId,
        agents,
        alerts,
        users,
        globalThresholds,
        messagingConfig,
        servicesMonitoringConfig,
        filesMonitoringConfig,
        availabilityPolicy,
        retentionConfig,
        enrollmentTokens,
        toasts,
        autoRefresh,
        toggleAutoRefresh,
        refreshData,
        acknowledgeAlert,
        acknowledgeAllAlerts,
        revokeAgent,
        deleteAgent,
        updateAgentThresholds,
        resetAgentThresholds,
        updateGlobalThresholds,
        updateMessagingConfig,
        updateServicesMonitoringConfig,
        updateFilesMonitoringConfig,
        updateAvailabilityPolicy,
        updateRetentionConfig,
        generateEnrollmentToken,
        createUser,
        updateUser,
        deleteUser,
        addToast,
        removeToast,
        exportCSV,
        login,
        logout,
        navigateToAgentDetail,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};

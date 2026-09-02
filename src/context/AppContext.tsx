/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
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
  /** Rafraîchissement réel : relit le parc et les alertes depuis le serveur. */
  refreshFleet: () => Promise<void>;
  acknowledgeAlert: (alertId: string, comment?: string, operatorName?: string) => void;
  resolveAlert: (alertId: string, comment?: string, operatorName?: string) => void;
  acknowledgeAllAlerts: (operatorName?: string, comment?: string) => void;
  revokeAgent: (agentId: string) => Promise<void>;
  deleteAgent: (agentId: string) => Promise<void>;
  updateAgentThresholds: (agentId: string, thresholds: CustomThresholds) => void;
  resetAgentThresholds: (agentId: string) => Promise<void>;
  updateGlobalThresholds: (thresholds: GlobalThresholds) => void;
  updateMessagingConfig: (config: MessagingNotificationConfig) => void;
  updateAvailabilityPolicy: (policy: AvailabilityPolicy) => void;
  updateRetentionConfig: (config: DataRetentionConfig) => void;
  generateEnrollmentToken: () => Promise<EnrollmentToken | null>;
  createUser: (userData: { name: string; email: string; role: Role; password: string }) => Promise<void>;
  updateUser: (userId: string, updates: Partial<User>) => Promise<void>;
  deleteUser: (userId: string) => Promise<void>;
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
    const token = localStorage.getItem('access_token');
    const saved = localStorage.getItem(`${STORAGE_KEY_PREFIX}currentUser`);
    if (!token || !saved) return null;
    try {
      return JSON.parse(saved);
    } catch {
      return null;
    }
  });

  // Repli en lecture seule, jamais en administrateur : sans profil en cache,
  // afficher une interface d'administration serait accorder par défaut le
  // droit le plus fort. Le serveur reste l'autorité — ce rôle ne sert qu'à
  // décider ce que l'interface propose.
  const [currentRole, setCurrentRoleState] = useState<Role>(() => {
    return currentUser?.role || 'ReadOnly';
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
    durationSeconds: 300,
    escalateAfterMinutes: 15,
    alertReminderHours: 3,
    heartbeatIntervalSeconds: 30,
    diskMountRules: [],
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
      if (!localStorage.getItem('access_token')) {
        setCurrentUser(null);
        return;
      }

      // Le rôle est relu auprès du serveur à chaque chargement.
      //
      // Il n'était posé qu'à la connexion puis conservé dans le stockage
      // local : un changement de droits — promotion, révocation, réattribution
      // par l'annuaire — restait invisible jusqu'à une déconnexion manuelle.
      // Dans le sens de la révocation, cela laissait une interface
      // d'administration à quelqu'un qui n'y avait plus droit.
      try {
        const fresh = await authService.getCurrentUser();
        if (fresh && fresh.role !== currentUser.role) {
          setCurrentUser(fresh);
          setCurrentRoleState(fresh.role);
          localStorage.setItem(`${STORAGE_KEY_PREFIX}currentUser`, JSON.stringify(fresh));
        }
      } catch {
        // Profil injoignable : on garde le rôle en cache pour cette session,
        // le serveur refusera de toute façon ce qui n'est pas permis.
      }

      setLoading(true);
      try {
        const agentsData = await agentsService.getAgents();
        setAgents(agentsData);
      } catch (error) {
        console.error('Error loading agents:', error);
        addToast({
          type: 'error',
          title: 'Agents introuvables',
          message: "L'API n'a pas renvoyé la liste des agents. Reconnectez-vous.",
        });
      }

      try {
        const alertsData = await alertsService.getAlerts();
        setAlerts(alertsData);
      } catch (error) {
        console.error('Error loading alerts:', error);
      }

      try {
        const usersData = await usersService.getUsers();
        setUsers(usersData);
      } catch (error) {
        console.error('Error loading users:', error);
      }

      try {
        const thresholdsData = await settingsService.getGlobalThresholds();
        setGlobalThresholds(thresholdsData);
      } catch (error) {
        console.error('Error loading thresholds:', error);
      }

      try {
        const retentionData = await settingsService.getRetentionConfig();
        setRetentionConfig(retentionData);
      } catch (error) {
        console.error('Error loading retention:', error);
      }

      try {
        const tokensData = await settingsService.getEnrollmentTokens();
        setEnrollmentTokens(tokensData);
      } catch (error) {
        console.error('Error loading tokens:', error);
      }

      setLoading(false);
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
    localStorage.setItem(`${STORAGE_KEY_PREFIX}messagingConfig`, JSON.stringify(messagingConfig));
  }, [messagingConfig]);

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

  /**
   * Rafraîchissement périodique depuis le serveur.
   *
   * Ce minuteur fabriquait auparavant la télémétrie : toutes les 10 secondes il
   * appliquait `(Math.random() - 0.5) * 6` au CPU et `* 3` à la RAM de chaque
   * agent, réécrivait l'historique des courbes et forçait « Il y a 2s » comme
   * dernier heartbeat. Le tableau de bord montrait donc une activité inventée,
   * y compris pour un parc entièrement à l'arrêt, et un agent réellement en
   * surcharge n'apparaissait jamais. Les données ne sont désormais lues que
   * depuis l'API.
   */
/**
 * Recalcule le nombre d'alertes actives par hôte à partir des alertes
 * réellement chargées.
 *
 * Le mappeur posait `activeAlertsCount: 0` en dur et l'API de liste ne
 * renvoie pas ce décompte : la colonne « Alertes » du parc affichait donc
 * toujours « — » et le filtre « A des alertes » ne retournait jamais rien,
 * alors que les alertes étaient bien là, dans le même état applicatif.
 */
function withAlertCounts(agents: Agent[], alerts: Alert[]): Agent[] {
  const counts = new Map<string, number>();
  for (const alert of alerts) {
    if (alert.status === 'resolved') continue;
    counts.set(alert.agentId, (counts.get(alert.agentId) || 0) + 1);
  }
  return agents.map((agent) =>
    agent.activeAlertsCount === (counts.get(agent.id) || 0)
      ? agent
      : { ...agent, activeAlertsCount: counts.get(agent.id) || 0 },
  );
}

  const refreshFleet = useCallback(async () => {
    try {
      const [freshAgents, freshAlerts] = await Promise.all([
        agentsService.getAgents(),
        alertsService.getAlerts(),
      ]);
      setAgents(withAlertCounts(freshAgents, freshAlerts));
      setAlerts(freshAlerts);
    } catch (error) {
      // Un rafraîchissement manqué ne doit pas interrompre la session ni
      // effacer les données déjà affichées.
      console.error('Error refreshing fleet:', error);
    }
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(refreshFleet, 10000);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshFleet]);

  useEffect(() => {
    if (!currentUser) return;
    const token = localStorage.getItem('access_token');
    if (!token) return;

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/notifications?token=${encodeURIComponent(token)}`);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg?.type !== 'agent.presence' || !msg.agent_id) return;
        const online = Boolean(msg.online);
        let missing = false;
        setAgents((prev) => {
          const idx = prev.findIndex((a) => a.id === msg.agent_id);
          if (idx === -1) {
            missing = true;
            return prev;
          }
          const next = [...prev];
          next[idx] = {
            ...next[idx],
            status: online ? 'online' : 'offline',
            lastHeartbeat: DataMapper.formatLastSeen(
              msg.last_seen_age_seconds ?? (online ? 0 : undefined),
            ),
            lastSeenAgeSeconds: msg.last_seen_age_seconds,
          };
          return next;
        });
        if (missing && online) void refreshFleet();
      } catch {
        /* ignore malformed frames */
      }
    };

    return () => {
      ws.close();
    };
  }, [currentUser, refreshFleet]);

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
    void alertsService.acknowledgeAlert(alertId, comment, operatorName).catch(() => undefined);
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

  const resolveAlert = (alertId: string, comment?: string, operatorName?: string) => {
    const operator = operatorName?.trim() || currentUser?.name || 'Opérateur CBC';
    void alertsService.resolveAlert(alertId, comment, operatorName).catch(() => undefined);
    setAlerts((prev) =>
      prev.map((alt) =>
        alt.id === alertId
          ? {
              ...alt,
              status: 'resolved',
              acknowledgedBy: operator,
              comment: comment?.trim() || alt.comment,
            }
          : alt
      )
    );
    addToast({
      type: 'success',
      title: 'Alerte résolue',
      message: `L'alerte #${alertId} est passée à Résolue.`,
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

  // La révocation doit atteindre le serveur : c'est lui qui refuse ensuite les
  // heartbeats de l'agent. Auparavant seul l'état local changeait, si bien
  // qu'un hôte compromis restait pleinement actif derrière un message de
  // succès, et réapparaissait « en ligne » au rechargement.
  const revokeAgent = async (agentId: string) => {
    if (currentRole !== 'Admin') {
      addToast({
        type: 'error',
        title: 'Permission refusée',
        message: 'Seul un Administrateur peut révoquer un agent.',
      });
      return;
    }

    try {
      await agentsService.revokeAgent(agentId);
      setAgents((prev) =>
        prev.map((ag) => (ag.id === agentId ? { ...ag, status: 'revoked' } : ag))
      );
      addToast({
        type: 'warning',
        title: 'Agent révoqué',
        message: `L'agent #${agentId} a été révoqué. Il recevra un code 401 lors de sa prochaine tentative de connexion.`,
      });
    } catch (error) {
      console.error('Error revoking agent:', error);
      addToast({
        type: 'error',
        title: 'Révocation impossible',
        message: "L'agent n'a pas été révoqué. Il reste actif — réessayez.",
      });
    }
  };

  const deleteAgent = async (agentId: string) => {
    if (currentRole !== 'Admin') {
      addToast({
        type: 'error',
        title: 'Permission refusée',
        message: 'Seul un Administrateur peut supprimer un agent.',
      });
      return;
    }

    try {
      await agentsService.deleteAgent(agentId);
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
    } catch (error) {
      console.error('Error deleting agent:', error);
      addToast({
        type: 'error',
        title: 'Suppression impossible',
        message: "L'agent n'a pas été supprimé.",
      });
    }
  };

  const updateAgentThresholds = async (agentId: string, thresholds: CustomThresholds) => {
    try {
      await agentsService.updateAgentThresholds(agentId, thresholds);
      setAgents((prev) =>
        prev.map((ag) => (ag.id === agentId ? { ...ag, customThresholds: thresholds } : ag))
      );
      addToast({
        type: 'success',
        title: 'Seuils mis à jour',
        message: `Seuils d'alerte personnalisés enregistrés pour l'agent.`,
      });
    } catch (error) {
      console.error('Error saving agent thresholds:', error);
      addToast({
        type: 'error',
        title: 'Échec',
        message: "Impossible d'enregistrer les seuils de l'hôte.",
      });
    }
  };

  const resetAgentThresholds = async (agentId: string) => {
    try {
      // Des seuils nuls signifient « utiliser les seuils globaux » côté serveur.
      await agentsService.updateAgentThresholds(agentId, {
        cpuWarning: null,
        cpuCritical: null,
        ramWarning: null,
        ramCritical: null,
        diskWarning: null,
        diskCritical: null,
      } as unknown as CustomThresholds);
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
    } catch (error) {
      console.error('Error resetting agent thresholds:', error);
      addToast({
        type: 'error',
        title: 'Échec',
        message: "Les seuils de l'hôte n'ont pas été réinitialisés.",
      });
    }
  };

  const updateGlobalThresholds = async (thresholds: GlobalThresholds) => {
    try {
      await settingsService.updateGlobalThresholds(thresholds);
    } catch (error) {
      console.error('Error saving thresholds:', error);
    }
    setGlobalThresholds(thresholds);
    addToast({
      type: 'success',
      title: 'Paramètres enregistrés',
      message: 'Les seuils d\'alerte globaux ont été appliqués.',
    });
  };

  const updateMessagingConfig = async (config: MessagingNotificationConfig) => {
    try {
      await settingsService.updateMessagingConfig(config);
    } catch (error) {
      console.error('Error saving messaging config:', error);
    }
    setMessagingConfig(config);
    addToast({
      type: 'success',
      title: 'Configuration mise à jour',
      message: 'La configuration de messagerie a été mise à jour avec succès.',
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

  /**
   * Le jeton doit être émis par le serveur.
   *
   * Il était auparavant fabriqué ici avec `Math.random()` : l'administrateur
   * recevait une chaîne d'allure crédible qui n'existait dans aucune base, si
   * bien qu'aucun agent ne pouvait s'enrôler avec. Les jetons sont désormais
   * persistés, datés et à usage unique côté serveur.
   */
  const generateEnrollmentToken = async (): Promise<EnrollmentToken | null> => {
    let created: any;
    try {
      created = await settingsService.createEnrollmentToken();
    } catch (error) {
      console.error('Error generating enrollment token:', error);
      addToast({
        type: 'error',
        title: 'Génération impossible',
        message: "Le jeton d'enrôlement n'a pas été créé.",
      });
      return null;
    }

    const tokenString = created.token;
    const newToken: EnrollmentToken = {
      id: created.id,
      token: tokenString,
      createdAt: (created.created_at || '').toString().replace('T', ' ').substring(0, 16),
      expiresAt: (created.expires_at || '').toString().replace('T', ' ').substring(0, 16),
      status: created.status || 'active',
      createdBy: created.created_by || currentUser?.name || 'Administrateur',
    };

    setEnrollmentTokens((prev) => [newToken, ...prev]);
    addToast({
      type: 'success',
      title: 'Jeton d\'enrôlement généré',
      message: `Jeton valide pendant 24 heures: ${tokenString}`,
    });

    return newToken;
  };

  // Le compte doit exister côté serveur, sinon il disparaît au rechargement et
  // la personne ne peut pas se connecter.
  const createUser = async (userData: { name: string; email: string; role: Role; password: string }) => {
    try {
      const created = await usersService.createUser(userData);
      setUsers((prev) => [...prev, created]);
      addToast({
        type: 'success',
        title: 'Utilisateur créé',
        message: `Le compte pour ${userData.name} (${userData.role}) a été ajouté.`,
      });
    } catch (error: any) {
      console.error('Error creating user:', error);
      addToast({
        type: 'error',
        title: 'Création impossible',
        message: error?.response?.data?.detail || "Le compte n'a pas été créé.",
      });
    }
  };

  const updateUser = async (userId: string, updates: Partial<User>) => {
    try {
      const saved = await usersService.updateUser(userId, updates);
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, ...saved } : u)));
      addToast({
        type: 'success',
        title: 'Utilisateur mis à jour',
        message: 'Les modifications de l\'utilisateur ont été enregistrées.',
      });
    } catch (error: any) {
      console.error('Error updating user:', error);
      addToast({
        type: 'error',
        title: 'Mise à jour impossible',
        message: error?.response?.data?.detail || "Les modifications n'ont pas été enregistrées.",
      });
    }
  };

  const deleteUser = async (userId: string) => {
    try {
      await usersService.deleteUser(userId);
      setUsers((prev) => prev.filter((u) => u.id !== userId));
      addToast({
        type: 'success',
        title: 'Utilisateur supprimé',
        message: 'Le compte utilisateur a été supprimé.',
      });
    } catch (error: any) {
      console.error('Error deleting user:', error);
      addToast({
        type: 'error',
        title: 'Suppression impossible',
        message: error?.response?.data?.detail || "Le compte n'a pas été supprimé.",
      });
    }
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
      throw error;
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
        refreshFleet,
        acknowledgeAlert,
        resolveAlert,
        acknowledgeAllAlerts,
        revokeAgent,
        deleteAgent,
        updateAgentThresholds,
        resetAgentThresholds,
        updateGlobalThresholds,
        updateMessagingConfig,
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

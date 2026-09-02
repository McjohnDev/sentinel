/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import axiosInstance from './axios.config';
import { AuthSource, Role, User } from '../../types';

export interface CreateUserRequest {
  username: string;
  email: string;
  password: string;
  role: string;
}

export interface LdapCandidate {
  username: string;
  email?: string | null;
  display_name?: string | null;
  dn: string;
  department?: string | null;
  title?: string | null;
  suggested_role: string;
  already_imported: boolean;
}

export interface UpdateUserRequest {
  username?: string;
  email?: string;
  role?: string;
  is_active?: boolean;
  manager_id?: string | null;
}

/**
 * Correspondance explicite des rôles.
 *
 * Le code dérivait auparavant le rôle par manipulation de chaîne
 * (`charAt(0).toUpperCase() + slice(1)`), ce qui transformait `read_only` en
 * `Read_only` — une valeur absente du type `Role` — et renvoyait `readonly`
 * au serveur, qui attend `read_only`. Toute modification de rôle échouait
 * donc silencieusement.
 */
const BACKEND_TO_ROLE: Record<string, Role> = {
  admin: 'Admin',
  operator: 'Operator',
  read_only: 'ReadOnly',
  security: 'Security',
};

const ROLE_TO_BACKEND: Record<Role, string> = {
  Admin: 'admin',
  Operator: 'operator',
  ReadOnly: 'read_only',
  Security: 'security',
};

export function toBackendRole(role: Role): string {
  return ROLE_TO_BACKEND[role] ?? 'read_only';
}

export function fromBackendRole(role: string): Role {
  return BACKEND_TO_ROLE[(role || '').toLowerCase()] ?? 'ReadOnly';
}

function mapUser(raw: any): User {
  return {
    id: raw.id,
    name: raw.username,
    email: raw.email,
    role: fromBackendRole(raw.role),
    createdAt: raw.created_at || new Date().toISOString().split('T')[0],
    status: raw.is_active ? 'active' : 'inactive',
    authSource: (raw.auth_source || 'local') as AuthSource,
    lastLoginAt: raw.last_login_at ?? null,
    permissions: raw.permissions ?? [],
  };
}

export const usersService = {
  async getUsers(): Promise<User[]> {
    const response = await axiosInstance.get('/auth/users');
    return (response.data as any[]).map(mapUser);
  },

  async createUser(userData: { name: string; email: string; role: Role; password: string }): Promise<User> {
    const response = await axiosInstance.post('/auth/register', {
      username: userData.name,
      email: userData.email,
      password: userData.password,
      role: toBackendRole(userData.role),
    });
    return mapUser(response.data);
  },

  /** Retourne l'utilisateur tel que le serveur l'a enregistré. */
  async updateUser(id: string, updates: Partial<User>): Promise<Partial<User>> {
    const payload: UpdateUserRequest = {};
    if (updates.name) payload.username = updates.name;
    if (updates.email) payload.email = updates.email;
    if (updates.role) payload.role = toBackendRole(updates.role);
    if (updates.status !== undefined) payload.is_active = updates.status === 'active';

    const response = await axiosInstance.put(`/auth/users/${id}`, payload);
    return mapUser(response.data);
  },

  async setPassword(id: string, password: string): Promise<void> {
    await axiosInstance.post(`/auth/users/${id}/password`, { password });
  },

  /**
   * Changement de mot de passe par le titulaire du compte.
   *
   * `setPassword` ci-dessus est la reinitialisation administrateur : elle
   * exige la permission USER_MANAGE et ne verifie pas le secret courant. Un
   * utilisateur ordinaire recevrait un 403.
   */
  async changeOwnPassword(currentPassword: string, newPassword: string): Promise<void> {
    await axiosInstance.post('/auth/me/password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  },

  /**
   * Recherche dans l'annuaire, pour importer un compte existant.
   *
   * Distinct de l'authentification : celle-ci refuse plusieurs résultats,
   * parce qu'un filtre ambigu connecterait un homonyme. Ici l'administrateur
   * cherche une personne et doit justement voir les homonymes pour choisir.
   */
  async searchLdap(term: string): Promise<LdapCandidate[]> {
    const { data } = await axiosInstance.get('/settings/ldap/search', { params: { q: term } });
    return data.data || [];
  },

  /**
   * Crée le compte miroir d'un compte d'annuaire.
   *
   * Aucun mot de passe n'est enregistré : l'authentification reste à
   * l'annuaire, et la révocation y reste immédiate.
   */
  async importFromLdap(username: string, role?: string): Promise<{ username: string; role: string }> {
    const { data } = await axiosInstance.post('/settings/ldap/import', { username, role });
    return data;
  },

  async deleteUser(id: string): Promise<void> {
    await axiosInstance.delete(`/auth/users/${id}`);
  },

  /** Permissions du compte connecté — l'UI n'a pas à réimplémenter la règle. */
  async getMyPermissions(): Promise<{ role: string; permissions: string[] }> {
    const response = await axiosInstance.get('/auth/permissions');
    return response.data;
  },

  /** Matrice complète rôle -> permissions, pour l'écran d'administration. */
  async getRoleMatrix(): Promise<{
    roles: Array<{ value: string; permissions: string[] }>;
    permissions: string[];
  }> {
    const response = await axiosInstance.get('/auth/roles');
    return response.data;
  },
};

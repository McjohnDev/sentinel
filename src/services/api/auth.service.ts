/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import axiosInstance from './axios.config';
import { User, Role } from '../../types';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user_id: string;
  username: string;
  role: string;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface RefreshTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export const authService = {
  async login(username: string, password: string): Promise<User> {
    console.log('Login attempt:', { username, passwordLength: password.length });
    const response = await axiosInstance.post<LoginResponse>('/auth/login', {
      username,
      password,
    });
    console.log('Login response:', response.data);

    const { access_token, refresh_token, user_id, username: returnedUsername, role } = response.data;

    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);

    // Récupérer l'email depuis la base de données ou utiliser une valeur par défaut
    const email = `${returnedUsername}@cbcam.cm`;

    return {
      id: user_id,
      name: returnedUsername,
      email: email,
      role: role.charAt(0).toUpperCase() + role.slice(1) as Role,
      createdAt: new Date().toISOString().split('T')[0],
      status: 'active',
    };
  },

  async logout(): Promise<void> {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('currentUser');
  },

  async refreshToken(refreshToken: string): Promise<RefreshTokenResponse> {
    const response = await axiosInstance.post<RefreshTokenResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    });

    const { access_token, refresh_token: newRefreshToken } = response.data;

    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', newRefreshToken);

    return response.data;
  },

  async getCurrentUser(): Promise<User | null> {
    try {
      const response = await axiosInstance.get('/auth/me');
      const user = response.data;

      return {
        id: user.id,
        name: user.username,
        email: user.email,
        role: user.role.charAt(0).toUpperCase() + user.role.slice(1) as Role,
        createdAt: user.created_at || new Date().toISOString().split('T')[0],
        status: user.is_active ? 'active' : 'inactive',
      };
    } catch (error) {
      return null;
    }
  },
};

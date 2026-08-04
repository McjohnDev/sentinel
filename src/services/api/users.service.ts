/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import axiosInstance from './axios.config';
import { User, Role } from '../../types';

export interface CreateUserRequest {
  username: string;
  email: string;
  password: string;
  role: string;
}

export interface UpdateUserRequest {
  username?: string;
  email?: string;
  role?: string;
  is_active?: boolean;
}

export const usersService = {
  async getUsers(): Promise<User[]> {
    const response = await axiosInstance.get('/auth/users');
    return response.data.map((user: any) => ({
      id: user.id,
      name: user.username,
      email: user.email,
      role: user.role.charAt(0).toUpperCase() + user.role.slice(1) as Role,
      createdAt: user.created_at || new Date().toISOString().split('T')[0],
      status: user.is_active ? 'active' : 'inactive',
    }));
  },

  async createUser(userData: { name: string; email: string; role: Role; password: string }): Promise<User> {
    const response = await axiosInstance.post('/auth/register', {
      username: userData.name,
      email: userData.email,
      password: userData.password,
      role: userData.role.toLowerCase(),
    });

    const user = response.data;
    return {
      id: user.id,
      name: user.username,
      email: user.email,
      role: user.role.charAt(0).toUpperCase() + user.role.slice(1) as Role,
      createdAt: user.created_at || new Date().toISOString().split('T')[0],
      status: user.is_active ? 'active' : 'inactive',
    };
  },

  async updateUser(id: string, updates: Partial<User>): Promise<void> {
    const updateData: UpdateUserRequest = {};
    if (updates.name) updateData.username = updates.name;
    if (updates.email) updateData.email = updates.email;
    if (updates.role) updateData.role = updates.role.toLowerCase();
    if (updates.status !== undefined) updateData.is_active = updates.status === 'active';

    await axiosInstance.put(`/auth/users/${id}`, updateData);
  },

  async deleteUser(id: string): Promise<void> {
    await axiosInstance.delete(`/auth/users/${id}`);
  },
};

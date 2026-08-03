import axios from 'axios';

const API_BASE_URL = 'https://localhost:8443/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const authAPI = {
  login: (username, password) => api.post('/auth/login', { username, password }),
  register: (username, email, password, role) => 
    api.post('/auth/register', { username, email, password, role }),
  getMe: (token) => api.get('/auth/me', {
    headers: { Authorization: `Bearer ${token}` }
  }),
};

export const agentsAPI = {
  list: (token, skip = 0, limit = 100) => 
    axios.get(`${API_BASE_URL}/agents?skip=${skip}&limit=${limit}`, {
      headers: { Authorization: `Bearer ${token}` }
    }),
  get: (id, token) => 
    axios.get(`${API_BASE_URL}/agents/${id}`, {
      headers: { Authorization: `Bearer ${token}` }
    }),
  getHeartbeats: (id, token, limit = 100, offset = 0) =>
    axios.get(`${API_BASE_URL}/agents/${id}/heartbeats?limit=${limit}&offset=${offset}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
};

export const alertsAPI = {
  list: (token, skip = 0, limit = 100) => 
    api.get(`/alerts?skip=${skip}&limit=${limit}`, {
      headers: { Authorization: `Bearer ${token}` }
    }),
  get: (id, token) => api.get(`/alerts/${id}`, {
    headers: { Authorization: `Bearer ${token}` }
  }),
};

export default api;

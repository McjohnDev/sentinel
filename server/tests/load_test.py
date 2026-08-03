from locust import HttpUser, task, between
import json
import uuid


class CBCSupervisionUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Login on start to get auth token"""
        response = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
            verify=False
        )
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = None
            self.headers = {}
    
    @task(3)
    def list_agents(self):
        """List agents - high frequency operation"""
        if self.token:
            self.client.get(
                "/api/agents",
                headers=self.headers,
                verify=False
            )
    
    @task(3)
    def list_alerts(self):
        """List alerts - high frequency operation"""
        if self.token:
            self.client.get(
                "/api/alerts",
                headers=self.headers,
                verify=False
            )
    
    @task(2)
    def get_health(self):
        """Health check - medium frequency"""
        self.client.get("/health", verify=False)
    
    @task(1)
    def get_metrics(self):
        """Get Prometheus metrics - low frequency"""
        self.client.get("/metrics", verify=False)
    
    @task(1)
    def list_agents_paginated(self):
        """List agents with pagination - low frequency"""
        if self.token:
            self.client.get(
                "/api/agents?skip=0&limit=10",
                headers=self.headers,
                verify=False
            )
    
    @task(1)
    def list_alerts_paginated(self):
        """List alerts with pagination - low frequency"""
        if self.token:
            self.client.get(
                "/api/alerts?skip=0&limit=10",
                headers=self.headers,
                verify=False
            )


class AdminUser(HttpUser):
    """Admin user with more write operations"""
    wait_time = between(2, 5)
    
    def on_start(self):
        """Login as admin"""
        response = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
            verify=False
        )
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = None
            self.headers = {}
    
    @task(2)
    def list_agents(self):
        """List agents"""
        if self.token:
            self.client.get(
                "/api/agents",
                headers=self.headers,
                verify=False
            )
    
    @task(2)
    def list_alerts(self):
        """List alerts"""
        if self.token:
            self.client.get(
                "/api/alerts",
                headers=self.headers,
                verify=False
            )
    
    @task(1)
    def get_health(self):
        """Health check"""
        self.client.get("/health", verify=False)

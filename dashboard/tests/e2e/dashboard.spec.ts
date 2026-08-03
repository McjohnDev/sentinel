import { test, expect } from '@playwright/test';

test.describe('CBC Supervision Dashboard E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the dashboard
    await page.goto('http://localhost:5173');
  });

  test('should display login page', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('CBC Supervision Platform');
    await expect(page.locator('input[type="text"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });

  test('should login with valid credentials', async ({ page }) => {
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button[type="submit"]');
    
    // Wait for navigation to dashboard
    await page.waitForURL('**/dashboard');
    
    // Verify we're on the dashboard
    await expect(page.locator('h1')).toContainText('CBC Supervision Platform');
    await expect(page.locator('text=Connecté en tant que: admin')).toBeVisible();
  });

  test('should show error with invalid credentials', async ({ page }) => {
    await page.fill('input[type="text"]', 'invalid');
    await page.fill('input[type="password"]', 'invalid');
    await page.click('button[type="submit"]');
    
    // Should show error message
    await expect(page.locator('text=Erreur')).toBeVisible();
  });

  test('should display agents list after login', async ({ page }) => {
    // Login first
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard');
    
    // Check for agents section
    await expect(page.locator('text=Agents')).toBeVisible();
  });

  test('should display alerts list after login', async ({ page }) => {
    // Login first
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard');
    
    // Check for alerts section
    await expect(page.locator('text=Alertes')).toBeVisible();
  });

  test('should toggle dark mode', async ({ page }) => {
    // Login first
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard');
    
    // Find and click theme toggle button
    const themeButton = page.locator('button:has-text("🌙")');
    await expect(themeButton).toBeVisible();
    await themeButton.click();
    
    // Verify theme changed
    await expect(page.locator('button:has-text("☀️")')).toBeVisible();
  });

  test('should logout', async ({ page }) => {
    // Login first
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard');
    
    // Click logout button
    await page.click('button:has-text("Déconnexion")');
    
    // Should be back to login page
    await expect(page.locator('input[type="text"]')).toBeVisible();
  });
});

import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  // Collect console errors
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    }
  });

  try {
    // Navigate to the deployed page
    await page.goto('https://suinucjnbac8.space.minimaxi.com', { timeout: 30000 });
    
    // Wait for the app to load
    await page.waitForSelector('.app-container', { timeout: 10000 });
    
    // Check for header elements
    const header = await page.$('.app-header');
    const title = await page.$('.header-title h1');
    
    if (!header || !title) {
      console.error('ERROR: Header or title not found');
      process.exit(1);
    }
    
    // Check for welcome screen
    const welcomeScreen = await page.$('.welcome-screen');
    if (!welcomeScreen) {
      console.error('ERROR: Welcome screen not found');
      process.exit(1);
    }
    
    // Check for input area
    const inputArea = await page.$('.input-area');
    if (!inputArea) {
      console.error('ERROR: Input area not found');
      process.exit(1);
    }
    
    // Test typing in the input fields
    await page.fill('textarea[placeholder="Enter your question..."]', 'What is AI?');
    await page.fill('textarea[placeholder="Enter context text for the model to analyze..."]', 'AI stands for Artificial Intelligence.');
    
    // Check if inputs are filled
    const questionValue = await page.$eval('textarea[placeholder="Enter your question..."]', el => el.value);
    const contextValue = await page.$eval('textarea[placeholder="Enter context text for the model to analyze..."]', el => el.value);
    
    if (questionValue !== 'What is AI?' || contextValue !== 'AI stands for Artificial Intelligence.') {
      console.error('ERROR: Input fields not working correctly');
      process.exit(1);
    }
    
    console.log('SUCCESS: All basic tests passed!');
    
    // Log any console errors (but don't fail if only warnings)
    if (errors.length > 0) {
      console.log('Console errors found:', errors);
    }
    
  } catch (error) {
    console.error('ERROR:', error.message);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();

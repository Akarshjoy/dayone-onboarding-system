const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let admin = true;
  const employee = { employee_id:'00000000-0000-4000-8000-000000000001',name:'Alex Morgan',email:'alex@example.com',department:'Engineering',role:'Product engineer',manager:'Sam Taylor',joining_date:'2026-10-01',employment_type:'full_time',status:'onboarding',accepted_at:'2026-09-16',progress:25,stages:{documents:{status:'complete'},it:{status:'in-progress'},policy:{status:'pending'},manager:{status:'pending'}},documents:{id_proof:{status:'verified'},degree_certificate:{status:'verified'},signed_offer:{status:'verified'}} };
  await page.route('**/config.js', route => route.fulfill({contentType:'application/javascript',body:"window.CONFIG={apiUrl:'https://fixture.invalid',region:'us-east-1',clientId:'fixture'}"}));
  await page.route('https://cognito-idp.us-east-1.amazonaws.com/**', route => {
    const token = ['e30',Buffer.from(JSON.stringify({'cognito:groups':admin?['HRAdmin']:[]})).toString('base64url'),'fixture'].join('.');
    return route.fulfill({json:{AuthenticationResult:{IdToken:token}}});
  });
  await page.route('https://fixture.invalid/**', route => route.fulfill({json:route.request().url().endsWith('/employees')?{items:[employee],cursor:null}:employee}));
  await page.goto('http://127.0.0.1:8080');
  async function signIn() {await page.locator('#email').fill('test@example.com');await page.locator('#password').fill('ExamplePassword!23');await page.getByRole('button',{name:'Sign in to your workspace'}).click();}
  await signIn();
  await page.getByRole('heading',{name:'Every beginning, in view.'}).waitFor();
  assert.equal(await page.locator('tbody tr').count(),1);
  await page.getByRole('button',{name:'Review →'}).click();
  await page.locator('#asset-form').waitFor();
  await page.screenshot({path:path.join(__dirname,'../docs/hr-preview.png'),fullPage:true});
  await page.getByRole('button',{name:'Sign out'}).click(); admin=false; await signIn();
  await page.getByRole('heading',{name:'Welcome, Alex.'}).waitFor();
  assert.equal(await page.getByRole('progressbar').getAttribute('aria-valuenow'),'25');
  await page.screenshot({path:path.join(__dirname,'../docs/hire-preview.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth),true,'Mobile should not overflow');
  assert.deepEqual(errors,[]);
  await browser.close();
  console.log('PASS: HR view, employee view, logout/login, progress, mobile overflow, no JS errors. Synthetic data only.');
})().catch(error=>{console.error(error);process.exit(1)});

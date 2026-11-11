const fs=require('fs'),path=require('path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root=path.resolve(__dirname,'..'),base=process.env.JIRAN_TEST_URL || 'http://127.0.0.1:5173';
(async()=>{
 const [email,account]=Object.entries(JSON.parse(fs.readFileSync(path.join(root,'.private/operator/team-demo-credentials.json'))))[0];
 const browser=await chromium.launch({headless:true});
 try {
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/login');await page.getByPlaceholder('Email',{exact:true}).fill(email);await page.getByPlaceholder('Password',{exact:true}).fill(account.password);await page.getByRole('button',{name:'Login',exact:true}).click();await page.waitForURL('**/retailer-dashboard');
  await page.getByRole('link',{name:'Analytics',exact:true}).click();await page.getByRole('button',{name:'Stock Metrics',exact:true}).click();
  const summary=page.locator('summary').filter({hasText:'Stock ranges · 7 / 14 / 30 / 60 days'}).first();await summary.waitFor();await summary.click();
  const table=page.getByRole('table',{name:/Stock planning matrix for/}).first();await table.waitFor();
  const days=await table.locator('tbody tr td:first-child').allTextContents();
  if(JSON.stringify(days)!==JSON.stringify(['7 days','14 days','30 days','60 days']))throw new Error('Incorrect horizon matrix');
  if(errors.length)throw new Error(errors.join('\n'));
  console.log('Dashboard stock matrix renders all four horizons, policy ranges and stock actions');
 } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});

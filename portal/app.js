'use strict';
const $ = id => document.getElementById(id);
let session = '', currentPair = '', timer = null, site = null, discoveredUrl = '';
const statusNames = {pending:'منتظر تأیید شما', approved:'در حال نصب و آزمون', ready:'آماده', failed:'ناموفق'};
const phaseNames = {waiting_for_browser_approval:'کمک‌نصاب منتظر تأیید شماست.', waiting_for_helper:'منتظر کمک‌نصاب روی لپ‌تاپ…', downloading:'بررسی یا دانلود نسخهٔ تأییدشده…', verifying:'بررسی کلید و فایل برنامه…', testing:'آزمون واقعی خواندن فایل؛ حداکثر ۱۵۰ ثانیه برای هر برنامه.', saving:'ذخیرهٔ امن پروفایل روی لپ‌تاپ…', ready:'اتصال آماده است. میان‌بر برنامه روی لپ‌تاپ را باز کن.'};
function notice(text, error=false) { $('message').hidden=false; $('message').textContent=text; $('message').classList.toggle('error',error); }
async function api(path, body) {
  const headers = {'Content-Type':'application/json'};
  if(session) headers.Authorization='Bearer '+session;
  const response=await fetch('api'+path,{method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:JSON.stringify(body),credentials:'omit',cache:'no-store',redirect:'error',signal:AbortSignal.timeout(60000)});
  const data=await response.json();
  if(!response.ok) throw new Error(data.error || 'درخواست انجام نشد. دوباره بررسی کن.');
  return data;
}
function action(element, fn) {
  element.addEventListener(element.tagName==='FORM'?'submit':'click',async event=>{
    event.preventDefault(); const button=element.tagName==='FORM'?element.querySelector('button'):element;
    button.disabled=true;
    try { await fn(); } catch(error) { notice(error.message,true); } finally { button.disabled=false; }
  });
}
function schedule() { clearTimeout(timer); if(session && currentPair) timer=setTimeout(()=>refreshPair().catch(error=>notice(error.message,true)),2500); }
async function refreshPair() {
  const pair=await api('/pair/'+currentPair);
  $('pair-panel').hidden=false; $('pair-title').textContent=pair.label;
  $('pair-state').textContent=statusNames[pair.status]||pair.status;
  $('pair-detail').textContent=pair.renewal?'این دستگاه اتصال قبلی دارد. تأیید شما، تمدید امن کلیدهای برنامه‌های انتخابی است.':'نام دستگاه را با لپ‌تاپی که کمک‌نصاب را روی آن اجرا کردی مقایسه کن.';
  $('approve-form').hidden=pair.status!=='pending';
  const phase=pair.phase.split(':');
  $('pair-progress').textContent=(phaseNames[phase[0]]||phase[0])+(phase[1]?' — '+phase[1]:'')+(pair.warning?' — پاک‌سازی کلید قبلی کامل نشده؛ مدیر بررسی کند.':'');
  if(pair.status==='ready') {clearTimeout(timer); await refreshDevices();}
  else if(pair.status==='pending'||pair.status==='approved') schedule();
}
async function refreshDevices() {
  const result=await api('/devices'); const box=$('devices'); box.replaceChildren();
  if(!result.devices.length) box.textContent='هنوز دستگاهی از این پرتال ثبت نشده است. اتصال‌های قدیمی خودکار منتقل نمی‌شوند.';
  for(const device of result.devices) {
    const row=document.createElement('article'); row.className='device';
    const name=document.createElement('strong'); name.textContent=device.label;
    const detail=document.createElement('p');
    detail.textContent=(device.status==='ready'?'آماده':'لغوشده')+' · '+(device.harnesses||[]).map(item=>typeof item==='string'?item:item.name).join(' / ');
    const revoke=document.createElement('button'); revoke.type='button'; revoke.className='secondary danger'; revoke.textContent='لغو دسترسی'; revoke.disabled=device.status==='revoked';
    action(revoke,async()=>{ if(confirm('دسترسی '+device.label+' به مدل لغو شود؟ فایل‌ها حذف نمی‌شوند.')) {await api('/device/revoke',{device_id:device.device_id});await refreshDevices();} });
    row.append(name,detail,revoke); box.append(row);
  }
}
action($('login-form'),async()=>{
  const password=$('password').value; $('password').value='';
  const result=await api('/login',{email:$('email').value.trim(),password}); session=result.session;
  $('login-form').hidden=true; $('signed-in').hidden=false; $('identity').textContent=result.user.user_email;
  $('devices-panel').hidden=false; $('admin-panel').hidden=result.user.user_role!=='proxy_admin';
  notice('وارد شدی. کمک‌نصاب را اجرا کن و درخواست همان دستگاه را تأیید کن.');
  await refreshDevices(); if(currentPair) await refreshPair();
});
action($('logout'),async()=>{
  if(currentPair && !confirm('خروج، اتصال تأییدشده اما ناتمام این نشست را لغو می‌کند. ادامه می‌دهی؟')) return;
  await api('/logout',{}); session=''; clearTimeout(timer);
  $('login-form').hidden=false; $('signed-in').hidden=true;
  for(const id of ['devices-panel','pair-panel','admin-panel']) $(id).hidden=true;
  notice('از حساب خارج شدی.');
});
action($('code-form'),async()=>{if(!session) throw new Error('اول وارد حساب خودت شو.'); currentPair=$('pair-code').value.trim().toUpperCase();await refreshPair();});
action($('approve-form'),async()=>{
  const harnesses=[...document.querySelectorAll('input[name=harness]:checked')].map(input=>input.value);
  if(!harnesses.length) throw new Error('حداقل یک برنامه را انتخاب کن.');
  await api('/pair/approve',{code:currentPair,harnesses}); await refreshPair();
});
action($('refresh-devices'),refreshDevices);
action($('model-form'),async()=>{
  $('model-selection').hidden=true;
  const result=await api('/admin/discover',{base_url:$('model-url').value.trim(),api_key:$('upstream-key').value});
  discoveredUrl=$('model-url').value.trim(); const select=$('model-id'); select.replaceChildren();
  for(const id of result.models) {const option=document.createElement('option');option.value=id;option.textContent=id;select.append(option);}
  $('model-selection').hidden=false; $('select-model').disabled=!site.ManagedModels;
  $('model-status').textContent=site.ManagedModels?'مدل‌ها پیدا شدند. ثبت مدل روی همهٔ کاربران سایت اثر دارد.':'مدل‌ها پیدا شدند؛ مدل پایلوت فعلی ثابت است و از این صفحه تغییر نمی‌کند.';
});
action($('select-model'),async()=>{
  if(discoveredUrl!==$('model-url').value.trim()) throw new Error('نشانی عوض شده؛ دوباره مدل‌ها را پیدا کن.');
  if(!confirm('مدل تمام اتصال‌های این سایت تغییر کند؟')) return;
  await api('/admin/select',{base_url:discoveredUrl,api_key:$('upstream-key').value,model_id:$('model-id').value});
  $('upstream-key').value=''; $('model-status').textContent='مدل ثبت شد. برای تأیید ابزارخوانی، کمک‌نصاب را اجرا و اتصال را آزمون کن.';
});
const code=new URLSearchParams(location.hash.slice(1)).get('pair');
if(code && /^[A-Z2-9]{10}$/.test(code)) {currentPair=code;$('pair-code').value=code;}
api('/info').then(value=>{site=value;$('site-name').textContent=value.SiteName;$('site-url').textContent=new URL(value.BaseUrl).host;}).catch(error=>notice('پرتال در دسترس نیست: '+error.message,true));

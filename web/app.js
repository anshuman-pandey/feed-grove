import {keys,locales} from './locales.js';
const $=id=>document.getElementById(id);
let language='en',state={feeds:[],entries:[]},preview=null,xml='',busy=false,statusKey='ready';
function negotiate(code){if(locales[code])return code;if(/^zh-(TW|HK|Hant)/i.test(code))return 'zh-TW';if(/^zh/i.test(code))return 'zh-CN';return locales[code?.split('-')[0]]?code.split('-')[0]:null;}
try{language=negotiate(localStorage.getItem('feed-grove-language'))||navigator.languages.map(negotiate).find(Boolean)||'en';}catch{}
const t=key=>locales[language][keys.indexOf(key)]||key;
function status(key){statusKey=key;$('status').textContent=t(key);}
function translate(){document.documentElement.lang=language;$('locale').value=language;document.querySelectorAll('[data-t]').forEach(e=>e.textContent=t(e.dataset.t));status(statusKey);render();renderPreview();}
$('locale').onchange=()=>{language=$('locale').value;try{localStorage.setItem('feed-grove-language',language);}catch{}translate();};
async function api(path,data){const response=await fetch('/api/'+path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Feed-Grove':state.token},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(result.error||'Request failed.');return result;}
async function load(){state=await api('library');render();}
async function action(fn){if(busy)return;busy=true;document.querySelectorAll('button,input[type=file]').forEach(e=>e.disabled=true);status('working');try{await fn();await load();status('done');}catch(e){status(e.message);}finally{busy=false;document.querySelectorAll('button,input[type=file]').forEach(e=>e.disabled=false);}}
function node(tag,text,className){const e=document.createElement(tag);e.textContent=text;if(className)e.className=className;return e;}
function render(){const source=$('source').value;$('source').replaceChildren(new Option(t('all'),''),...state.feeds.map(f=>new Option((f.folder.length?f.folder.join(' / ')+' · ':'')+f.title,f.url)));$('source').value=state.feeds.some(f=>f.url===source)?source:'';const query=$('search').value.toLocaleLowerCase();const entries=state.entries.filter(e=>(!$('source').value||e.feed_url===$('source').value)&&(!$('unread').checked||!e.is_read)&&(!$('starred').checked||e.starred)&&(e.title+'\n'+e.summary).toLocaleLowerCase().includes(query));$('count').textContent=new Intl.NumberFormat(language).format(entries.length);$('empty').hidden=entries.length>0;
$('articles').replaceChildren(...entries.map(e=>{const a=document.createElement('article');a.append(node('div',state.feeds.find(f=>f.url===e.feed_url)?.title||e.feed_url,'meta'),node('h3',e.title),node('p',e.summary,'summary'));if(e.url){const link=node('a',t('open'));link.href=e.url;link.target='_blank';link.rel='noopener noreferrer';a.append(link);}for(const [key,patch] of [[e.is_read?'unreadAction':'read',{read:!e.is_read}],[e.starred?'unsave':'save',{starred:!e.starred}]]){const b=node('button',t(key),'quiet');b.disabled=busy;b.onclick=()=>action(()=>api('mark',{url:e.feed_url,key:e.key,...patch}));a.append(b);}const refresh=node('button',t('refresh'),'quiet');refresh.disabled=busy;refresh.onclick=()=>action(()=>api('refresh',{url:e.feed_url}));a.append(refresh);return a;}));}
for(const id of ['search','source','unread','starred'])$(id).addEventListener(id==='search'?'input':'change',render);
$('refresh-source').onclick=()=>action(()=>{if(!$('source').value)throw Error('Select a source first.');return api('refresh',{url:$('source').value});});
$('reload').onclick=()=>action(async()=>{});
$('add').onsubmit=e=>{e.preventDefault();action(()=>api('refresh',{url:$('url').value}));};
async function readFile(input){const file=input.files[0];if(!file)throw Error('Select an XML file first.');if(file.size>2097152)throw Error('XML exceeds 2 MiB.');return new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer());}
$('ingest').onclick=()=>action(async()=>api('ingest',{url:$('url').value,xml:await readFile($('feed-file'))}));
function renderPreview(){$('preview').replaceChildren();$('import').hidden=!preview;$('cancel').hidden=!preview;if(preview){const list=document.createElement('ul');for(const f of preview)list.append(node('li',`${f.title} · ${f.folder.join(' / ')} · ${t(f.exists?'existing':'new')}`));$('preview').append(list);}}
$('opml').onchange=()=>action(async()=>{preview=null;xml='';renderPreview();const candidate=await readFile($('opml'));const result=await api('preview',{xml:candidate});xml=candidate;preview=result.feeds;renderPreview();});
$('cancel').onclick=()=>{preview=null;xml='';$('opml').value='';renderPreview();};
$('import').onclick=()=>action(async()=>{await api('import',{xml});preview=null;xml='';$('opml').value='';renderPreview();});
$('export').onclick=()=>action(async()=>{const response=await fetch('/api/opml');if(!response.ok)throw Error('Export failed.');const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=url;a.download='feed-grove.opml';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
translate();load().catch(e=>status(e.message));

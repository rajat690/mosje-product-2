/* ===== MoSJE Scholarship companion (Update 3) – mobile-first, WhatsApp-native web app =====
   Wired to the Product 2 API: /v1/chat/sessions (questions, channel-agnostic engine) and /v1/companion/*
   (results, details, Save on WhatsApp, My schemes, feedback, refer a friend) and /v1/speech/* (TTS/STT, optional). */
(function(){
'use strict';
var API='', LS_ST='p2_student_token', SS_SESS='p2_session';
var S={lang:'en',cfg:null,sid:null,tok:null,stTok:null,linked:null,scr:'chat',hist:[],msgs:[],reply:null,pending:null,
 stateQ:'',showAllStates:false,res:null,filter:'all',det:null,detId:null,docsHave:{},docOpen:{},checks:{},me:null,
 sheet:null,sd:{},dialog:null,refer:null,busy:false,woke:false,poll:null,rec:null,toBottom:false,scrollTo:null};
var POS={};
function $(s,r){return (r||document).querySelector(s);}
function $$(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s));}
/* ---------- UI languages (2 Oct): English + Hindi are inline (strings.js); other languages load a small pack
   /companion/lang/<code>.json on demand (strings, document help, month names, State names). Bhojpuri and Maithili
   use the Hindi app chrome; a language without a pack falls back to English. Chat questions always come translated
   from the server. */
var PACK={},PACK_WAIT={},HI_LIKE={hi:1,bho:1,mai:1},PACK_OF={bho:'hi',mai:'hi'};
function ui(){return HI_LIKE[S.lang]?'hi':'en';}
function pk(){return PACK[PACK_OF[S.lang]||S.lang]||null;}
function loadPack(code,cb){code=PACK_OF[code]||code;if(!code||code==='en'||PACK[code]){if(cb)cb();return;}
 if(PACK_WAIT[code]){if(cb)PACK_WAIT[code].push(cb);return;}PACK_WAIT[code]=cb?[cb]:[];
 var done=function(d){PACK[code]=d||{};var w=PACK_WAIT[code]||[];delete PACK_WAIT[code];w.forEach(function(f){f();});};
 fetch(API+'/companion/lang/'+code+'.json').then(function(r){return r.ok?r.json():{};}).then(done,function(){done({});});}
function t(k,p){var e=T[k],q=pk(),s=q&&q.strings&&q.strings[k];if(!s){if(!e)return k;s=(ui()==='hi'&&e[1])?e[1]:e[0];}
 if(p)for(var x in p)s=s.split('{'+x+'}').join(p[x]);return s;}
/* State names in the student's language (display only - the data and the API keep the English name) */
function stl(x){var q=pk(),m=q&&q.states;return (m&&x&&m[x])||x;}
function stMatch(o,q){return o.label.toLowerCase().indexOf(q)>=0||stl(o.label).toLowerCase().indexOf(q)>=0;}
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function linkify(h){return h.replace(/(https?:\/\/[^\s<]+[^\s<.,;:!?)\]'"])/g,function(u){return '<a href="'+u+'" target="_blank" rel="noopener noreferrer">'+u+'</a>';});}
function waFmt(s){return linkify(esc(s).replace(/\*([^*\n]+)\*/g,'<b>$1</b>')).replace(/\n/g,'<br>');}
function money(n){return '₹'+Number(n).toLocaleString('en-IN');}
var MON={en:['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],hi:['जनवरी','फ़रवरी','मार्च','अप्रैल','मई','जून','जुलाई','अगस्त','सितंबर','अक्टूबर','नवंबर','दिसंबर']};
function pd(iso){if(!iso)return null;var p=String(iso).slice(0,10).split('-');return new Date(+p[0],+p[1]-1,+p[2],12);}
function fmtD(iso){var d=pd(iso);if(!d)return '';var q=pk(),m=(q&&q.months&&q.months.length===12)?q.months:MON[ui()];return d.getDate()+' '+m[d.getMonth()]+' '+d.getFullYear();}
function daysTxt(n){return n===1?t('dayLeft1'):t('daysLeft',{n:n});}
function nowStr(){var d=new Date(),h=d.getHours(),m=d.getMinutes();return (h%12||12)+':'+(m<10?'0':'')+m+' '+(h>=12?'pm':'am');}
var BCP={en:'en-IN',hi:'hi-IN',bn:'bn-IN',as:'as-IN',kn:'kn-IN',ta:'ta-IN',te:'te-IN',ml:'ml-IN',or:'or-IN',bho:'hi-IN',mai:'hi-IN',gu:'gu-IN',mr:'mr-IN',pa:'pa-IN'};
/* ---------- API ---------- */
function api(method,path,body,opt){opt=opt||{};var h={'Accept':'application/json'};
 if(body!==undefined&&!(body instanceof FormData))h['Content-Type']='application/json';
 if(S.tok)h['X-Session-Token']=S.tok; if(S.stTok)h['X-Student-Token']=S.stTok;
 var slow=null;if(!S.woke&&!opt.quiet){slow=setTimeout(function(){if(!S.woke){sys(t('waking'));}},2500);}
 return fetch(API+path,{method:method,headers:h,body:body===undefined?undefined:(body instanceof FormData?body:JSON.stringify(body))})
  .then(function(r){S.woke=true;if(slow)clearTimeout(slow);return r.json().catch(function(){return {};}).then(function(d){return {ok:r.ok,status:r.status,data:d};});})
  .catch(function(){if(slow)clearTimeout(slow);return {ok:false,status:0,data:{}};});}
function ev(name,scheme,data){if(!S.sid)return;api('POST','/v1/companion/sessions/'+S.sid+'/events',{name:name,scheme_id:scheme||null,data:data||{}},{quiet:1});}
/* ---------- chat model ---------- */
function push(m){m.time=m.time||nowStr();S.msgs.push(m);return m;}
function sys(text){if(S.scr!=='chat'){toast(text);return;}push({who:'sys',raw:text});refresh(true);}
function dropTyping(){S.msgs=S.msgs.filter(function(m){return m.who!=='typing';});}
function isTyping(){return S.msgs.some(function(m){return m.who==='typing';});}
function staleReviews(){S.msgs.forEach(function(m){if(m.kind==='review')m.stale=true;});}
function curView(){return (S.reply&&S.reply.view)||'';}
function askKey(){var v=curView();return v.indexOf('ASK_')===0?v.slice(4):null;}
var QKEYS=['state','class_passed','gender','annual_family_income','category'];
function progress(){var r=S.reply;if(!r)return null;var v=r.view||'';if(v.indexOf('ASK_')===0){var i=QKEYS.indexOf(v.slice(4));return i<0?null:i;}if(v==='SUMMARY')return 5;return null;}
/* ---------- render engine ---------- */
var SCR={},SHEETS={},ACT={};
function render(anim){var vp=$('#vp');if(!vp)return;var r=SCR[S.scr]();var cur=vp.querySelector('.scr:not(.leaving)');
 if(!anim&&cur&&cur.dataset.id===S.scr){var sc=cur.querySelector('.scroll'),top=sc?sc.scrollTop:0,ae=document.activeElement,fci=ae&&ae.id==='ci',val=fci?ae.value:'';
  cur.innerHTML=r;var sc2=cur.querySelector('.scroll');if(sc2)sc2.scrollTop=S.toBottom?sc2.scrollHeight:top;if(fci){var ci=$('#ci');if(ci){ci.value=val;ci.focus();}}}
 else{if(cur){var cs=cur.querySelector('.scroll');if(cs)POS[cur.dataset.id]=cs.scrollTop;}
  var el=document.createElement('div');el.className='scr'+(anim?' in-'+anim:'');el.dataset.id=S.scr;el.innerHTML=r;vp.appendChild(el);
  if(anim)el.addEventListener('animationend',function h(e){if(e.target===el){el.classList.remove('in-'+anim);el.removeEventListener('animationend',h);}});
  $$('.scr',vp).forEach(function(o){if(o!==el){o.classList.add('leaving');if(anim){o.classList.add('out-'+anim);setTimeout(function(){o.remove();},480);}else o.remove();}});
  var s=el.querySelector('.scroll');if(s){if(S.scr==='chat')s.scrollTop=s.scrollHeight;else if(S.scrollTo){var tg=el.querySelector('#'+S.scrollTo);if(tg)s.scrollTop=tg.getBoundingClientRect().top-s.getBoundingClientRect().top-10;}else if(anim==='pop'&&POS[S.scr]!=null)s.scrollTop=POS[S.scr];}
  S.scrollTo=null;}
 S.toBottom=false;S.msgs.forEach(function(m){if(m.who!=='typing')m.shown=true;});}
function refresh(bottom){S.toBottom=!!bottom&&S.scr==='chat';render(false);}
function go(id,anim){if(S.scr!==id)S.hist.push(S.scr);S.scr=id;closeSheetNow();render(anim||'push');}
function back(){if(S.dialog){S.dialog=null;renderOverlay(true);return;}if(S.sheet){closeSheet();return;}
 if(!S.hist.length)return;S.scr=S.hist.pop();render('pop');}
function popTo(id){var i=S.hist.lastIndexOf(id);if(i<0){go(id,'pop');return;}S.hist=S.hist.slice(0,i);S.scr=id;closeSheetNow();render('pop');}
function toast(msg){var p=$('#phone');if(!p)return;var old=p.querySelector('.toast');if(old)old.remove();var d=document.createElement('div');d.className='toast';d.setAttribute('role','status');d.textContent=msg;p.appendChild(d);setTimeout(function(){d.remove();},2600);}
function openSheet(name,data){S.sheet=name;S.sd=data||{};renderOverlay(true);}
function stopPoll(){if(S.poll){clearInterval(S.poll);S.poll=null;}}
function closeSheet(){var o=$('#ovl');if(!S.sheet&&!S.dialog)return;stopPoll();S.sheet=null;S.dialog=null;o.classList.add('closing');var sh=o.querySelector('.sheet,.dlg');if(sh)sh.classList.add('closing');
 setTimeout(function(){o.classList.remove('closing');if(!S.sheet&&!S.dialog){o.className='ovl';o.innerHTML='';}},240);}
function closeSheetNow(){stopPoll();S.sheet=null;S.dialog=null;var o=$('#ovl');if(o){o.className='ovl';o.innerHTML='';}}
function renderOverlay(fresh){var o=$('#ovl');if(!S.sheet&&!S.dialog){o.className='ovl';o.innerHTML='';return;}
 var name=S.dialog?'dlg':S.sheet,content=S.dialog?dialogHTML():SHEETS[S.sheet]();var ex=o.querySelector('.sheet,.dlg');
 if(!fresh&&ex&&o.dataset.name===name){var st=ex.scrollTop;var ta=$('#fbc');var tv=ta?ta.value:null;ex.innerHTML=content;ex.scrollTop=st;if(tv!=null&&$('#fbc'))$('#fbc').value=tv;return;}
 o.dataset.name=name;o.className='ovl show';o.innerHTML='<div class="ovbd" data-a="'+(S.dialog?'dlgCancel':'closeSheet')+'"></div>'+(S.dialog?'<div class="dlg" role="alertdialog">'+content+'</div>':'<div class="sheet" role="dialog" aria-modal="true">'+content+'</div>');}
/* ---------- frame ---------- */
function langBtn(){var c=S.cfg&&S.cfg.languages||[];var cur=c.filter(function(l){return l.code===S.lang;})[0];return '<button class="lang" data-a="openLang" aria-label="'+esc(t('language'))+'">'+ic('chat',15,'#fff')+'<b>'+esc(cur?cur.native:(S.lang==='hi'?'हिंदी':'English'))+'</b></button>';}
function frame(o){var n=S.me?S.me.saved.length:0;
 var head='<div class="apph">'+(o.back?'<button class="ib" data-a="back" aria-label="'+t('back')+'">'+ic('back',24,'#fff')+'</button>':'<span style="width:6px"></span>')+
  (o.icon||'<div class="av">'+LOGO(22)+'<span class="vb">'+ic('check',9,'#fff')+'</span></div>')+
  '<div class="who"><b><span class="tt">'+esc(o.title||t('brand'))+'</span>'+(o.title?'':' '+VERIFIED)+'</b><small>'+esc(o.sub||(isTyping()?t('typingS'):t('appSub')))+'</small></div>'+
  (S.me&&!o.noBm?'<button class="ib bm" data-a="goMy" aria-label="'+t('myTitle')+'">'+ic('starF',22,'#fff')+(n?'<i>'+n+'</i>':'')+'</button>':'')+langBtn()+
  '<button class="ib" data-a="openMenu" aria-label="'+esc(t('menuTitle'))+'">'+ic('dots',22,'#fff')+'</button></div>';
 var p=o.progress;var prog=p!=null?'<div class="progress"><div class="seg">'+[1,2,3,4,5].map(function(i){return '<i class="'+(i<=p?'on':'')+'"></i>';}).join('')+'</div><span>'+(p>=5?'✓ '+t('qShort',{n:5}):t('qShort',{n:Math.min(5,p+1)}))+'</span></div>':'';
 return head+prog+'<div class="scroll wall" id="sc">'+o.body+'</div>'+(o.tray||'')+(o.bottom||'');}
/* ---------- chat screen ---------- */
var LBL={state:'lblState',class_passed:'lblEdu',gender:'lblGender',annual_family_income:'lblIncome',category:'lblCat'};
function msgHTML(m,prev){var anim=m.shown?'':' pop';var first=!prev||prev.who!==m.who||prev.who==='sys';
 if(m.who==='day')return '<div class="day"><span>'+esc(m.raw)+'</span></div>';
 if(m.who==='sys')return '<div class="sys'+anim+'">'+waFmt(m.raw)+'</div>';
 if(m.who==='typing')return '<div class="row'+(first?'':' cont')+'"><div class="b'+(first?' tl':'')+' pop" style="padding:12px 14px"><div class="dots"><i></i><i></i><i></i></div></div></div>';
 var tl=first?' tl':'',cont=first?'':' cont';
 if(m.who==='me')return '<div class="row out'+cont+'"><div class="b'+tl+anim+'">'+waFmt(m.raw)+'<span class="meta">'+m.time+' '+TICKS+'</span><div class="clr"></div></div></div>';
 var meta='<span class="meta">'+m.time+'</span><div class="clr"></div>',inner,w='';
 if(m.kind==='q'){inner='<div class="qlbl">'+t('qOf',{n:m.n})+'</div><div style="font-size:16px;font-weight:500">'+waFmt(m.raw)+'</div>'+meta;}
 else if(m.kind==='consent'){inner=waFmt(m.raw)+'<div class="nchip"><span>'+t('noName')+'</span><span>'+t('noAadhaar')+'</span><span>'+t('noBank')+'</span></div>'+meta;}
 else if(m.kind==='review'){w=' w';inner=reviewHTML(m)+meta;}
 else{inner=waFmt(m.raw);
  if(m.links)inner+=m.links.map(function(l){return '<div><a class="extlink" href="'+esc(l.url)+'" target="_blank" rel="noopener noreferrer">'+ic('ext',16)+esc(l.label)+'</a></div>';}).join('');
  if(m.share){w=' w';inner+='<div class="btns v"><button data-a="shareWa" data-v="'+esc(m.share.whatsapp_share_url||'')+'">'+WALOGO(18)+' '+t('sendWa')+'</button><button data-a="copy" data-v="'+esc(m.share.web_link||'')+'">'+ic('share',17)+t('copyLink')+'</button></div>';}
  inner+=meta;}
 return '<div class="row'+cont+'"><div class="b'+tl+w+anim+'">'+inner+'</div></div>';}
function reviewHTML(m){var dis=m.stale?' disabled':'';
 return '<div style="font-size:16px;font-weight:500">'+t('reviewQ')+'</div><small class="hint" style="margin:0 0 4px">'+t('reviewSub')+'</small>'+
  m.rows.map(function(r){return '<div class="ans-row"><div><span>'+esc(r.field||t(LBL[r.key]))+'</span><b>'+esc((r.key==='state'?stl(r.value):r.value)||'–')+'</b></div><button data-a="editAns" data-v="'+r.key+'"'+dis+'>'+t('edit')+'</button></div>';}).join('')+
  '<button class="btn pri blk inbtn" data-a="proceed"'+dis+'>'+ic('sparkle',18)+t('showSchemes')+'</button>';}
function chip(lbl,act,v,cls){return '<button class="qr'+(cls?' '+cls:'')+'" data-a="'+act+'" data-v="'+esc(v)+'">'+lbl+'</button>';}
function trayHTML(){if(isTyping()||S.busy)return '';var h='';
 if(S.pending){h=chip(t('no'),'confirm','no')+chip(ic('check',18)+t('yes'),'confirm','yes','pri');return '<div class="tray" id="tray">'+h+'</div>';}
 var r=S.reply;if(!r)return '';var v=r.view||'',opts=r.options||[];
 if(v==='SUMMARY'||v.indexOf('RESULTS')===0)return '';
 var items=opts.filter(function(o){return (o.kind||'item')==='item';}),navs=opts.filter(function(o){return o.kind==='nav';});
 if(v==='ASK_state'){var q=S.stateQ.trim().toLowerCase(),all=items;
  if(q)items=all.filter(function(o){return stMatch(o,q);}).slice(0,8);
  else if(!S.showAllStates){var lk=(S.cfg&&S.cfg.likely_states)||[];items=all.filter(function(o){return lk.indexOf(o.label)>=0;});}
  h=items.length?items.map(function(o){return chip(esc(stl(o.label)),'opt',o.id+'|'+stl(o.label));}).join(''):'<div class="none">'+t('noState')+'</div>';
  if(!q&&!S.showAllStates)h+=chip(t('showAll')+' ▾','allStates','','nav');}
 else h=items.map(function(o){var lbl=esc(o.label)+(o.desc&&v!=='LANG'?' <small>'+esc(o.desc)+'</small>':'');return chip(lbl,'opt',o.id+'|'+o.label,o.id==='agree'?'pri':'');}).join('');
 h+=navs.map(function(o){return chip(esc(o.label),'opt',o.id+'|'+o.label,'nav');}).join('');
 return h?'<div class="tray" id="tray">'+h+'</div>':'';}
function composer(){var ph=askKey()==='state'?t('ph_state'):askKey()?t('typeAnswer'):t('tapOption');
 return '<form class="comp" data-f="chat" autocomplete="off"><div class="inp"><input id="ci" type="text" enterkeyhint="send" maxlength="500" placeholder="'+esc(ph)+'" aria-label="'+esc(ph)+'"></div>'+
  '<button class="sendb'+(S.rec?' rec':'')+'" type="submit" aria-label="'+esc(t('send'))+'" id="sendb">'+ic('mic',22,'#fff')+'</button></form>';}
SCR.chat=function(){var h='<div class="chat"><div class="day"><span>'+esc(t('todayTest'))+'</span></div>';
 for(var i=0;i<S.msgs.length;i++)h+=msgHTML(S.msgs[i],S.msgs[i-1]);
 return frame({progress:progress(),body:h+'</div>',tray:trayHTML(),bottom:composer()});};
/* ---------- conversation ---------- */
function saveSess(){try{sessionStorage.setItem(SS_SESS,JSON.stringify({sid:S.sid,tok:S.tok}));}catch(e){}}
function handleReply(r,opts){var nl=PACK_OF[r.language]||r.language;if(nl&&nl!=='en'&&!PACK[nl]){loadPack(nl,function(){handleReply(r,opts);});return;}
 opts=opts||{};S.reply=r;S.pending=null;S.stateQ='';S.showAllStates=false;
 if(r.language)S.lang=r.language;document.documentElement.lang=S.lang;
 var v=r.view||'';
 if(v.indexOf('RESULTS')===0&&r.status==='COMPLETED'){push({who:'bot',raw:t('finding')});refresh(true);ev('questions_done');loadResults(function(){go('summary','push');});return;}
 if(v==='SUMMARY'){loadProfile(function(rows){staleReviews();push({who:'bot',kind:'review',rows:rows});refresh(true);});return;}
 if(v==='CONSENT')push({who:'bot',kind:'consent',raw:r.text});
 else if(v.indexOf('ASK_')===0){var parts=String(r.text||'').split('\n\n');var q=parts.pop();parts.forEach(function(p){if(p.trim())push({who:'bot',raw:p});});
  push({who:'bot',kind:'q',n:QKEYS.indexOf(v.slice(4))+1,raw:q.replace(/^\(\d\/\d\)\s*/,'')});}
 else{var m=push({who:'bot',raw:r.text||''});if(r.ui&&r.ui.external_links)m.links=r.ui.external_links;if(r.share&&(v==='REFER'||v==='SHARED'))m.share=r.share;}
 refresh(true);}
function sendText(text,echo,opts){opts=opts||{};if(!S.sid||S.busy)return;if(echo)push({who:'me',raw:echo});
 S.busy=true;push({who:'typing'});refresh(true);
 api('POST','/v1/chat/sessions/'+S.sid+'/messages',{text:text}).then(function(res){S.busy=false;dropTyping();
  if(!res.ok){push({who:'sys',raw:t('netErr')});refresh(true);return;}
  var d=res.data;if(d.new_session){S.sid=d.session_id;saveSess();if(opts.clear!==false){S.msgs=[];S.res=null;S.checks={};}}
  if(opts.clear)S.msgs=[];
  handleReply(d.reply);});}
function loadProfile(cb){api('GET','/v1/companion/sessions/'+S.sid+'/results').then(function(res){cb(res.ok?res.data.profile:[]);});}
function loadResults(cb){api('GET','/v1/companion/sessions/'+S.sid+'/results').then(function(res){if(!res.ok){toast(t('netErr'));return;}S.res=res.data;if(res.data.linked_phone)S.linked=res.data.linked_phone;if(cb)cb();});}
function typed(v){var k=askKey();
 if(S.pending){if(/^(y|yes|ok|haan|han|ha|हाँ|हां|ठीक)/i.test(v))return ACT.confirm('yes');if(/^(n|no|nahi|nahin|नहीं)/i.test(v))return ACT.confirm('no');}
 if(!k){sendText(v,v);return;}
 push({who:'me',raw:v});S.busy=true;refresh(true);
 api('POST','/v1/companion/sessions/'+S.sid+'/interpret',{text:v,key:k}).then(function(res){S.busy=false;var d=res.data||{};
  if(res.ok&&d.understood&&d.exact){sendText(d.send,null);return;}
  if(res.ok&&d.understood){S.pending={send:d.send,label:stl(d.label)};push({who:'bot',raw:t('youMean',{x:stl(d.label)})});refresh(true);return;}
  sendText(v,null);});}
ACT.confirm=function(v){var p=S.pending;if(!p)return;S.pending=null;if(v==='yes'){sendText(p.send,t('yes'));}else{push({who:'me',raw:t('no')});push({who:'bot',raw:t('pickAbove')});refresh(true);}};
ACT.opt=function(v){var i=v.indexOf('|');sendText(v.slice(0,i),v.slice(i+1));};
ACT.allStates=function(){S.showAllStates=true;refresh(true);};
ACT.editAns=function(k){staleReviews();if(S.scr!=='chat')popTo('chat');sendText('edit:'+k,t('edit')+' · '+t(LBL[k]));};
ACT.proceed=function(){staleReviews();if(curView().indexOf('RESULTS')===0&&S.res){refresh();go('summary','push');return;}sendText('proceed',t('showSchemes'));};
ACT.shareWa=function(u){if(u){window.open(u,'_blank','noopener');ev('shared',null,{via:'whatsapp'});}};
ACT.copy=function(u){copyText(u);};
function copyText(u){if(!u)return;var done=function(){toast(t('copied'));};if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(u).then(done,function(){prompt('',u);});}else{prompt('',u);}}
/* ---------- scheme helpers ---------- */
var DOCS={
 aadhaar:{n:["Aadhaar card","आधार कार्ड"],p:["You'll need it when you apply","आवेदन करते समय इसकी ज़रूरत होगी"],w:["Aadhaar Seva Kendra, bank or post office","आधार सेवा केंद्र, बैंक या डाकघर"],c:["Free (update ₹50)","मुफ़्त (अपडेट ₹50)"],t:["Up to 30 days if new","नया बनवाने में 30 दिन तक"]},
 domicile:{n:["Domicile / residence certificate","मूल निवास प्रमाण पत्र"],p:["Shows the State you live in","आप किस राज्य में रहते हैं, यह बताता है"],w:["Tehsil office, CSC centre or State e-district portal","तहसील कार्यालय, CSC केंद्र या राज्य ई-डिस्ट्रिक्ट पोर्टल"],c:["₹10–50","₹10–50"],t:["7–15 days","7–15 दिन"]},
 caste:{n:["Caste certificate","जाति प्रमाण पत्र"],p:["Shows your category (SC/ST/OBC)","आपकी श्रेणी (SC/ST/OBC) बताता है"],w:["Tehsil office or CSC centre","तहसील कार्यालय या CSC केंद्र"],c:["₹25–50","₹25–50"],t:["15–30 days","15–30 दिन"]},
 income:{n:["Income certificate","आय प्रमाण पत्र"],p:["Shows your family's yearly income","परिवार की सालाना आय बताता है"],w:["Tehsil office, CSC centre or State portal","तहसील कार्यालय, CSC केंद्र या राज्य पोर्टल"],c:["₹25–50","₹25–50"],t:["7–15 days","7–15 दिन"]},
 marks:{n:["Last exam marksheet","पिछली परीक्षा की मार्कशीट"],p:["Marks card of your last class","पिछली कक्षा का अंक पत्र"],w:["Your school or college office","आपके स्कूल या कॉलेज का कार्यालय"],c:["Free","मुफ़्त"],t:["Same day","उसी दिन"]},
 fee:{n:["Fee receipt / admission letter","फ़ीस रसीद / एडमिशन पत्र"],p:["Proof that you study this year","इस साल पढ़ाई का सबूत"],w:["College accounts office","कॉलेज का अकाउंट्स ऑफिस"],c:["Free","मुफ़्त"],t:["1–2 days","1–2 दिन"]},
 bank:{n:["Bank passbook (Aadhaar-linked)","बैंक पासबुक (आधार से जुड़ी)"],p:["Your own account, linked to Aadhaar","आपका अपना खाता, आधार से जुड़ा"],w:["Any bank or India Post Payments Bank","कोई भी बैंक या इंडिया पोस्ट पेमेंट्स बैंक"],c:["Free (zero-balance account)","मुफ़्त (ज़ीरो बैलेंस खाता)"],t:["1–7 days","1–7 दिन"]},
 class12:{n:["Class 12 marksheet","कक्षा 12 की मार्कशीट"],p:["From your board / school","आपके बोर्ड / स्कूल से"],w:["Your school or board website","आपका स्कूल या बोर्ड की वेबसाइट"],c:["Free","मुफ़्त"],t:["Same day","उसी दिन"]},
 degree:{n:["UG / PG certificates","UG / PG प्रमाण पत्र"],p:["Your earlier degree marksheets","आपकी पिछली डिग्री की मार्कशीट"],w:["Your university office","आपके विश्वविद्यालय का कार्यालय"],c:["Free","मुफ़्त"],t:["1–7 days","1–7 दिन"]},
 research:{n:["Research / admission letter","शोध / प्रवेश पत्र"],p:["From your guide or department","आपके गाइड या विभाग से"],w:["Your department office","आपके विभाग का कार्यालय"],c:["Free","मुफ़्त"],t:["1–7 days","1–7 दिन"]},
 photo:{n:["Passport-size photo","पासपोर्ट साइज़ फ़ोटो"],p:["Recent photo, light background","हाल की फ़ोटो, हल्का बैकग्राउंड"],w:["Any photo studio","किसी भी फ़ोटो स्टूडियो में"],c:["₹30–60","₹30–60"],t:["Same day","उसी दिन"]},
 disability:{n:["Disability certificate (UDID)","दिव्यांगता प्रमाण पत्र (UDID)"],p:["Only if the scheme asks for it","केवल अगर योजना माँगे"],w:["District hospital / swavlambancard.gov.in","ज़िला अस्पताल / swavlambancard.gov.in"],c:["Free","मुफ़्त"],t:["15–60 days","15–60 दिन"]}
};
function L(p){return p?((ui()==='hi'&&p[1])?p[1]:p[0]):'';}
function DL(k,f){var q=pk(),x=q&&q.docs&&q.docs[k];return (x&&x[f])||L(DOCS[k]&&DOCS[k][f]);}
function docName(d){var x=DOCS[d.key];return x?DL(d.key,'n'):d.raw;}
function tileFor(c){return c.is_state?'home':(/girl|women|beti/i.test(c.name)?'star':/merit|top class|national/i.test(c.name)?'medal':'cap');}
function srcLine(c){return (c.is_state?stl(c.state_ut):t('central'))+(c.portal?' · '+c.portal:'');}
function stOf(c){var x=S.checks[c.scheme_id];if(c.status==='check'){if(x==='yes')return 'ok';if(x==='no')return 'no';return 'chk';}return 'ok';}
function chkQ(c){var g=(c.check||[])[0];if(!g)return '';if(g.k==='income'&&g.x)return t('chk_income',{x:Number(g.x).toLocaleString('en-IN')});return t('chk_group',{g:t('g_'+g.k)});}
function amtHTML(c){if(!c.amount_per_year)return '<b class="rs" style="font-size:14px">'+t('amountUnknown')+'</b>';return '<b class="rs">'+money(c.amount_per_year)+' '+kindTxt(c)+'</b>';}
function kindTxt(c){return c.amount_kind==='once'?t('once'):c.amount_kind==='total'?t('inTotal'):t('perYear');}
function dlHTML(c){if(!c.last_date)return '<span class="dl" style="color:var(--ink2)">'+t('lastDateUnknown')+'</span>';return '<span class="dl">'+fmtD(c.last_date)+' · <i class="'+(c.days_left<15?'':'ok')+'">'+daysTxt(c.days_left)+'</i></span>';}
function pillFor(st){return st==='ok'?'<span class="pill p-ok">'+ic('check',13)+t('eligible')+'</span>':st==='chk'?'<span class="pill p-chk">'+ic('info',13)+t('check1')+'</span>':'<span class="pill p-no">'+t('notElig')+'</span>';}
function isSaved(id){return !!(S.me&&S.me.saved.some(function(x){return x.scheme_id===id;}));}
function whyText(w){var k=w.k,x=w.x;if(k==='state')return t('wState',{x:stl(x)});if(k==='region')return t('wRegion',{x:x});if(k==='cat')return t('wCat',{x:x});if(k==='girl')return t('wGirl');
 if(k==='edu')return t('wEduL',{x:t('lv_'+x)});if(k==='inc')return t('wIncY',{x:Number(x).toLocaleString('en-IN')});if(k==='inc_check')return t('wIncChk',{x:Number(x).toLocaleString('en-IN')});if(k==='age')return t('wAge',{x:x});return t('wOpen');}
/* ---------- summary ---------- */
function cardHTML(c){var st=stOf(c),sv=isSaved(c.scheme_id);
 var h='<div class="row"><div class="b w card" id="card-'+esc(c.scheme_id)+'"><div class="prev'+(c.is_state?' st':'')+'"><button style="display:flex;gap:10px;align-items:center;flex:1;min-width:0;text-align:left" data-a="detail" data-v="'+esc(c.scheme_id)+'">'+tile(tileFor(c))+'<span class="tx"><span class="src">'+esc(srcLine(c))+'</span><span class="nm" style="display:block">'+esc(c.name)+'</span></span></button><button class="star" data-a="star" data-v="'+esc(c.scheme_id)+'" aria-label="'+t(sv?'saved':'save')+'">'+ic(sv?'starF':'star',22,sv?'#F2A900':'#8696A0')+'</button></div>'+
  '<div class="body"><div class="facts"><div class="f"><small>'+t('amount')+'</small>'+amtHTML(c)+'</div><div class="f"><small>'+t('lastDate')+'</small>'+dlHTML(c)+'</div></div>'+
  '<div class="strow">'+pillFor(st)+'<span class="doc">'+ic('doc',14,'#54656F')+t(st==='chk'?'docsShort':'docsNeeded',{n:(c.documents||[]).length})+'</span></div>'+
  (st==='chk'?'<div class="ask"><b>'+t('oneCheck')+'</b>'+esc(chkQ(c))+(S.checks[c.scheme_id]==='ns'?'<div style="margin-top:4px;font-size:12.5px;color:#7A5800">💡 '+t('askOffice')+'</div>':'')+'</div>':'')+'</div>';
 h+=st==='chk'?'<div class="btns"><button data-a="chk" data-v="'+esc(c.scheme_id)+'|yes">'+t('yes')+'</button><button data-a="chk" data-v="'+esc(c.scheme_id)+'|no">'+t('no')+'</button><button data-a="chk" data-v="'+esc(c.scheme_id)+'|ns">'+t('notSure')+'</button></div>'
  :'<div class="btns"><button data-a="steps" data-v="'+esc(c.scheme_id)+'">'+ic('list',17)+t('seeSteps')+'</button><button data-a="apply" data-v="'+esc(c.scheme_id)+'">'+ic('ext',16)+t('applyNow')+'</button></div>';
 return h+'</div></div>';}
function cardById(id){var r=S.res;if(r)for(var i=0;i<r.cards.length;i++)if(r.cards[i].scheme_id===id)return r.cards[i];if(S.det&&S.det.scheme_id===id)return S.det;return null;}
SCR.summary=function(){var r=S.res||{cards:[],summary:{},profile:[]};var all=r.cards,list=all.filter(function(c){return stOf(c)!=='no';});
 var ok=list.filter(function(c){return stOf(c)==='ok';}),chk=list.filter(function(c){return stOf(c)==='chk';}),soon=list.filter(function(c){return c.closing_soon;});
 var known=list.filter(function(c){return c.amount_per_year&&c.amount_kind==='year';}),f=S.filter;
 /* 2 Oct: "Up to X a year" = biggest single yearly amount (eligible first), never a sum - same rule as the API's summary.max_per_year */
 var pool=known.filter(function(c){return stOf(c)==='ok';});if(!pool.length)pool=known;
 var top=pool.reduce(function(a,c){return c.amount_per_year>a?c.amount_per_year:a;},0);
 var fl=list.filter(function(c){return f==='all'||(f==='ok'&&stOf(c)==='ok')||(f==='chk'&&stOf(c)==='chk')||(f==='soon'&&c.closing_soon);});
 var prof=(r.profile||[]).filter(function(p){return p.value;}).map(function(p){return p.key==='state'?stl(p.value):p.value;}).join(' · ');
 var b='<div class="chat"><div class="day"><span>'+esc(t('todayTest'))+'</span></div>';
 b+='<div class="row out"><div class="b tl"><div style="font-size:12.5px;color:var(--teal-d);font-weight:500;margin-bottom:2px">'+t('myDetails')+'</div><div>'+esc(prof)+'</div><button class="edit" data-a="editDetails">'+ic('edit',15,'#027EB5')+t('editDetails')+'</button><span class="meta">'+nowStr()+' '+TICKS+'</span><div class="clr"></div></div></div>';
 if(S.linked)b+='<div class="sys">'+ic('check',12,'#0A7A3E',' style="display:inline;vertical-align:-1px"')+' '+esc(t('linkedNum',{p:S.linked}))+'</div>';
 if(!list.length){b+='<div class="row"><div class="b tl w">'+t('noMatch')+'<span class="meta">'+nowStr()+'</span><div class="clr"></div></div></div>';}
 else{b+='<div class="row"><div class="b tl w hero"><div class="top"><div class="hi">'+t('namasteAnon')+'</div><h1>'+t('canApply')+'<br><em>'+(list.length===1?t('nSch1'):t('nSch',{n:list.length}))+'</em></h1>'+
  (top?'<div class="amt"><div><small>'+t('couldGet')+'</small><strong>'+esc(t('upTo',{x:money(top)}))+'</strong><small style="font-weight:400;color:var(--ink2)">'+esc(t('maxNote'))+'</small></div><svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#008069" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7h18v12H3z"/><path d="M3 11h18"/><path d="M7 15h3"/><path d="M6 7l8-4 2 4"/></svg></div>':'')+
  '<div class="pills">'+(ok.length?'<span class="pill p-ok">'+ic('check',13)+t('nEligible',{n:ok.length})+'</span>':'')+(chk.length?'<span class="pill p-chk">'+ic('info',13)+t('nCheck',{n:chk.length})+'</span>':'')+(r.summary&&r.summary.state_schemes?'<span class="pill p-st">'+esc(t('stateFirst'))+'</span>':'')+'</div></div>'+
  '<div class="trust">'+ic('shield',14,'#008069')+'<b>'+t('official')+'</b><span class="tl1">· '+t('trustLine')+'</span><span class="meta" style="margin:0 0 0 auto">'+nowStr()+'</span></div></div></div>';
  var cl=r.summary&&r.summary.closest;
  b+='<div class="row cont"><div class="b w warnb"><div class="t">'+ic('clock',14,'#B26A00')+t('closest')+'</div>'+(cl?'<p><b>'+esc(cl.name)+'</b> '+t('closesOn')+' <b style="white-space:nowrap">'+fmtD(cl.last_date)+'</b> <span class="days">'+daysTxt(cl.days_left)+'</span></p>':'<p>'+esc(t('noDatesYet'))+'</p>')+'<span class="meta">'+nowStr()+'</span><div class="clr"></div></div></div>';
  b+='<div class="fchips">'+[['all',t('f_all',{n:list.length})],['ok',t('f_ok')+' '+ok.length],['chk',t('f_chk')+' '+chk.length],['soon',t('f_soon')+(soon.length?' '+soon.length:'')]].map(function(x){return '<button class="fc'+(f===x[0]?' on':'')+'" data-a="filter" data-v="'+x[0]+'">'+x[1]+'</button>';}).join('')+'</div>';
  b+=fl.length?fl.map(cardHTML).join(''):'<div class="sys">'+t('noneHere')+'</div>';}
 var no=all.filter(function(c){return stOf(c)==='no';});
 if(no.length)b+='<div class="nolist"><b style="font-weight:500;display:block;padding-top:4px">'+t('notForYou')+'</b>'+no.map(function(c){return '<div><span>'+esc(c.name)+'</span><button data-a="chk" data-v="'+esc(c.scheme_id)+'|undo">'+t('undo')+'</button></div>';}).join('')+'</div>';
 b+='<div class="row cont"><div class="b w" style="padding:2px 12px">'+[['feedback','openFb',ic('smile',20,'#008069')],['referTitle','openRefer',ic('people',20,'#008069')]].map(function(x){return '<button class="linkrow" data-a="'+x[1]+'">'+x[2]+t(x[0])+'<span class="go">'+ic('chevron',20,'#AEBAC1')+'</span></button>';}).join('')+'</div></div>';
 b+='<div class="note">'+(S.lang!=='en'?esc(t('schemeEnNote'))+'<br>':'')+esc(t('testData'))+'</div><div style="height:8px"></div></div>';
 var bot=S.me?'<div class="botbar"><button class="cta-in" data-a="goMy">'+WALOGO(28)+'<span><b>'+ic('check',15,'#0A7A3E',' style="display:inline;vertical-align:-2px"')+' '+t('savedWa')+'</b><small>'+t('savedWaSub')+'</small></span></button><button class="round" data-a="goMy" aria-label="'+t('myTitle')+'">'+ic('starF',24,'#fff')+'</button></div>'
  :'<div class="botbar"><button class="cta-in" data-a="openSave" data-v="all">'+WALOGO(28)+'<span><b>'+t('saveWa')+'</b><small>'+t('saveWaSub')+'</small></span></button><button class="round" data-a="openSave" data-v="all" aria-label="'+t('saveWa')+'">'+ic('bell',24,'#fff')+'</button></div>';
 return frame({body:b,bottom:bot});};
ACT.filter=function(v){S.filter=v;refresh();ev('filter',null,{f:v});};
ACT.chk=function(v){var p=v.split('|');if(p[1]==='undo')delete S.checks[p[0]];else S.checks[p[0]]=p[1];if(p[1]==='yes')toast('✓ '+t('checkYesAck'));render(false);};
ACT.editDetails=function(){popTo('chat');loadProfile(function(rows){staleReviews();push({who:'bot',kind:'review',rows:rows});refresh(true);});};
/* ---------- details ---------- */
function docsCount(d){var h=S.docsHave[d.scheme_id]||{},docs=d.documents||[];return {a:docs.filter(function(x){return h[x.key];}).length,b:docs.length||1};}
SCR.details=function(){var d=S.det;if(!d)return frame({back:1,title:t('loading'),body:'<div class="sys" style="margin-top:20px">'+t('loading')+'</div>'});
 var st=stOf(d),dc=docsCount(d),sv=isSaved(d.scheme_id),have=S.docsHave[d.scheme_id]||{};
 var b='<div class="chat" style="padding-top:12px">';
 b+='<div class="row"><div class="b tl w card"><div class="prev'+(d.is_state?' st':'')+'">'+tile(tileFor(d))+'<span class="tx"><span class="src">'+esc(srcLine(d))+'</span><span class="nm" style="display:block;font-size:16px">'+esc(d.name)+'</span></span></div>'+
  '<div class="body"><div class="facts"><div class="f"><small>'+t('amount')+'</small>'+amtHTML(d)+'</div><div class="f"><small>'+t('lastDate')+'</small>'+dlHTML(d)+'</div></div>'+
  (d.benefit?'<div style="font-size:13.5px;color:var(--ink2);margin-top:6px">'+esc(d.benefit)+'</div>':'')+
  '<div class="strow">'+pillFor(st)+'<span class="doc">'+ic('doc',14,'#54656F')+t('docsNeeded',{n:(d.documents||[]).length})+'</span><span class="meta" style="margin:0 0 0 auto">'+nowStr()+'</span></div></div>'+
  '<div class="btns"><button data-a="listen">'+ic('speaker',18)+t('listen')+'</button><button data-a="openShare" data-v="'+esc(d.scheme_id)+'">'+ic('people',18)+t('shareParent')+'</button></div></div></div>';
 if(d.short_description&&d.short_description.trim()!==(d.benefit||'').trim()&&d.short_description.trim()!==(d.amount_text||'').trim())b+='<div class="row cont"><div class="b w">'+esc(d.short_description)+'<span class="meta">'+nowStr()+'</span><div class="clr"></div></div></div>';
 b+='<div class="row cont"><div class="b w"><div class="sec-t">'+ic('check',15,'#005C4B')+t('whyMatch')+'</div><ul class="why">'+(d.why||[]).map(function(w){return '<li>'+ic('check',16,'#0A7A3E')+'<span>'+esc(whyText(w))+'</span></li>';}).join('')+'</ul><span class="meta">'+nowStr()+'</span><div class="clr"></div></div></div>';
 if(st==='chk')b+='<div class="row cont"><div class="b w" id="chkq" style="border-left:4px solid #F2A900"><div class="sec-t" style="color:#9A5B00">'+ic('info',15,'#9A5B00')+t('oneCheck')+'</div><div style="font-size:15px">'+esc(chkQ(d))+'</div><span class="meta">'+nowStr()+'</span><div class="clr"></div><div class="btns"><button data-a="chk" data-v="'+esc(d.scheme_id)+'|yes">'+t('yes')+'</button><button data-a="chk" data-v="'+esc(d.scheme_id)+'|no">'+t('no')+'</button><button data-a="chk" data-v="'+esc(d.scheme_id)+'|ns">'+t('notSure')+'</button></div></div></div>';
 b+='<div class="row cont"><div class="b w" id="docs"><div class="sec-t">'+ic('doc',15,'#005C4B')+t('docsTitle')+'<span style="margin-left:auto;text-transform:none;letter-spacing:0;color:var(--ink2);font-weight:500">'+t('docsReady',{a:dc.a,b:(d.documents||[]).length})+'</span></div><div class="meter"><i style="width:'+Math.round(dc.a/dc.b*100)+'%"></i></div><small class="hint" style="margin:0 0 2px">'+t('docsTick')+'</small>'+
  (d.documents||[]).map(function(x){var k=x.key,dd=DOCS[k],on=!!have[k],op=!!S.docOpen[d.scheme_id+':'+k];
   return '<div class="dk"><div style="display:flex;align-items:center"><button class="dkrow'+(on?' on':'')+'" data-a="doc" data-v="'+esc(d.scheme_id)+'|'+k+'" role="checkbox" aria-checked="'+on+'"><span class="cb'+(on?' on':'')+'">'+(on?ic('check',16,'#fff'):'')+'</span><span class="dn"><b>'+esc(docName(x))+'</b><span>'+esc(dd?DL(k,'p'):x.raw)+'</span></span></button>'+(dd?'<button class="how" data-a="how" data-v="'+esc(d.scheme_id)+'|'+k+'">'+t('howGet')+ic(op?'chevD':'chevron',16,'#027EB5')+'</button>':'')+'</div>'+
   (op&&dd?'<div class="howbox"><span>'+t('where')+'</span><b style="font-weight:500">'+esc(DL(k,'w'))+'</b><span>'+t('cost')+'</span><b style="font-weight:500">'+esc(DL(k,'c'))+'</b><span>'+t('time')+'</span><b style="font-weight:500">'+esc(DL(k,'t'))+'</b></div>':'')+'</div>';}).join('')+'<span class="meta">'+nowStr()+'</span><div class="clr"></div></div></div>';
 b+='<div class="row cont"><div class="b w" id="steps"><div class="sec-t">'+ic('list',15,'#005C4B')+t('stepsTitle')+'</div><ol class="steps"><li><i>1</i><span>'+esc(t('step1',{p:d.portal||'scholarships.gov.in'}))+'</span></li><li><i>2</i><span>'+esc(t('step2'))+'</span></li><li><i>3</i><span>'+esc(t('step3'))+'</span></li></ol><span class="meta">'+nowStr()+'</span><div class="clr"></div></div></div>';
 b+='<div class="safety">'+ic('shield',16,'#8A6A00')+'<span>'+t('neverPay')+'</span></div><div class="note">'+(S.lang!=='en'?esc(t('schemeEnNote'))+'<br>':'')+esc(t('testData'))+'</div><div style="height:6px"></div></div>';
 var bot='<div class="dbar"><button class="btn out" data-a="star" data-v="'+esc(d.scheme_id)+'">'+ic(sv?'starF':'star',20,sv?'#F2A900':'#005C4B')+t(sv?'saved':'save')+'</button><button class="btn pri" data-a="apply" data-v="'+esc(d.scheme_id)+'">'+t('applyOfficial')+ic('ext',17,'#fff')+'</button></div>';
 return frame({back:1,title:d.name,sub:srcLine(d),icon:'<span style="margin-left:-2px">'+tile(tileFor(d),36)+'</span>',body:b,bottom:bot});};
function openDetail(id,scrollTo){S.detId=id;var c=cardById(id);S.det=(S.det&&S.det.scheme_id===id)?S.det:null;S.scrollTo=scrollTo||null;go('details','push');
 api('GET','/v1/companion/sessions/'+S.sid+'/schemes/'+encodeURIComponent(id)).then(function(res){if(!res.ok){toast(t('netErr'));return;}if(S.detId!==id)return;S.det=res.data;
  var sv=S.me&&S.me.saved.filter(function(x){return x.scheme_id===id;})[0];if(sv&&sv.docs_have)S.docsHave[id]=Object.assign({},sv.docs_have,S.docsHave[id]||{});
  if(S.scr==='details'){S.scrollTo=scrollTo||null;var cur=$('.scr:not(.leaving)');if(cur){cur.innerHTML=SCR.details();if(scrollTo){var sc=cur.querySelector('.scroll'),tg=cur.querySelector('#'+scrollTo);if(sc&&tg)sc.scrollTop=tg.getBoundingClientRect().top-sc.getBoundingClientRect().top-10;}}S.scrollTo=null;}});}
ACT.detail=function(v){var p=String(v).split('|');openDetail(p[0],p[1]);};
ACT.steps=function(v){openDetail(v,'steps');};
ACT.doc=function(v){var p=v.split('|');var h=S.docsHave[p[0]]=S.docsHave[p[0]]||{};h[p[1]]=!h[p[1]];render(false);
 if(isSaved(p[0]))api('PATCH','/v1/companion/me/schemes/'+encodeURIComponent(p[0]),{docs_have:h},{quiet:1}).then(function(r){if(r.ok)S.me=r.data.me;});};
ACT.how=function(v){var k=v.replace('|',':');S.docOpen[k]=!S.docOpen[k];render(false);};
ACT.star=function(v){if(!S.me){openSave(v);return;}
 if(isSaved(v)){api('DELETE','/v1/companion/me/schemes/'+encodeURIComponent(v)).then(function(r){if(r.ok){S.me=r.data;toast(t('removedToast'));render(false);}});}
 else{api('POST','/v1/companion/me/schemes',{scheme_ids:[v]}).then(function(r){if(r.ok){S.me=r.data;toast(t('savedToast'));render(false);}});}};
ACT.apply=function(v){openSheet('apply',{id:v});};
ACT.openShare=function(v){openSheet('share',{id:v});};
/* Listen: server TTS (SPEECH_*) -> device voice -> "coming soon" */
var AUDIO=null;
function listenText(d){var p=[d.name];if(d.amount_per_year)p.push(t('amount')+': '+money(d.amount_per_year)+' '+kindTxt(d));if(d.last_date)p.push(t('lastDate')+': '+fmtD(d.last_date));
 (d.why||[]).forEach(function(w){p.push(whyText(w));});p.push(t('neverPayShort'));return p.join('. ');}
function deviceSpeak(text){if(!('speechSynthesis' in window)||typeof SpeechSynthesisUtterance==='undefined')return false;var lang=BCP[S.lang]||'en-IN';
 var vs=window.speechSynthesis.getVoices()||[];var ok=!vs.length||vs.some(function(v){return (v.lang||'').toLowerCase().indexOf(lang.slice(0,2))===0;});if(!ok)return false;
 try{window.speechSynthesis.cancel();var u=new SpeechSynthesisUtterance(text);u.lang=lang;window.speechSynthesis.speak(u);return true;}catch(e){return false;}}
ACT.listen=function(){var d=S.det;if(!d)return;var text=listenText(d);ev('listen',d.scheme_id);
 if(AUDIO){try{AUDIO.pause();}catch(e){}AUDIO=null;}
 var sp=S.cfg&&S.cfg.speech;if(!sp||!sp.tts){if(deviceSpeak(text))toast(t('listenDevice'));else toast(t('listenSoon'));return;}
 api('POST','/v1/speech/tts',{text:text,lang:S.lang},{quiet:1}).then(function(r){
  if(r.ok&&(r.data.audio_base64||r.data.url)){try{AUDIO=new Audio(r.data.url||('data:'+r.data.mime+';base64,'+r.data.audio_base64));var pr=AUDIO.play();if(pr&&pr.catch)pr.catch(function(){toast(t('listenSoon'));});}catch(e){toast(t('listenSoon'));}return;}
  if(deviceSpeak(text))toast(t('listenDevice'));else toast(t('listenSoon'));});};
/* ---------- My schemes ---------- */
var STEPK=['stSaved','stDocs','stApplied','stResult'],STEPV=['saved','docs','applied','result'];
function stepIdx(st){return {saved:0,docs:1,applied:2,result:3,approved:3,rejected:3}[st]||0;}
var REMK={docs_nudge:'remDocs',deadline_7:'rem7',deadline_2:'rem2',result_check:'remResult',renewal_30:'remRenew',new_schemes:'remNew'};
function myCard(it){var id=it.scheme_id,si=stepIdx(it.status),dd={scheme_id:id,documents:it.documents||[]};var h=S.docsHave[id]=Object.assign({},it.docs_have||{},S.docsHave[id]||{});var dc=docsCount(dd);
 var tr='<div class="track">'+STEPK.map(function(k,i){var lbl=i===3&&it.status==='approved'?t('stApproved'):i===3&&it.status==='rejected'?t('stRejected'):t(k);var cls=i<si?'done':i===si?(i===3&&it.status!=='result'?(it.status==='rejected'?'done rej':'done'):'cur'):'';
  return '<button class="'+cls+'" data-a="track" data-v="'+esc(id)+'|'+STEPV[i]+'"><span class="d">'+(cls.indexOf('done')>=0?ic(it.status==='rejected'&&i===3?'close':'check',13,'#fff'):'')+'</span>'+lbl+'</button>';}).join('')+'</div>';
 var nx=(S.me.upcoming||[]).filter(function(u){return u.scheme_id===id;})[0];var x='';
 var dateRow=it.last_date?'':'<div style="display:flex;align-items:center;gap:8px;margin-top:6px;font-size:13px"><span class="muted">'+t('addDate')+'</span><input class="datein" type="date" data-c="lastdate" data-v="'+esc(id)+'" aria-label="'+esc(t('addDate'))+'"></div>';
 if(it.status==='saved'||it.status==='docs'){if(it.status==='docs')x+='<div style="display:flex;align-items:center;gap:8px;margin-top:4px"><div style="flex:1"><div style="font-size:12.5px;color:var(--ink2)">'+t('docsMeter',{a:dc.a,b:(it.documents||[]).length})+'</div><div class="meter" style="margin:4px 0 0"><i style="width:'+Math.round(dc.a/dc.b*100)+'%"></i></div></div><button class="mini" data-a="detail" data-v="'+esc(id)+'|docs">'+ic('doc',14)+t('openChecklist')+'</button></div>';
  x+=nx?'<div class="remchip">'+ic('bell',14,'#005C4B')+t('nextRem',{d:fmtD(nx.due_on)})+'</div>':dateRow;}
 else if(it.status==='applied'){x='<div class="remchip">'+ic('clock',14,'#005C4B')+t('appliedNote')+'</div>';}
 else if(it.status==='result'){x='<div style="font-size:13.5px;margin-top:2px">'+t('pickRes')+'</div><div class="chiprow"><button class="mini g" data-a="result" data-v="'+esc(id)+'|approved">✓ '+t('stApproved')+'</button><button class="mini r" data-a="result" data-v="'+esc(id)+'|rejected">✕ '+t('stRejected')+'</button></div>';}
 else if(it.status==='approved'){x='<div style="font-size:14px;font-weight:500;margin-top:2px">'+t('approvedMsg')+'</div>'+(it.renewal_needed==null?'<div style="font-size:13.5px;margin-top:4px">'+t('renewQ')+'</div><div class="chiprow"><button class="mini g" data-a="renew" data-v="'+esc(id)+'|1">'+t('yes')+'</button><button class="mini" data-a="renew" data-v="'+esc(id)+'|0">'+t('no')+'</button></div>':it.renewal_needed?(it.renewal_date?'<div class="remchip">'+t('renewSet',{d:fmtD(it.renewal_date)})+'</div>':'<div style="display:flex;align-items:center;gap:8px;margin-top:6px;font-size:13px"><span class="muted">'+t('renewDue')+'</span><input class="datein" type="date" data-c="renewdate" data-v="'+esc(id)+'" aria-label="'+esc(t('renewDue'))+'"></div>'):'<div class="remchip" style="background:#F0F2F5;color:var(--ink2)">'+t('noRenew')+'</div>');}
 else if(it.status==='rejected'){x='<div class="remchip" style="background:#FFF3E0;color:#7A4A00">'+t('rejectedTip')+'</div>';}
 var sub=(it.amount_per_year?money(it.amount_per_year)+' '+kindTxt(it):t('amountUnknown'))+' · '+(it.last_date?fmtD(it.last_date)+' · <span style="color:'+(it.days_left<15?'var(--red)':'inherit')+';font-weight:'+(it.days_left<15?700:400)+'">'+daysTxt(it.days_left)+'</span>':t('lastDateUnknown'));
 return '<div class="row cont"><div class="b w mycard" id="my-'+esc(id)+'" style="padding:0;overflow:hidden"><div style="padding:10px 10px 6px"><div style="display:flex;gap:10px;align-items:center">'+tile(it.level==='Central'?'cap':'home',38)+'<div style="flex:1;min-width:0"><div class="nm">'+esc(it.name)+'</div><div class="sub">'+sub+'</div></div></div>'+tr+'<div style="font-size:11.5px;color:var(--ink3);text-align:center;margin-top:-2px">'+t('tapStep')+'</div>'+x+'</div>'+
  '<div class="btns" style="margin:6px 0 0"><button data-a="detail" data-v="'+esc(id)+'">'+ic('list',17)+t('seeSteps')+'</button><button data-a="unsave" data-v="'+esc(id)+'">'+ic('trash',17)+t('remove')+'</button></div></div></div>';}
SCR.my=function(){var m=S.me;if(!m)return frame({back:1,title:t('myTitle'),noBm:1,body:'<div class="sys" style="margin-top:20px">'+t('emptyMy')+'</div>'});var pr=m.preferences||{},st=m.stats||{};
 var tg=function(k,lbl,ico){return '<button class="tgl" data-a="tgl" data-v="'+k+'" role="switch" aria-checked="'+!!pr[k]+'"><span style="display:flex;gap:10px;align-items:center">'+ico+lbl+'</span><span class="sw'+(pr[k]?' on':'')+'"></span></button>';};
 var b='<div class="chat"><div class="day"><span>'+esc(t('todayTest'))+'</span></div>';
 b+='<div class="row"><div class="b tl w"><div style="display:flex;gap:10px;align-items:center;padding:2px 0 6px">'+WALOGO(34)+'<div style="flex:1"><div style="font-size:12.5px;color:var(--ink2)">'+t('remTo')+'</div><b style="font-size:16px;font-weight:500;letter-spacing:.3px">'+esc(m.phone_masked)+'</b></div>'+ic('check',20,'#0A7A3E')+'</div>'+
  tg('deadline',t('tglDeadline'),ic('clock',18,'#008069'))+tg('new',t('tglNew'),ic('sparkle',18,'#008069'))+tg('renew',t('tglRenew'),'<span style="font-size:16px;width:18px;text-align:center">🔁</span>')+'</div></div>';
 b+='<div class="stats"><div class="stat"><b>'+(st.saved||0)+'</b><span>'+t('stSaved')+'</span></div><div class="stat"><b>'+(st.docs||0)+'</b><span>'+t('statDocs')+'</span></div><div class="stat"><b>'+(st.applied||0)+'</b><span>'+t('stApplied')+'</span></div><div class="stat"><b>'+(st.approved||0)+'</b><span>'+t('stApproved')+'</span></div></div>';
 b+=m.saved.length?m.saved.map(myCard).join(''):'<div class="sys">'+t('emptyMy')+'</div>';
 if(pr['new'])b+='<div class="row cont" style="margin-top:6px"><div class="b w" style="border-left:4px solid #25D366"><div class="sec-t">'+ic('sparkle',15,'#005C4B')+t('newAlertT')+'</div><div style="font-size:14px;color:var(--ink2)">'+t('newAlertS')+'</div><span class="meta">'+nowStr()+'</span><div class="clr"></div></div></div>';
 var up=m.upcoming||[];
 b+='<div class="row cont"><div class="b w"><div class="sec-t">'+ic('bell',15,'#005C4B')+t('upcoming')+'</div>'+(up.length?'<ul class="tl">'+up.slice(0,5).map(function(u){var it=m.saved.filter(function(x){return x.scheme_id===u.scheme_id;})[0];return '<li><span class="when">'+esc(fmtD(u.due_on))+'</span><span><b style="font-weight:500">'+esc(t(REMK[u.kind]||'upcoming'))+'</b><br><span class="muted" style="font-size:13px">'+esc(it?it.name:'')+'</span></span></li>';}).join('')+'</ul>':'<div class="muted" style="font-size:13.5px">'+t('noUpcoming')+'</div>')+'<span class="meta">'+nowStr()+'</span><div class="clr"></div></div></div>';
 var rows=[];if(S.cfg&&S.cfg.wa_hi_link)rows.push(['seeWa','openWaChat',WALOGO(22)]);rows.push(['findMore','goSummary',ic('list',20,'#008069')],['referTitle','openRefer',ic('people',20,'#008069')],['feedback','openFb',ic('smile',20,'#008069')],['deleteData','askDelete',ic('trash',20,'#B3261E')]);
 b+='<div class="row cont"><div class="b w" style="padding:2px 12px">'+rows.map(function(r){return '<button class="linkrow" data-a="'+r[1]+'"'+(r[0]==='deleteData'?' style="color:#B3261E"':'')+'>'+r[2]+t(r[0])+'<span class="go">'+ic('chevron',20,'#AEBAC1')+'</span></button>';}).join('')+'</div></div><div class="safety">'+ic('shield',16,'#8A6A00')+'<span>'+t('neverPayShort')+'</span></div><div style="height:10px"></div></div>';
 return frame({back:S.hist.length?1:0,title:t('myTitle'),sub:t('mySub')+' · '+m.saved.length,noBm:1,icon:'<div class="av" style="background:#D9FDD3">'+ic('starF',20,'#008069')+'</div>',body:b});};
function loadMe(cb){if(!S.stTok){if(cb)cb(false);return;}api('GET','/v1/companion/me',undefined,{quiet:1}).then(function(r){if(r.ok){S.me=r.data;}else if(r.status===401){S.stTok=null;S.me=null;try{localStorage.removeItem(LS_ST);}catch(e){}}if(cb)cb(r.ok);});}
function setStudent(tok,me){S.stTok=tok;try{localStorage.setItem(LS_ST,tok);}catch(e){}if(me)S.me=me;}
function patchSaved(id,body,msg){api('PATCH','/v1/companion/me/schemes/'+encodeURIComponent(id),body).then(function(r){if(r.ok){S.me=r.data.me;if(msg)toast(msg);render(false);}else toast(t('netErr'));});}
ACT.goMy=function(){if(S.scr==='my')return;loadMe(function(){go('my','push');});};
ACT.goSummary=function(){if(S.res){popTo('summary');return;}popTo('chat');};
ACT.track=function(v){var p=v.split('|');patchSaved(p[0],{status:p[1]});};
ACT.result=function(v){var p=v.split('|');patchSaved(p[0],{status:p[1]});};
ACT.renew=function(v){var p=v.split('|');patchSaved(p[0],{renewal_needed:p[1]==='1'});};
ACT.unsave=function(v){api('DELETE','/v1/companion/me/schemes/'+encodeURIComponent(v)).then(function(r){if(r.ok){S.me=r.data;toast(t('removedToast'));render(false);}});};
ACT.tgl=function(v){var pr=S.me.preferences,b={};b[v]=!pr[v];api('PUT','/v1/companion/me/preferences',b).then(function(r){if(r.ok){S.me=r.data;render(false);}});};
ACT.openWaChat=function(){if(S.cfg&&S.cfg.wa_hi_link)window.open(S.cfg.wa_hi_link,'_blank','noopener');};
ACT.askDelete=function(){S.dialog='del';renderOverlay(true);};
ACT.dlgCancel=function(){S.dialog=null;renderOverlay(true);};
ACT.delConfirm=function(){api('DELETE','/v1/companion/me').then(function(r){if(!r.ok){toast(t('netErr'));return;}S.me=null;S.stTok=null;try{localStorage.removeItem(LS_ST);}catch(e){}closeSheetNow();toast(t('deleted'));if(S.res)popTo('summary');else popTo('chat');});};
function dialogHTML(){return '<h3>'+t('deleteQ')+'</h3><p>'+t('deleteSub')+'</p><div class="r"><button class="btn out" data-a="dlgCancel">'+t('cancel')+'</button><button class="btn danger" data-a="delConfirm">'+ic('trash',18,'#fff')+t('del')+'</button></div>';}
/* ---------- sheets ---------- */
function shHead(title,icon){return '<div class="grab"></div><div class="shh">'+(icon||'')+'<h3>'+title+'</h3><button class="x" data-a="closeSheet" aria-label="'+t('close')+'">'+ic('close',22)+'</button></div>';}
function featList(){var f=[['ft1','ft1s',ic('starF',18,'#008069')],['ft2','ft2s',ic('clock',18,'#008069')],['ft3','ft3s',ic('sparkle',18,'#008069')],['ft4','ft4s',ic('list',18,'#008069')],['ft5','ft5s','<span style="font-size:16px">🔁</span>']];
 return '<div class="lbl" style="margin:2px 0 2px">'+t('youGet')+'</div><ul class="feat">'+f.map(function(x){return '<li style="padding:4px 0"><span class="fi">'+x[2]+'</span><span><b style="font-weight:500">'+t(x[0])+'</b><small>'+t(x[1])+'</small></span></li>';}).join('')+'</ul>';}
function saveIds(){var d=S.sd;if(d.scope&&d.scope!=='all')return [d.scope];return ((S.res&&S.res.cards)||[]).filter(function(c){return stOf(c)!=='no';}).map(function(c){return c.scheme_id;});}
function scopeLine(){var d=S.sd,txt;if(d.scope==='all')txt=t('savingAll',{n:saveIds().length});else{var c=cardById(d.scope);txt=t('savingOne',{s:c?c.name:d.scope});}return '<div class="pill p-ok" style="margin:0 0 10px;white-space:normal">'+ic('starF',13)+esc(txt)+'</div>';}
function sTg(k,lbl){var on=S.sd.remind[k];return '<button class="tgl" data-a="tglS" data-v="'+k+'" role="switch" aria-checked="'+on+'"><span>'+lbl+'</span><span class="sw'+(on?' on':'')+'"></span></button>';}
function consentLine(){var on=!!S.sd.agree;return '<button class="consent" data-a="agreeS" role="checkbox" aria-checked="'+on+'" style="width:100%;text-align:left"><span class="cb'+(on?' on':'')+'" style="width:22px;height:22px">'+(on?ic('check',14,'#fff'):'')+'</span><span>'+t('consentSave')+'</span></button>'+(S.sd.err==='agree'?'<div class="err" role="alert">'+t('needAgree')+'</div>':'');}
function openSave(scope){openSheet('save',{scope:scope||'all',step:'age',remind:{deadline:true,'new':true,renew:true},agree:false});}
ACT.openSave=function(v){openSave(v);};
SHEETS.save=function(){var d=S.sd,st=d.step,h=shHead(t('saveTitle'),WALOGO(30));
 if(st==='done'){return h+'<div class="okbig"><div class="ring"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#0A7A3E" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></div><h4>'+t('savedOk')+'</h4><p>'+esc(t('rSaved',{n:S.me?S.me.saved.length:saveIds().length}))+'</p></div>'+
  '<div class="stack"><button class="btn pri blk" data-a="goMy">'+ic('starF',18,'#fff')+t('goMy')+'</button><button class="btn out blk" data-a="closeSheet">'+t('keepBrowsing')+'</button></div>';}
 if(st==='age')return h+'<p class="shsub">'+t('saveSub')+'</p>'+scopeLine()+'<div style="font-size:16px;font-weight:500;margin:4px 0 8px">'+t('ageQ')+'</div><div class="stack" style="margin-top:0"><button class="btn out blk" data-a="ageS" data-v="18plus">'+t('age_18')+'</button><button class="btn out blk" data-a="ageS" data-v="u18">'+t('age_u18')+'</button></div>';
 if(st==='known')return h+'<p class="shsub">'+t('saveSub')+'</p>'+scopeLine()+featList()+'<div class="numbox">'+WALOGO(30)+'<div><small>'+t('yourWa')+'</small><b>'+esc(S.linked||(S.me&&S.me.phone_masked)||'')+'</b><small>'+t('fromChat')+'</small></div></div>'+sTg('deadline','⏰ '+t('tglDeadline'))+sTg('new','🎓 '+t('tglNew'))+consentLine()+'<button class="btn pri blk" data-a="doSave">'+ic('check',20,'#fff')+t('oneTap')+'</button>';
 if(st==='phone')return h+'<div class="lbl" style="margin:0 0 8px;color:var(--teal)">'+t('stepOf',{n:1})+'</div>'+scopeLine()+featList()+'<label class="lbl" for="ph" style="margin-top:10px">'+t('enterPhone')+'</label><div class="field"><span class="pre">+91</span><input id="ph" type="tel" inputmode="numeric" maxlength="12" autocomplete="tel-national" placeholder="'+t('phonePh')+'" value="'+esc(d.phone||'')+'"></div>'+(d.err==='phone'?'<div class="err" role="alert">'+t('invalidPhone')+'</div>':'')+consentLine()+'<button class="btn pri blk" data-a="phNext">'+t('next')+ic('chevron',20,'#fff')+'</button>';
 if(st==='hi'){var msg=esc(d.wa_text||'').replace(esc(d.code||''),'<span class="code">'+esc(d.code||'')+'</span>');
  return h+'<div class="lbl" style="margin:0 0 8px;color:var(--teal)">'+t('stepOf',{n:2})+'</div><div style="font-size:16px;font-weight:500">'+t('confirmHi')+'</div><div class="muted" style="font-size:14px;margin-top:2px">'+t('confirmHiSub')+'</div>'+
  '<div class="lbl" style="margin-top:12px">'+(d.wa_link?t('hiReady'):t('sendThis'))+'</div><div class="preview"><div class="row out" style="padding:0"><div class="b tl">'+msg+'<span class="meta">'+TICKS+'</span><div class="clr"></div></div></div></div>'+
  (d.wa_link?'<button class="btn wa blk" data-a="openWaHi">'+WALOGO(22,'#073B22','#25D366')+t('openWaHi')+'</button>':'<div class="err">'+t('waNotSet')+'</div>')+
  (d.waiting?'<div class="wait">'+'<span class="spin"></span>'+t('waitingSave')+'</div>':'')+(d.err==='expired'?'<div class="err">'+t('codeExpired')+'</div>':'');}
 if(st==='parent')return h+'<div style="display:flex;gap:10px;align-items:flex-start;background:#FFF8E6;border-radius:12px;padding:10px 12px;font-size:14px;color:#5A4300">'+ic('people',20,'#9A5B00')+'<span>'+t('parentTitle')+'</span></div>'+scopeLine().replace('margin:0 0 10px','margin:12px 0 4px')+(S.linked?'<div class="numbox">'+WALOGO(26)+'<div><small>'+t('yourWa')+'</small><b>'+esc(S.linked)+'</b></div></div>':'<label class="lbl" for="ph">'+t('yourPhone')+'</label><div class="field"><span class="pre">+91</span><input id="ph" type="tel" inputmode="numeric" maxlength="12" placeholder="'+t('phonePh')+'" value="'+esc(d.phone||'')+'"></div>')+(d.err==='phone'?'<div class="err" role="alert">'+t('invalidPhone')+'</div>':'')+consentLine()+'<button class="btn pri blk" data-a="parentNext">'+t('next')+ic('chevron',20,'#fff')+'</button>';
 if(st==='wait')return h+'<p class="shsub">'+t('parentHow')+'</p>'+(d.parent&&d.parent.message?'<div class="lbl" style="margin:0">'+t('previewLbl')+'</div><div class="preview"><div class="b tl" style="max-width:100%">'+waFmt(d.parent.message)+'<span class="meta">'+TICKS+'</span><div class="clr"></div></div></div>':'')+
  (d.parent&&d.parent.bot_link?'<button class="btn wa blk" data-a="askParent">'+WALOGO(22,'#073B22','#25D366')+t('askParentWa')+'</button>':'<div class="err">'+t('waNotSet')+'</div>')+'<div class="wait"><span class="spin"></span>'+t('waitingParent')+'</div>'+(d.err==='expired'?'<div class="err">'+t('codeExpired')+'</div>':'');
 return h;};
ACT.ageS=function(v){var d=S.sd;d.age=v;d.err=null;d.step=v==='u18'?'parent':((S.linked||S.me)?'known':'phone');renderOverlay();};
ACT.tglS=function(v){S.sd.remind[v]=!S.sd.remind[v];renderOverlay();};
ACT.agreeS=function(){S.sd.agree=!S.sd.agree;if(S.sd.agree&&S.sd.err==='agree')S.sd.err=null;renderOverlay();};
function needAgree(){if(!S.sd.agree){S.sd.err='agree';renderOverlay();return true;}return false;}
function saveBody(extra){var d=S.sd;var b={scheme_ids:saveIds(),scope:d.scope==='all'?'all':'selected',consent:true,age_band:d.age||'18plus',remind:d.remind};for(var k in extra)b[k]=extra[k];return b;}
function afterSaved(data){setStudent(data.student_token,data.me);S.sd.step='done';renderOverlay();render(false);}
ACT.doSave=function(){if(needAgree())return;var el=$('.sheet .btn.pri');if(el)el.classList.add('busy');
 api('POST','/v1/companion/sessions/'+S.sid+'/save',saveBody({})).then(function(r){if(r.ok&&r.data.status==='saved')afterSaved(r.data);else toast((r.data&&r.data.detail&&r.data.detail.message)||t('netErr'));});};
function readPhone(){var v=(($('#ph')||{}).value||S.sd.phone||'').replace(/\D/g,'');if(v.length===12&&v.indexOf('91')===0)v=v.slice(2);S.sd.phone=v;return /^[6-9]\d{9}$/.test(v)?v:null;}
function startPoll(code){stopPoll();var n=0;S.poll=setInterval(function(){n++;if(n>200||!S.sheet){stopPoll();return;}
 api('GET','/v1/companion/sessions/'+S.sid+'/save-status/'+encodeURIComponent(code),undefined,{quiet:1}).then(function(r){if(!r.ok||!S.sheet)return;var st=r.data.status;
  if(st==='confirmed'){stopPoll();if(r.data.student_token)afterSaved(r.data);else{loadMe(function(){S.sd.step='done';renderOverlay();render(false);});}}
  else if(st==='expired'){stopPoll();S.sd.err='expired';renderOverlay();}});},3000);}
ACT.phNext=function(){var v=readPhone();if(!v){S.sd.err='phone';renderOverlay();var i=$('#ph');if(i)i.focus();return;}if(needAgree())return;S.sd.err=null;
 api('POST','/v1/companion/sessions/'+S.sid+'/save',saveBody({phone:v})).then(function(r){if(!r.ok){toast((r.data.detail&&r.data.detail.message)||t('netErr'));return;}
  if(r.data.status==='saved'){afterSaved(r.data);return;}var d=S.sd;d.code=r.data.code;d.wa_text=r.data.wa_text;d.wa_link=r.data.wa_link;d.step='hi';renderOverlay();startPoll(d.code);});};
ACT.openWaHi=function(){var d=S.sd;if(d.wa_link){window.open(d.wa_link,'_blank','noopener');d.waiting=true;renderOverlay();}};
ACT.parentNext=function(){var v=S.linked?null:readPhone();if(!S.linked&&!v){S.sd.err='phone';renderOverlay();return;}if(needAgree())return;S.sd.err=null;
 api('POST','/v1/companion/sessions/'+S.sid+'/save',saveBody(v?{phone:v}:{})).then(function(r){if(!r.ok){toast((r.data.detail&&r.data.detail.message)||t('netErr'));return;}
  var d=S.sd;d.code=r.data.code;d.parent=r.data.parent;d.step='wait';renderOverlay();startPoll(d.code);});};
ACT.askParent=function(){var p=S.sd.parent;if(p&&p.whatsapp_share_url){window.open(p.whatsapp_share_url,'_blank','noopener');api('POST','/v1/companion/sessions/'+S.sid+'/referral',{kind:'parent',via:'whatsapp'},{quiet:1});}};
ACT.closeSheet=function(){closeSheet();};
SHEETS.apply=function(){var c=cardById(S.sd.id)||{},dc=docsCount(c);return shHead(t('leaving'),'<span class="ic" style="width:36px;height:36px;background:#E7F5F0">'+ic('ext',20,'#008069')+'</span>')+
 '<div class="numbox">'+ic('lock',20,'#1E8E3E')+'<div><b>'+esc(c.portal||'')+'</b><small>'+esc(c.name||'')+'</small></div></div>'+
 '<div style="font-size:14px">'+t('keepReady',{a:dc.a,b:(c.documents||[]).length})+'</div><div class="meter" style="margin:6px 0 10px"><i style="width:'+Math.round(dc.a/dc.b*100)+'%"></i></div>'+
 '<div class="safety" style="margin:0 0 4px">'+ic('shield',16,'#8A6A00')+'<span>'+t('neverPay')+'</span></div>'+
 '<div class="stack"><button class="btn pri blk" data-a="goApply" data-v="'+esc(c.scheme_id||'')+'">'+t('continueTo',{d:esc(c.portal||'portal')})+ic('ext',17,'#fff')+'</button><button class="btn out blk" data-a="notReady" data-v="'+esc(c.scheme_id||'')+'">'+t('notReady')+'</button></div>';};
ACT.goApply=function(v){var c=cardById(v);ev('apply_clicked',v);if(c&&c.apply_url)window.open(c.apply_url,'_blank','noopener');closeSheet();
 if(isSaved(v)){var it=S.me.saved.filter(function(x){return x.scheme_id===v;})[0];if(it&&it.status==='saved')patchSaved(v,{status:'docs'});}};
ACT.notReady=function(v){closeSheet();if(S.scr==='details'){var sc=$('.scr:not(.leaving) .scroll'),d=$('#docs');if(sc&&d)sc.scrollTo({top:sc.scrollTop+d.getBoundingClientRect().top-sc.getBoundingClientRect().top-10,behavior:'smooth'});}else openDetail(v,'docs');};
function parentText(c){var docs=(c.documents||[]).slice(0,4).map(docName).join(', ');var link=S.refer?S.refer.web_link:(c.apply_url||'');
 return t('parentMsg',{s:c.name,a:c.amount_per_year?money(c.amount_per_year)+' '+kindTxt(c):t('amountUnknown'),d:c.last_date?fmtD(c.last_date):t('lastDateUnknown'),docs:docs})+'\n'+(c.apply_url||'')+(S.refer?'\n'+t('schemeLink')+' '+S.refer.web_link:'');}
SHEETS.share=function(){var c=cardById(S.sd.id)||{};if(!S.refer)ensureRefer(function(){if(S.sheet==='share')renderOverlay();});
 return shHead(t('shareParent'),'<span class="ic" style="width:36px;height:36px;background:#E7F5F0">'+ic('people',20,'#008069')+'</span>')+'<div class="lbl" style="margin:0">'+t('previewLbl')+'</div><div class="preview"><div class="row out" style="padding:0"><div class="b tl" style="max-width:100%">'+waFmt(parentText(c))+'<span class="meta">'+TICKS+'</span><div class="clr"></div></div></div></div>'+
 '<div class="stack"><button class="btn pri blk" data-a="sendParentMsg">'+WALOGO(20,'#fff','#00A884')+t('sendWa')+'</button></div>';};
ACT.sendParentMsg=function(){var c=cardById(S.sd.id)||{};window.open('https://wa.me/?text='+encodeURIComponent(parentText(c)),'_blank','noopener');
 api('POST','/v1/companion/sessions/'+S.sid+'/referral',{kind:'parent',via:'whatsapp',scheme_id:c.scheme_id||null},{quiet:1});closeSheet();};
/* ---------- feedback + refer a friend ---------- */
SHEETS.fb=function(){var d=S.sd,h=shHead(t('fbTitle'));var f=['😣','🙁','😐','🙂','😄'];
 if(d.sent)return h+'<div class="okbig" style="padding-top:4px"><div class="ring"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#0A7A3E" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></div><p style="font-size:15px;color:var(--ink)">'+t('fbThanks')+'</p></div><div class="stack"><button class="btn pri blk" data-a="openRefer">'+WALOGO(20,'#fff','#00A884')+t('shareFriends')+'</button><button class="btn out blk" data-a="closeSheet">'+t('done')+'</button></div>';
 h+='<div class="faces">'+f.map(function(e,i){return '<button class="'+(d.rating===i+1?'on':'')+'" data-a="rate" data-v="'+(i+1)+'" aria-pressed="'+(d.rating===i+1)+'"><span>'+e+'</span>'+t('fb'+(i+1))+'</button>';}).join('')+'</div>';
 if(d.rating)h+='<label class="lbl" for="fbc">'+t('fbComment')+'</label><textarea class="ta" id="fbc" maxlength="1000">'+esc(d.comment||'')+'</textarea><div class="stack"><button class="btn pri blk" data-a="sendFb">'+t('fbSend')+'</button></div>';
 return h;};
ACT.openFb=function(){openSheet('fb',{rating:0});};
ACT.rate=function(v){S.sd.rating=+v;renderOverlay();};
ACT.sendFb=function(){var d=S.sd,c=(($('#fbc')||{}).value||d.comment||'').trim();
 api('POST','/v1/companion/sessions/'+S.sid+'/feedback',{rating:d.rating,comment:c||null,context:{screen:S.hist.length?S.scr:S.scr,scheme_id:S.scr==='details'&&S.det?S.det.scheme_id:''}}).then(function(r){
  if(!r.ok){toast(t('netErr'));return;}S.refer=r.data.refer||S.refer;d.sent=true;renderOverlay();});};
function ensureRefer(cb){if(S.refer){if(cb)cb();return;}var p=S.me&&!S.sid?api('POST','/v1/companion/me/referral',{kind:'refer'}):api('POST','/v1/companion/sessions/'+S.sid+'/referral',{kind:'refer'},{quiet:1});
 p.then(function(r){if(r.ok)S.refer=r.data;if(cb)cb();});}
SHEETS.refer=function(){var h=shHead(t('referTitle'),'<span class="ic" style="width:36px;height:36px;background:#E7F5F0">'+ic('people',20,'#008069')+'</span>');var r=S.refer;
 if(!r)return h+'<div class="wait"><span class="spin"></span>'+t('loading')+'</div>';
 return h+'<p class="shsub">'+t('referSub')+'</p><div class="refcode"><div><small class="muted" style="display:block;font-size:12.5px">'+t('referCode')+'</small><b>'+esc(r.share_code)+'</b></div><button class="linkbtn" data-a="copy" data-v="'+esc(r.web_link)+'">'+t('copyLink')+'</button></div>'+
  '<div class="lbl" style="margin:0">'+t('previewLbl')+'</div><div class="preview"><div class="row out" style="padding:0"><div class="b tl" style="max-width:100%">'+waFmt(r.share_message||r.web_link)+'<span class="meta">'+TICKS+'</span><div class="clr"></div></div></div></div>'+
  '<div class="stack"><button class="btn wa blk" data-a="referWa">'+WALOGO(22,'#073B22','#25D366')+t('sendWa')+'</button>'+(navigator.share?'<button class="btn out blk" data-a="referNative">'+ic('share',18)+t('moreShare')+'</button>':'')+'</div>';};
ACT.openRefer=function(){openSheet('refer',{});ensureRefer(function(){if(S.sheet==='refer')renderOverlay();});};
function logShare(via){if(S.sid)api('POST','/v1/companion/sessions/'+S.sid+'/referral',{kind:'refer',via:via},{quiet:1});else if(S.me)api('POST','/v1/companion/me/referral',{kind:'refer',via:via},{quiet:1});}
ACT.referWa=function(){var r=S.refer;if(!r)return;window.open(r.whatsapp_share_url,'_blank','noopener');logShare('whatsapp');};
ACT.referNative=function(){var r=S.refer;if(!r||!navigator.share)return;navigator.share({text:r.share_message,url:r.web_link}).then(function(){logShare('native');},function(){});};
/* ---------- language + menu ---------- */
SHEETS.lang=function(){var c=(S.cfg&&S.cfg.languages)||[{code:'en',native:'English',en:'English'},{code:'hi',native:'हिंदी',en:'Hindi'}];
 return shHead(t('chooseLang'))+'<div class="langlist">'+c.map(function(l){return '<button class="'+(l.code===S.lang?'on':'')+'" data-a="setLang" data-v="'+l.code+'">'+esc(l.native)+'<small>'+esc(l.en)+'</small></button>';}).join('')+'</div>';};
ACT.openLang=function(){openSheet('lang');};
ACT.setLang=function(code){closeSheetNow();if(code===S.lang||!S.sid){S.lang=code;document.documentElement.lang=code;loadPack(code,function(){render(false);});return;}
 /* Product Vision s.9: a language switch clears the screen and re-asks the current step in the new language */
 S.busy=true;api('POST','/v1/chat/sessions/'+S.sid+'/messages',{text:'language'}).then(function(r1){/* send the list number, not the code: 'hi' would be read as a greeting */var o=r1.ok&&(r1.data.reply.options||[]).filter(function(x){return x.code===code;})[0];return api('POST','/v1/chat/sessions/'+S.sid+'/messages',{text:o?o.id:code});}).then(function(res){S.busy=false;
  if(!res.ok){toast(t('netErr'));return;}var r=res.data.reply;loadPack(r.language||code,function(){S.lang=code;document.documentElement.lang=code;S.msgs=[];
  if(S.res||S.scr!=='chat'){S.reply=r;if(r.language)S.lang=r.language;if(S.res)loadResults(function(){render(false);});if(S.scr==='details'&&S.detId)openDetailRefresh();else render(false);if(S.scr==='chat')handleReply(r);}
  else handleReply(r);});});};
function openDetailRefresh(){var id=S.detId;api('GET','/v1/companion/sessions/'+S.sid+'/schemes/'+encodeURIComponent(id)).then(function(r){if(r.ok){S.det=r.data;render(false);}});}
SHEETS.menu=function(){var rows=[['restart','restart',ic('back',20,'#008069')],['language','openLang',ic('chat',20,'#008069')]];if(S.me)rows.push(['myTitle','goMy',ic('starF',20,'#008069')]);rows.push(['feedback','openFb',ic('smile',20,'#008069')],['referTitle','openRefer',ic('people',20,'#008069')]);
 return shHead(t('menuTitle'))+'<div class="menu-list">'+rows.map(function(r){return '<button class="linkrow" data-a="'+r[1]+'">'+r[2]+t(r[0])+'<span class="go">'+ic('chevron',20,'#AEBAC1')+'</span></button>';}).join('')+
  '<a class="linkrow" href="/companion/classic" style="text-decoration:none">'+ic('list',20,'#8696A0')+t('classic')+'</a></div><div class="safety" style="margin:10px 0 0">'+ic('shield',16,'#8A6A00')+'<span>'+t('neverPayShort')+'</span></div>';};
ACT.openMenu=function(){openSheet('menu');};
ACT.restart=function(){closeSheetNow();S.res=null;S.checks={};S.det=null;S.refer=null;S.hist=[];if(S.scr!=='chat'){S.scr='chat';render('pop');}sendText('restart',null,{clear:true});};
ACT.back=function(){back();};
/* ---------- mic (STT) ---------- */
function micTap(){var sp=S.cfg&&S.cfg.speech;if(!sp||!sp.stt||!navigator.mediaDevices||typeof MediaRecorder==='undefined'){toast(t('micSoon'));ev('mic',null,{available:false});return;}
 if(S.rec){try{S.rec.stop();}catch(e){}return;}
 navigator.mediaDevices.getUserMedia({audio:true}).then(function(stream){var chunks=[],mr=new MediaRecorder(stream);S.rec=mr;toast(t('micListening'));refresh(true);
  var timer=setTimeout(function(){try{mr.stop();}catch(e){}},10000);
  mr.ondataavailable=function(e){if(e.data&&e.data.size)chunks.push(e.data);};
  mr.onstop=function(){clearTimeout(timer);stream.getTracks().forEach(function(tr){tr.stop();});S.rec=null;refresh(true);var blob=new Blob(chunks,{type:mr.mimeType||'audio/webm'});
   var fd=new FormData();fd.append('file',blob,'voice.webm');fd.append('lang',S.lang);
   api('POST','/v1/speech/stt',fd,{quiet:1}).then(function(r){if(r.ok&&r.data.text){ev('mic',null,{available:true});typed(r.data.text);}else toast(t('micFail'));});};
  mr.start();},function(){toast(t('micFail'));});}
/* ---------- boot ---------- */
function params(){var q={};location.search.replace(/^\?/,'').split('&').forEach(function(kv){if(!kv)return;var p=kv.split('=');q[decodeURIComponent(p[0])]=decodeURIComponent((p[1]||'').replace(/\+/g,' '));});return q;}
function entryOf(q){var e={};['src','om','r','ref','utm_source','utm_medium','utm_campaign','utm_content','utm_term'].forEach(function(k){if(q[k])e[k]=q[k];});return e;}
function cleanUrl(){try{history.replaceState(null,'',location.pathname);}catch(e){}}
function start(q){var lang=/^(en|hi|bn|as|kn|ta|te|ml|or|bho|mai|gu|mr|pa)$/.test(q.lang||'')?q.lang:undefined;
 api('POST','/v1/chat/sessions',{entry:entryOf(q),language:lang}).then(function(r){if(!r.ok){sys(t('netErr'));return;}S.sid=r.data.session_id;S.tok=r.data.session_token;saveSess();ev('web_opened',null,{src:q.src||'organic'});handleReply(r.data.reply);});}
function resume(sid,tok,q){S.sid=sid;S.tok=tok;api('GET','/v1/chat/sessions/'+sid).then(function(r){if(!r.ok||!r.data.last_reply){S.sid=S.tok=null;start(q);return;}saveSess();handleReply(r.data.last_reply);});}
function boot(){var b=document.body;
 b.innerHTML='<div class="stage"><div class="phone" id="phone"><div class="vp" id="vp"></div><div class="ovl" id="ovl"></div></div></div>';
 var p=$('#phone');
 p.addEventListener('click',function(e){var el=e.target.closest('[data-a]');if(!el||el.disabled)return;var a=el.dataset.a;if(!ACT[a])return;e.preventDefault();ACT[a](el.dataset.v,el);});
 p.addEventListener('submit',function(e){var f=e.target.closest('[data-f]');if(!f)return;e.preventDefault();var ci=$('#ci',f),v=(ci&&ci.value||'').trim();if(!v){micTap();return;}if(S.busy)return;ci.value='';S.stateQ='';typed(v);});
 p.addEventListener('input',function(e){var el=e.target;if(el.id==='ph'&&S.sd){S.sd.phone=el.value;return;}if(el.id==='fbc'&&S.sd){S.sd.comment=el.value;return;}if(el.id!=='ci')return;var sb=$('#sendb');if(sb)sb.innerHTML=ic(el.value.trim()?'send':'mic',22,'#fff');
  if(askKey()==='state'){S.stateQ=el.value;var old=$('#tray'),d=document.createElement('div');d.innerHTML=trayHTML();var n=d.firstChild;if(old&&n){n.classList.add('static');old.replaceWith(n);}else if(old)old.remove();}});
 p.addEventListener('change',function(e){var el=e.target;if(!el.dataset||!el.dataset.c||!el.value)return;var body=el.dataset.c==='lastdate'?{last_date:el.value}:{renewal_date:el.value};patchSaved(el.dataset.v,body,t('dateSaved'));});
 p.addEventListener('keydown',function(e){if(e.key==='Enter'&&e.target.id==='ph'){e.preventDefault();if(S.sd.step==='parent')ACT.parentNext();else ACT.phNext();}});
 document.addEventListener('keydown',function(e){if(e.key==='Escape'&&(S.sheet||S.dialog)){if(S.dialog)ACT.dlgCancel();else closeSheet();}});
 render(false);
 try{S.stTok=localStorage.getItem(LS_ST);}catch(e){}
 var q=params();
 api('GET','/v1/companion/config',undefined,{quiet:1}).then(function(r){if(r.ok){S.cfg=r.data;render(false);}});
 loadMe(function(){if(S.scr!=='chat')render(false);});
 if(q.c){cleanUrl();api('POST','/v1/companion/open',{code:q.c,entry:entryOf(q)}).then(function(r){if(!r.ok){start(q);return;}var d=r.data;S.sid=d.session_id;S.tok=d.session_token;saveSess();
   if(d.phone_masked)S.linked=d.phone_masked;if(d.student_token)setStudent(d.student_token);if(!d.linked)push({who:'sys',raw:t('linkUsed')});
   if(d.screen==='my'&&d.student_token){loadMe(function(){handleReply(d.reply);go('my','push');});return;}handleReply(d.reply);});return;}
 if(q.session&&q.token){cleanUrl();resume(q.session,q.token,q);return;}
 var ss=null;try{ss=JSON.parse(sessionStorage.getItem(SS_SESS)||'null');}catch(e){}
 if(ss&&ss.sid&&ss.tok&&!q.src&&!q.ref&&!q.om){resume(ss.sid,ss.tok,q);return;}
 if(q.src||q.ref||q.om)cleanUrl();
 start(q);}
window.P2={get S(){return S;},ACT:ACT};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();

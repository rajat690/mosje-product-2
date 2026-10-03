/* ===== inline SVG icons ===== */
var IC={
 back:'<path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20z"/>',
 close:'<path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>',
 send:'<path d="M3.4 20.4L21 12 3.4 3.6v6.6L15 12 3.4 13.8z"/>',
 mic:'<path d="M12 14a3 3 0 003-3V5a3 3 0 00-6 0v6a3 3 0 003 3zm5.3-3a5.3 5.3 0 01-10.6 0H5a7 7 0 006 6.9V21h2v-3.1a7 7 0 006-6.9z"/>',
 check:'<path d="M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z"/>',
 edit:'<path d="M3 17.25V21h3.75L17.8 9.94l-3.75-3.75zM20.7 7.04a1 1 0 000-1.41l-2.34-2.34a1 1 0 00-1.41 0l-1.83 1.83 3.75 3.75z"/>',
 star:'<path d="M22 9.24l-7.19-.62L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.63-7.03zM12 15.4l-3.76 2.27 1-4.28-3.32-2.88 4.38-.38L12 6.1l1.71 4.04 4.38.38-3.32 2.88 1 4.28z"/>',
 starF:'<path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/>',
 bell:'<path d="M12 22a2 2 0 002-2h-4a2 2 0 002 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4a1.5 1.5 0 00-3 0v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1z"/>',
 lock:'<path d="M18 8h-1V6A5 5 0 007 6v2H6a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V10a2 2 0 00-2-2zm-6 9a2 2 0 110-4 2 2 0 010 4zm3.1-9H8.9V6a3.1 3.1 0 016.2 0z"/>',
 dots:'<path d="M12 8a2 2 0 100-4 2 2 0 000 4zm0 2a2 2 0 100 4 2 2 0 000-4zm0 6a2 2 0 100 4 2 2 0 000-4z"/>',
 share:'<path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7a2.7 2.7 0 000-1.39l7.05-4.11A3 3 0 1015 5c0 .24.04.47.09.7L8.04 9.81a3 3 0 100 4.38l7.12 4.16c-.05.21-.08.43-.08.65A2.92 2.92 0 1018 16.08z"/>',
 ext:'<path d="M19 19H5V5h7V3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7h-2zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3z"/>',
 list:'<path d="M3 13h2v-2H3zm0 4h2v-2H3zm0-8h2V7H3zm4 4h14v-2H7zm0 4h14v-2H7zM7 7v2h14V7z"/>',
 doc:'<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zm-1 7V3.5L18.5 9z"/>',
 clock:'<path d="M12 2a10 10 0 100 20 10 10 0 000-20zm1 11h-5v-2h3V6h2z"/>',
 info:'<path d="M11 7h2v6h-2zm0 8h2v2h-2zM12 2a10 10 0 100 20 10 10 0 000-20z" fill-rule="evenodd"/>',
 shield:'<path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9z"/>',
 speaker:'<path d="M3 9v6h4l5 5V4L7 9zm13.5 3A4.5 4.5 0 0014 8v8a4.5 4.5 0 002.5-4zM14 3.2v2.1a7 7 0 010 13.4v2.1a9 9 0 000-17.6z"/>',
 people:'<path d="M16 11a3 3 0 100-6 3 3 0 000 6zm-8 0a3 3 0 100-6 3 3 0 000 6zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5C15 14.17 10.33 13 8 13zm8 0c-.29 0-.62.02-.97.05A4.2 4.2 0 0117 16.5V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>',
 home:'<path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/>',
 chevron:'<path d="M9 6l6 6-6 6-1.4-1.4L12.2 12 7.6 7.4z"/>',
 chevD:'<path d="M7 10l5 5 5-5z"/>',
 cam:'<path d="M12 15.2a3.2 3.2 0 100-6.4 3.2 3.2 0 000 6.4zM9 2L7.17 4H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V6a2 2 0 00-2-2h-3.17L15 2z"/>',
 attach:'<path d="M16.5 6v11.5a4 4 0 01-8 0V5a2.5 2.5 0 015 0v10.5a1 1 0 01-2 0V6H10v9.5a2.5 2.5 0 005 0V5a4 4 0 00-8 0v12.5a5.5 5.5 0 0011 0V6z"/>',
 smile:'<path d="M12 2a10 10 0 100 20 10 10 0 000-20zm-3.5 6a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm7 0a1.5 1.5 0 110 3 1.5 1.5 0 010-3zM12 17.5a5.5 5.5 0 01-5.11-3.5h10.22A5.5 5.5 0 0112 17.5z"/>',
 call:'<path d="M6.6 10.8a15.1 15.1 0 006.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1A17 17 0 013 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1z"/>',
 trash:'<path d="M6 19a2 2 0 002 2h8a2 2 0 002-2V7H6zM19 4h-3.5l-1-1h-5l-1 1H5v2h14z"/>',
 chat:'<path d="M20 2H4a2 2 0 00-2 2v18l4-4h14a2 2 0 002-2V4a2 2 0 00-2-2z"/>',
 sparkle:'<path d="M19 9l1.25-2.75L23 5l-2.75-1.25L19 1l-1.25 2.75L15 5l2.75 1.25zm-7.5.5L9 4 6.5 9.5 1 12l5.5 2.5L9 20l2.5-5.5L17 12zM19 15l-1.25 2.75L15 19l2.75 1.25L19 23l1.25-2.75L23 19l-2.75-1.25z"/>',
 qr:'<path d="M3 11h8V3H3zm2-6h4v4H5zM3 21h8v-8H3zm2-6h4v4H5zM13 3v8h8V3zm6 6h-4V5h4zM19 19h2v2h-2zM13 13h2v2h-2zM15 15h2v2h-2zM13 17h2v2h-2zM15 19h2v2h-2zM17 17h2v2h-2zM17 13h2v2h-2zM19 15h2v2h-2z"/>'
};
function ic(n,s,c,extra){return '<svg width="'+(s||20)+'" height="'+(s||20)+'" viewBox="0 0 24 24" fill="'+(c||'currentColor')+'" aria-hidden="true"'+(extra||'')+'>'+IC[n]+'</svg>';}
var TICKS='<svg width="16" height="11" viewBox="0 0 16 11" fill="#53BDEB" aria-hidden="true"><path d="M11.07.66L4.6 7.12 2.1 4.62 1 5.72l3.6 3.6 7.57-7.56zM15 .66L8.53 7.12l-.7-.7-1.1 1.1 1.8 1.8L16.1 1.76z"/></svg>';
var WALOGO=function(s,bg,fg){return '<svg width="'+s+'" height="'+s+'" viewBox="0 0 24 24" aria-hidden="true"><path fill="'+(bg||'#25D366')+'" d="M12 2a10 10 0 00-8.6 15.1L2 22l5-1.3A10 10 0 1012 2z"/><path fill="'+(fg||'#fff')+'" d="M16.9 14.4c-.3-.1-1.6-.8-1.8-.9-.3-.1-.4-.1-.6.1l-.8 1c-.2.2-.3.2-.6.1a6.6 6.6 0 01-3.3-2.9c-.2-.4.2-.4.7-1.3.1-.2 0-.3 0-.4l-.8-2c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 00-.7.3 3 3 0 00-.9 2.2 5.2 5.2 0 001.1 2.7 11.8 11.8 0 004.5 4c1.7.7 2.3.8 3.2.6.5-.1 1.6-.6 1.8-1.3.2-.6.2-1.1.2-1.3-.1-.1-.3-.2-.6-.4z"/></svg>';};
var LOGO=function(s){return '<svg width="'+(s||26)+'" height="'+(s||26)+'" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3L1 9l11 6 9-4.9V17h2V9z" fill="#008069"/><path d="M5 13.2v4L12 21l7-3.8v-4L12 17z" fill="#25D366"/></svg>';};
var VERIFIED='<svg width="16" height="16" viewBox="0 0 24 24" aria-label="verified"><path d="M12 1l2.6 2.2 3.4-.4.9 3.3 3 1.7-1.3 3.2 1.3 3.2-3 1.7-.9 3.3-3.4-.4L12 23l-2.6-2.2-3.4.4-.9-3.3-3-1.7L3.4 13 2.1 9.8l3-1.7.9-3.3 3.4.4z" fill="#25D366"/><path d="M8 12.3l2.6 2.6L16.2 9" stroke="#fff" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
/* scheme tile icons (stroke) */
var TILE={
 cap:['#FFF4D6','#B57A00','<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11v5c3.5 2.5 8.5 2.5 12 0v-5"/><path d="M22 9v6"/>'],
 home:['#E6F4FF','#1769C2','<path d="M4 21V9l8-6 8 6v12"/><path d="M9 21v-6h6v6"/>'],
 medal:['#E3F6EF','#008069','<circle cx="12" cy="9" r="6"/><path d="M8.5 14L7 22l5-3 5 3-1.5-8"/><path d="M10 9l1.5 1.5L14.5 7.5"/>'],
 star:['#F1E8FF','#7B3FE4','<path d="M12 2l3 6.3 6.9.9-5 4.8 1.2 6.9L12 17.6 5.9 20.9 7.1 14l-5-4.8 6.9-.9z"/>'],
 trophy:['#FFEFD9','#C26A00','<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 01-10 0z"/><path d="M17 5h3v2a3 3 0 01-3 3M7 5H4v2a3 3 0 003 3"/>'],
 food:['#FDE8EF','#C2185B','<path d="M7 2v8a2 2 0 002 2v10M11 2v6M3 2v6a4 4 0 004 4"/><path d="M17 22V2c-2.5 1.5-4 4.5-4 8h4"/>'],
 book:['#E8EEFF','#3F51B5','<path d="M4 19.5A2.5 2.5 0 016.5 17H20V3H6.5A2.5 2.5 0 004 5.5z"/><path d="M4 19.5A2.5 2.5 0 006.5 22H20v-5"/>']
};
function tile(k,s){var t=TILE[k]||TILE.cap;s=s||42;return '<span class="ic" style="width:'+s+'px;height:'+s+'px;background:'+t[0]+'"><svg width="'+Math.round(s*.56)+'" height="'+Math.round(s*.56)+'" viewBox="0 0 24 24" fill="none" stroke="'+t[1]+'" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+t[2]+'</svg></span>';}
var SBAR_IC='<span class="ic"><svg width="15" height="11" viewBox="0 0 15 11" fill="currentColor"><path d="M1 10h2V7H1zm4 0h2V5H5zm4 0h2V3H9zm4 0h2V1h-2z"/></svg><svg width="14" height="11" viewBox="0 0 14 11" fill="currentColor"><path d="M7 10.5L.3 3.6a9.6 9.6 0 0113.4 0z"/></svg><svg width="22" height="11" viewBox="0 0 22 11"><rect x=".5" y=".5" width="18" height="10" rx="2.5" fill="none" stroke="currentColor"/><rect x="2" y="2" width="12" height="7" rx="1.2" fill="currentColor"/><rect x="19.5" y="3.5" width="2" height="4" rx="1" fill="currentColor"/></svg></span>';

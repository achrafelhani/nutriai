const Nutri={
 token:localStorage.getItem('token'), profile:null,
 headers(json=true){const h={Authorization:`Bearer ${this.token}`};if(json)h['Content-Type']='application/json';return h},
 async api(url,opts={}){opts.headers={...this.headers(!(opts.body instanceof FormData)),...(opts.headers||{})};const r=await fetch(url,opts);let d={};try{d=await r.json()}catch(e){}if(r.status===401){localStorage.removeItem('token');location.href='/login';throw new Error('Session expirée')}if(!r.ok)throw new Error(d.error||'Une erreur est survenue');return d},
 toast(msg){const host=document.getElementById('toasts');if(!host)return;const t=document.createElement('div');t.className='toast';t.textContent=msg;host.appendChild(t);setTimeout(()=>t.remove(),3200)},
 logout(){localStorage.removeItem('token');localStorage.removeItem('username');location.href='/'},
 toggleMenu(){document.getElementById('sidebar')?.classList.toggle('open')},
 pct(v,max){return max?Math.max(0,Math.min(100,(Number(v||0)/Number(max))*100)):0},
 async init(){if(!this.token){location.href='/login';return}document.getElementById('dateLabel').textContent=new Intl.DateTimeFormat('fr-FR',{weekday:'long',day:'numeric',month:'long'}).format(new Date());try{this.profile=await this.api('/auth/profile');const n=this.profile.username||'NutriAI';document.getElementById('sidebarName').textContent=n;document.getElementById('avatar').textContent=n[0].toUpperCase();document.getElementById('sidebarGoal').textContent=this.goalLabel(this.profile.goal)}catch(e){}try{const s=await this.api('/meals/streak');document.getElementById('streakTop').textContent=s.streak}catch(e){}this.bindSearch()},
 goalLabel(g){return({perte:'Perte de poids',muscle:'Prise de masse',maintien:'Maintien',sante:'Santé'})[g]||'Profil nutritionnel'},
 bindSearch(){const q=document.getElementById('globalSearch');q?.addEventListener('keydown',e=>{if(e.key==='Enter'){const v=q.value.toLowerCase();if(v.includes('repas'))location.href='/repas';else if(v.includes('progress'))location.href='/progression';else if(v.includes('coach')||v.includes('ia'))location.href='/coach';else if(v.includes('objectif'))location.href='/objectifs';else if(v.includes('profil')||v.includes('param'))location.href='/profil';else this.toast('Essayez : repas, progression, coach, objectifs ou profil.')}})},
 modal(html){const b=document.getElementById('modalBackdrop');document.getElementById('modal').innerHTML=html;b.classList.add('open')},closeModal(){document.getElementById('modalBackdrop')?.classList.remove('open')}
};
document.addEventListener('DOMContentLoaded',()=>Nutri.init());document.getElementById('modalBackdrop')?.addEventListener('click',e=>{if(e.target.id==='modalBackdrop')Nutri.closeModal()});

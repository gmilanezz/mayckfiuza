const API = "/api";
let token = localStorage.token,
  user = JSON.parse(localStorage.user || "null"),
  tab = "agenda";
const $ = (s) => document.querySelector(s),
  headers = () => ({
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  });
async function req(p, o = {}) {
  let r = await fetch(API + p, {
    ...o,
    headers: { ...headers(), ...(o.headers || {}) },
  });
  let d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.detail || "Erro");
  return d;
}
const logo = () => `<img class="app-image brand-logo" src="/logo-mayck.png" alt="Mayck Fiuza Treinador">`;
const CONTACT = { instagram: localStorage.MAYCK_INSTAGRAM || "", whatsapp: localStorage.MAYCK_WHATSAPP || "" };
const WHATSAPP = (import.meta.env.VITE_MAYCK_WHATSAPP || CONTACT.whatsapp || "").trim();
function whatsappFloat() { const value = WHATSAPP.replace(/[^0-9]/g, ""); return value ? `<a class="whatsapp-float" href="https://wa.me/${value}" target="_blank" rel="noopener noreferrer" aria-label="Abrir WhatsApp">WhatsApp</a>` : ""; }
const safe = (value) => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;", "\"":"&quot;", "'":"&#39;"}[ch]));
let activeWorkoutTimer = null;
function login() {
  app.innerHTML = `<main class="auth"><section class="auth-card">${logo()}<div><h1 class="page-heading accent">Mayck Fiuza</h1><p class="text-paragraph muted">Agenda, treinos e evolução dos alunos.</p></div><form class="app-form" id="f"><label class="field">Usuário<input class="form-control" id="u" autocomplete="username" required></label><label class="field">Senha<input class="form-control" id="p" type="password" autocomplete="current-password" required></label><button class="ui-button btn wide">Entrar</button><button type="button" class="ui-button forgot-link" onclick="forgotPassword()">Esqueci minha senha</button><p id="err" class="text-paragraph error"></p></form><div class="auth-divider"><span>Primeiro acesso?</span></div><div class="auth-actions"><button class="ui-button btn ghost" onclick="register('student')">Criar conta de aluno</button></div></section></main>`;
  f.onsubmit = async (e) => {
    e.preventDefault();
    let body = new URLSearchParams({ username: u.value, password: p.value });
    let r = await fetch(API + "/login", { method: "POST", body });
    if (!r.ok) {
      err.textContent = "Usuário ou senha inválidos";
      return;
    }
    saveSession(await r.json());
  };
}
function forgotPassword() {
  app.innerHTML = `<main class="auth"><section class="auth-card">${logo()}<button class="ui-button text-btn" onclick="login()">Voltar ao login</button><div><h1 class="page-heading">Redefinir senha</h1><p class="text-paragraph muted">Informe seu usuário, o código Mayck e escolha uma nova senha.</p></div><form class="app-form" id="resetf"><label class="field">Usuário<input class="form-control" id="resetUser" autocomplete="username" required></label><label class="field">Código Mayck<input id="resetCode" maxlength="5" minlength="5" pattern="[A-Za-z0-9]{5}" class="form-control code-input" placeholder="A1B2C" required></label><label class="field">Nova senha<input class="form-control" id="resetPass" type="password" minlength="5" autocomplete="new-password" required></label><label class="field">Confirmar nova senha<input class="form-control" id="resetConfirm" type="password" minlength="5" autocomplete="new-password" required></label><button class="ui-button btn wide">Redefinir senha</button><p id="resetErr" class="text-paragraph error"></p><p id="resetOk" class="text-paragraph success"></p></form></section></main>`;
  resetf.onsubmit = async (e) => {
    e.preventDefault();
    resetErr.textContent = "";
    resetOk.textContent = "";
    if (resetPass.value !== resetConfirm.value) {
      resetErr.textContent = "As senhas não coincidem.";
      return;
    }
    try {
      let r = await fetch(API + "/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: resetUser.value,
          invite_code: resetCode.value,
          new_password: resetPass.value,
        }),
      });
      let d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || "Não foi possível redefinir a senha");
      resetOk.textContent = "Senha redefinida. Redirecionando para o login...";
      setTimeout(login, 1200);
    } catch (e) {
      resetErr.textContent = e.message;
    }
  };
}

async function register(role) {
  role = "student";
  let professors = [];
  if (role === "student")
    professors = await fetch(API + "/public/professors").then((r) => r.json());
  app.innerHTML = `<main class="auth"><section class="auth-card">${logo()}<button class="ui-button text-btn" onclick="login()">Voltar ao login</button><div><h1 class="page-heading">${role === "professor" ? "Aluno" : "Aluno"}</h1><p class="text-paragraph muted">Use o código de 5 caracteres fornecido pelo Mayck.</p></div><form class="app-form" id="rf"><label class="field">Nome completo<input class="form-control" id="rn" required></label><label class="field">Usuário<input class="form-control" id="ru" required></label>${role === "student" ? `<label class="field">Professor<select class="form-select" id="rp" required><option value="">Selecione</option>${professors.map((x) => `<option value="${x.id}">${x.name}</option>`).join("")}</select></label>` : ""}<label class="field">Senha<input class="form-control" id="rpass" type="password" minlength="5" required></label><label class="field">Código Mayck<input id="rcode" maxlength="5" minlength="5" pattern="[A-Za-z0-9]{5}" class="form-control code-input" placeholder="A1B2C" required></label><button class="ui-button btn wide">Criar conta</button><p id="rerr" class="text-paragraph error"></p></form></section></main>`;
  rf.onsubmit = async (e) => {
    e.preventDefault();
    try {
      let d = await fetch(API + "/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: rn.value,
          username: ru.value,
          password: rpass.value,
          role,
          invite_code: rcode.value,
          professor_id: role === "student" ? +rp.value : null,
        }),
      }).then(async (r) => {
        let d = await r.json();
        if (!r.ok) throw Error(d.detail || "Não foi possível criar a conta");
        return d;
      });
      saveSession(d);
    } catch (e) {
      rerr.textContent = e.message;
    }
  };
}
function saveSession(d) {
  token = d.access_token;
  user = d.user;
  localStorage.token = token;
  localStorage.user = JSON.stringify(user);
  tab = user.role === "student" ? "treino" : "agenda";
  render();
}
function menuItems() {
  return user.role === "student"
    ? [["treino","⌁","Meu treino"],["evolucao","↗","Evolução"],["contato","@","Contato"]]
    : [["agenda","▦","Aulas do dia"],["alunos","◎","Alunos"],["pagamentos","$","Pagamentos"],["fotos","▣","Fotos dos alunos"],["contato","@","Contato"]];
}
function nav() {
  return `<header class="topbar"><div class="brand-inline nav-logo-only">${logo()}</div><button class="ui-button menu-button" onclick="toggleMenu(true)" aria-label="Abrir menu"><span class="hamburger-icon" aria-hidden="true"><span class="hamburger-line hamburger-line-top"></span><span class="hamburger-line hamburger-line-middle"></span><span class="hamburger-line hamburger-line-bottom"></span></span></button><div class="user-chip"><div><b class="user-name">${user.name}</b><span class="user-role">${user.role}</span></div></div></header><div class="menu-overlay" onclick="toggleMenu(false)"></div><aside class="sidebar"><div class="sidebar-head">${logo()}<button class="ui-button menu-close" onclick="toggleMenu(false)">×</button></div><div class="profile"><b class="profile-name">${user.name}</b><span class="profile-role">${user.role === "student" ? "Aluno" : "Professor"}</span></div><nav class="side-nav">${menuItems().map(x=>`<button class="ui-button side-link ${tab===x[0]?"active":""}" onclick="setTab('${x[0]}')"><i class="side-icon">${x[1]}</i><span class="side-label">${x[2]}</span></button>`).join("")}</nav><button class="ui-button side-link logout" onclick="logout()"><i class="side-icon">↪</i><span class="side-label">Sair</span></button></aside>`;
}
function setTab(nextTab) {
  tab = nextTab;
  toggleMenu(false);
  render();
}

function toggleMenu(open) {
  document.body.classList.toggle("menu-open", open);
}
async function render() {
  if (!token) return login();
  app.innerHTML = `${nav()}${whatsappFloat()}<main class="shell"><div class="page-title"><h1 class="page-heading">${menuItems().find((x) => x[0] === tab)?.[2] || "Painel"}</h1></div><div id="view"></div></main>`;
  try {
    if (tab === "contato") return contato();
    if (user.role === "student") return tab === "evolucao" ? evolucao() : treino();
    if (tab === "alunos") return alunos();
    if (tab === "pagamentos") return pagamentos();
    if (tab === "fotos") return fotosAlunos();
    return agenda(false);
  } catch (e) {
    view.innerHTML = `<div class="card error">${e.message}</div>`;
  }
}
async function agenda() {
  const [data, students] = await Promise.all([req("/lessons"), req("/students")]);
  const days = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
  view.innerHTML = `<div class="grid"><section class="card"><h2 class="section-heading">Nova aula</h2><form class="app-form" id="lf"><label class="field">Aluno cadastrado<select class="form-select" id="lessonStudent" required><option value="">Selecione um aluno</option>${students.map(s=>`<option value="${s.id}">${safe(s.name)}</option>`).join("")}</select></label><label class="field">Dia<select class="form-select" id="day">${["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"].map((d,i)=>`<option value="${i}">${d}</option>`).join("")}</select></label><label class="field">Horário<input class="form-control" id="time" type="time" required></label><button class="ui-button btn">Salvar aula</button></form></section><section class="card"><h2 class="section-heading">Aulas pendentes</h2><div class="list">${data.filter(x=>x.status==='pending').map(x=>`<div class="row"><div><b class="row-title">${safe(x.student)}</b><div class="muted">${days[x.weekday]} ${safe(x.time)}</div></div><div class="row-actions"><button class="ui-button btn action compact" title="Marcar como concluída" aria-label="Concluir aula de ${safe(x.student)}" onclick="finishLesson(${x.id})">✓</button><button class="ui-button btn action compact" onclick="delLesson(${x.id})">Excluir</button></div></div>`).join("") || '<div class="empty">Nenhuma aula pendente.</div>'}</div></section></div>`;
  document.querySelector('#lf').addEventListener('submit',async e=>{
    e.preventDefault();
    const student = students.find(s=>s.id===Number(document.querySelector('#lessonStudent').value));
    if(!student) return alert('Selecione um aluno cadastrado.');
    try {await req('/lessons',{method:'POST',body:JSON.stringify({student_id:student.id,student_name:student.name,weekday:Number(document.querySelector('#day').value),time:document.querySelector('#time').value})});await render();}
    catch(err){alert(err.message);}
  });
}
async function finishLesson(id) {
  try {await req('/lessons/'+id+'/status?status=completed',{method:'PATCH'});await render();}
  catch(err){alert(err.message);}
}
async function delLesson(id) {
  if(!confirm('Cancelar esta aula? Ela continuará no histórico como cancelada.')) return;
  try {await req('/lessons/'+id,{method:'DELETE'});await render();}
  catch(err){alert(err.message);}
}
const lessonCalendarState = { studentId: null, year: new Date().getFullYear(), month: new Date().getMonth(), lessons: [], name: '' };
function calendarDate(value) {
  if (!value) return null;
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
  return match ? `${match[1]}-${match[2]}-${match[3]}` : null;
}
function drawStudentLessonCalendar() {
  const state = lessonCalendarState;
  const editor = document.querySelector('#editor');
  if (!editor) return;
  const {year, month, lessons} = state;
  const firstDay = (new Date(year, month, 1).getDay() + 6) % 7;
  const count = new Date(year, month + 1, 0).getDate();
  const label = new Intl.DateTimeFormat('pt-BR', {month:'long', year:'numeric'}).format(new Date(year, month, 1));
  let cells = Array.from({length:firstDay}, () => '<div class="lesson-calendar-blank" aria-hidden="true"></div>');
  for (let day = 1; day <= count; day++) {
    const date = `${year}-${String(month+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
    const weekday = (new Date(year, month, day).getDay()+6)%7;
    const events = lessons.filter(x => {
      if (x.status === 'completed') return calendarDate(x.completed_at) === date;
      if (x.status === 'cancelled') return calendarDate(x.cancelled_at) === date;
      return x.weekday === weekday; // Aula semanal pendente: previsão, não presença confirmada.
    });
    const dots = events.map(x => {
      const kind = x.status === 'completed' ? 'lesson-done' : x.status === 'cancelled' ? 'lesson-cancelled' : 'lesson-pending';
      const status = x.status === 'completed' ? 'Concluída' : x.status === 'cancelled' ? 'Cancelada' : 'Prevista';
      return `<span class="lesson-dot ${kind}" title="${status} — ${safe(x.time)}" aria-label="${status} às ${safe(x.time)}"></span>`;
    }).join('');
    const today = new Date();
    const isToday = today.getFullYear()===year && today.getMonth()===month && today.getDate()===day;
    cells.push(`<div class="lesson-calendar-day ${isToday?'is-today':''}" aria-label="Dia ${day}, ${events.length} aulas"><span class="lesson-calendar-number">${day}</span><div class="lesson-calendar-dots">${dots}</div></div>`);
  }
  editor.innerHTML = `<section class="card editor"><h2 class="section-heading">Aulas de ${safe(state.name)}</h2><div class="lesson-calendar-nav"><button class="ui-button btn action compact" onclick="changeStudentLessonMonth(-1)" aria-label="Mês anterior">‹</button><strong>${safe(label)}</strong><button class="ui-button btn action compact" onclick="changeStudentLessonMonth(1)" aria-label="Próximo mês">›</button></div><div class="lesson-calendar-grid">${['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'].map(d=>`<div class="lesson-calendar-weekday">${d}</div>`).join('')}${cells.join('')}</div><div class="lesson-calendar-legend"><span><i class="lesson-dot lesson-done"></i> Concluída</span><span><i class="lesson-dot lesson-pending"></i> Prevista / não concluída</span><span><i class="lesson-dot lesson-cancelled"></i> Cancelada</span></div><p class="muted lesson-calendar-note">Aulas pendentes são exibidas semanalmente no dia programado. Aulas concluídas e canceladas aparecem na data em que foram marcadas. O cadastro atual não registra uma data específica para cada ocorrência.</p></section>`;
}
function changeStudentLessonMonth(offset) {
  const next = new Date(lessonCalendarState.year, lessonCalendarState.month + offset, 1);
  lessonCalendarState.year = next.getFullYear();
  lessonCalendarState.month = next.getMonth();
  drawStudentLessonCalendar();
}
async function studentLessons(id) {
  try {
    const [lessons, students] = await Promise.all([req('/students/'+id+'/lessons'),req('/students')]);
    lessonCalendarState.studentId = id;
    lessonCalendarState.lessons = lessons;
    lessonCalendarState.name = students.find(s=>s.id===id)?.name || 'Aluno';
    const now = new Date();
    lessonCalendarState.year = now.getFullYear();
    lessonCalendarState.month = now.getMonth();
    drawStudentLessonCalendar();
  } catch(err) {alert(err.message);}
}
async function alunos() {
  let ss = await req("/students");
  view.innerHTML = `<div class="grid"><section class="card"><div class="section-head"><h2 class="section-heading">Adicionar aluno</h2></div><p class="text-paragraph muted">O aluno também pode criar a própria conta usando o código Mayck e selecionar você como professor.</p><form class="app-form" id="sf"><label class="field">Nome<input class="form-control" id="sn" required></label><label class="field">Usuário<input class="form-control" id="su" required></label><label class="field">Senha inicial<input class="form-control" id="sp" minlength="5" required></label><button class="ui-button btn">Cadastrar diretamente</button></form></section><section class="card"><h2 class="section-heading">Meus alunos</h2><div class="list">${ss.map((s) => `<div class="row"><div><b class="row-title">${s.name}</b><div class="muted">@${s.username}</div></div><div class="row-actions"><button class="ui-button btn action compact" onclick="workout(${s.id},'${s.name.replaceAll("'", "")}')">Treino</button><button class="ui-button btn action compact" onclick="openStudentPhotos(${s.id})">Fotos</button><button class="ui-button btn action compact" onclick="studentLessons(${s.id})">Aulas</button></div></div>`).join("") || '<span class="empty">Nenhum aluno.</span>'}</div></section></div><div id="editor"></div>`;
  sf.onsubmit = async (e) => {
    e.preventDefault();
    await req("/students", {
      method: "POST",
      body: JSON.stringify({
        name: sn.value,
        username: su.value,
        password: sp.value,
      }),
    });
    render();
  };
}
function workout(id, name) {
  editor.innerHTML = `<section class="card editor"><div class="section-head"><h2 class="section-heading">Treino de <span class="accent">${name}</span></h2></div><form class="app-form" id="wf"><label class="field">Título<input class="form-control" id="wt" placeholder="Treino A — Inferiores" required></label><label class="field">Periodização<input class="form-control" id="wp" placeholder="Semanas 1–4 · força/hipertrofia"></label><label class="field">Planilha<textarea class="form-textarea" id="wc" placeholder="Agachamento — 4x10 — 90s\nLeg press — 4x12 — 60s" required></textarea></label><button class="ui-button btn">Publicar para o aluno</button></form></section>`;
  wf.onsubmit = async (e) => {
    e.preventDefault();
    await req("/workouts", {
      method: "POST",
      body: JSON.stringify({
        student_id: id,
        title: wt.value,
        periodization: wp.value,
        content: wc.value,
      }),
    });
    alert("Treino publicado no perfil do aluno.");
  };
}
async function treino() {
  let ws = await req("/workouts");
  view.innerHTML = `<div class="workout-links">${ws.map(w=>`<button class="ui-button workout-link" onclick="treinoDetalhe(${w.id})"><span class="workout-link-title">${w.title}</span><b class="workout-link-action">ABRIR →</b></button>`).join("") || '<section class="card empty">Seu professor ainda não publicou um treino.</section>'}</div>`;
}
async function treinoDetalhe(id) {
  let w = await req("/workouts/"+id);
  view.innerHTML = `<button class="ui-button text-btn back" onclick="treino()">Voltar - Meus treinos</button><section class="card workout-detail"><p class="workout-periodization">${w.periodization || "TREINO"}</p><h2 class="section-heading">${w.title}</h2><div class="workout-content">${w.content}</div><div id="timerBox" class="timer-box"><span class="timer-label">DURAÇÃO</span><strong id="timerText" class="timer-value">00:00:00</strong></div><div class="workout-actions"><button id="startWorkout" class="ui-button btn" type="button">Iniciar treino</button><button id="finishWorkout" class="ui-button btn action" type="button" disabled>Finalizar treino</button></div></section>`;
  const startButton = document.querySelector("#startWorkout");
  const finishButton = document.querySelector("#finishWorkout");
  startButton?.addEventListener("click", () => startWorkoutTimer(w.id, w.title));
  finishButton?.addEventListener("click", () => finishWorkoutTimer(w.id, w.title));
}
function startWorkoutTimer(id, title) {
  if (activeWorkoutTimer) clearInterval(activeWorkoutTimer.interval);
  const startButton = document.querySelector("#startWorkout");
  const finishButton = document.querySelector("#finishWorkout");
  const timerDisplay = document.querySelector("#timerText");
  if (!startButton || !finishButton || !timerDisplay) return;
  const started = Date.now(); activeWorkoutTimer = { id, title, started };
  startButton.disabled = true; finishButton.disabled = false; timerDisplay.textContent = "00:00:00";
  activeWorkoutTimer.interval = setInterval(() => { timerDisplay.textContent = formatDuration(Date.now() - started); }, 1000);
}
function formatDuration(ms){ let t=Math.floor(ms/1000),h=Math.floor(t/3600),m=Math.floor((t%3600)/60),s=t%60; return [h,m,s].map(v=>String(v).padStart(2,'0')).join(':'); }
async function finishWorkoutTimer(id,title){
  if(!activeWorkoutTimer || activeWorkoutTimer.id!==id) return;
  clearInterval(activeWorkoutTimer.interval); const duration=Date.now()-activeWorkoutTimer.started; activeWorkoutTimer=null;
  await req("/workouts/"+id+"/complete",{method:"POST"});
  await shareWorkoutCard(title,duration);
  const finishButton = document.querySelector("#finishWorkout");
  const startButton = document.querySelector("#startWorkout");
  if (finishButton) finishButton.disabled = true;
  if (startButton) startButton.disabled = false;
}
async function shareWorkoutCard(title,duration){
  const canvas=document.createElement('canvas'); canvas.width=1080; canvas.height=1920; const c=canvas.getContext('2d');
  c.fillStyle='#8b003f'; c.fillRect(0,0,1080,1920);
  try{ const img=new Image(); img.src='/logo-mayck.png'; await img.decode(); c.drawImage(img,240,180,600,600); }catch(e){}
  c.textAlign='center'; c.fillStyle='#fff5f2'; c.font='bold 54px Arial'; c.fillText('TREINO CONCLUÍDO',540,930);
  c.fillStyle='#fff5f2'; c.font='bold 78px Arial'; wrapCanvasText(c,title.toUpperCase(),540,1050,850,92);
  c.fillStyle='#fff5f2'; c.font='bold 36px Arial'; c.fillText('DURAÇÃO',540,1320);
  c.fillStyle='#fff5f2'; c.font='bold 110px Arial'; c.fillText(formatDuration(duration),540,1440);
  c.fillStyle='#fff5f2'; c.font='bold 38px Arial'; c.fillText('MAYCK FIUZA',540,1680);
  const blob=await new Promise(r=>canvas.toBlob(r,'image/png')); const file=new File([blob],'mayck-treino.png',{type:'image/png'});
  if(navigator.share && navigator.canShare?.({files:[file]})){ try{ await navigator.share({title:'Treino concluído',text:`${title} • ${formatDuration(duration)}`,files:[file]}); return; }catch(e){ if(e.name==='AbortError') return; } }
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='mayck-treino.png'; a.click(); URL.revokeObjectURL(a.href); alert('Card gerado. No celular, compartilhe a imagem no Instagram Stories.');
}
function wrapCanvasText(c,text,x,y,maxWidth,lineHeight){ const words=text.split(' '); let line='',lines=[]; for(const word of words){ const test=line?line+' '+word:word; if(c.measureText(test).width>maxWidth&&line){lines.push(line);line=word}else line=test} lines.push(line); lines.slice(0,3).forEach((l,i)=>c.fillText(l,x,y+i*lineHeight)); }
async function complete(id) {
  await req("/workouts/" + id + "/complete", { method: "POST" });
  alert("Treino concluído!");
}
async function optimizePhoto(file) {
  if (!file.type.startsWith("image/")) throw new Error("Selecione apenas arquivos de imagem.");

  const bitmap = await createImageBitmap(file);
  const maxSide = 1600;
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  const width = Math.max(1, Math.round(bitmap.width * scale));
  const height = Math.max(1, Math.round(bitmap.height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  canvas.getContext("2d").drawImage(bitmap, 0, 0, width, height);
  bitmap.close?.();

  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.82));
  if (!blob) throw new Error("Não foi possível preparar a foto para envio.");
  if (blob.size > 3.5 * 1024 * 1024) throw new Error("A foto ainda ficou muito grande após a otimização.");

  const baseName = (file.name || "foto").replace(/\.[^.]+$/, "");
  return new File([blob], `${baseName}.jpg`, { type: "image/jpeg" });
}

async function evolucao() {
  let w = await req("/weights/" + user.id),
    max = Math.max(...w.map((x) => x.value), 1);
  view.innerHTML = `<div class="grid"><section class="card"><div class="section-head"><h2 class="section-heading">Peso semanal</h2></div><form class="app-form" id="peso"><label class="field">Peso (kg)<input class="form-control" id="kg" type="number" step=".1" required></label><button class="ui-button btn">Registrar peso</button></form><div class="chart">${w.map((x) => `<div class="bar" style="height:${Math.max(12, (x.value / max) * 130)}px" title="${x.value} kg"><span class="bar-label">${String(x.measured_on).slice(5)}</span></div>`).join("")}</div></section><section class="card"><h2 class="section-heading">Foto de evolução</h2><p class="text-paragraph muted">Envie sua foto semanal. O arquivo fica vinculado exclusivamente à sua conta.</p><form class="app-form" id="photo"><label class="field">Imagens<input class="form-control" id="img" type="file" accept="image/*" multiple required></label><button class="ui-button btn">Enviar foto</button></form></section></div>`;
  peso.onsubmit = async (e) => {
    e.preventDefault();
    await req("/weights", {
      method: "POST",
      body: JSON.stringify({
        value: +kg.value,
        measured_on: new Date().toISOString().slice(0, 10),
      }),
    });
    render();
  };
  photo.onsubmit = async (e) => {
    e.preventDefault();
    const files = [...img.files];
    if (!files.length) return;

    const button = e.currentTarget.querySelector("button[type=submit], button");
    if (button) button.disabled = true;

    try {
      let sent = 0;
      for (const file of files) {
        const optimized = await optimizePhoto(file);
        const fd = new FormData();
        fd.append("files", optimized, optimized.name);

        const r = await fetch(API + "/photos", {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: fd,
        });

        if (!r.ok) {
          let detail = "Erro no envio da foto";
          try {
            const data = await r.json();
            if (data?.detail) detail = data.detail;
          } catch {}
          if (r.status === 413) detail = "A foto ficou grande demais para o servidor. Tente outra imagem.";
          throw new Error(detail);
        }
        sent++;
      }
      alert(`${sent} foto(s) enviada(s)`);
      render();
    } catch (err) {
      alert(err?.message || "Erro no envio da foto");
    } finally {
      if (button) button.disabled = false;
    }
  };
}
async function fotosAlunos(){
  const students=await req('/students');
  view.innerHTML=`<section class="card"><h2 class="section-heading">Fotos dos alunos</h2><p class="text-paragraph muted">Acesse o histórico de evolução enviado semanalmente por cada aluno.</p><div class="student-photo-list">${students.map(s=>`<button class="ui-button workout-link" onclick="openStudentPhotos(${s.id})"><span class="workout-link-title">${s.name}</span><b class="workout-link-action">VER FOTOS →</b></button>`).join('') || '<div class="empty">Nenhum aluno cadastrado.</div>'}</div></section><div id="photoGallery"></div>`;
}
async function openStudentPhotos(id) {
  if (tab !== "fotos") { tab = "fotos"; await render(); }
  const [photos, students] = await Promise.all([req("/photos/" + id), req("/students")]);
  const name = students.find((item) => item.id === id)?.name || "Aluno";
  const gallery = document.querySelector("#photoGallery");
  const base = API.replace(/\/api$/, "");
  const photoUrl = (path) => path.startsWith("data:") ? path : base + path;
  gallery.innerHTML = `<section class="card gallery-card"><button class="ui-button text-btn back" onclick="fotosAlunos()">← Todos os alunos</button><h2 class="section-heading">Fotos de ${name}</h2><div class="photo-grid">${photos.map((photo) => `<a class="app-link photo-link" href="${photoUrl(photo.path)}" target="_blank"><img class="app-image photo-image" src="${photoUrl(photo.path)}" alt="Evolução de ${name}"><span class="photo-date">${new Date(photo.created_at).toLocaleDateString("pt-BR")}</span></a>`).join("") || '<div class="empty">Este aluno ainda não enviou fotos.</div>'}</div></section>`;
  gallery.scrollIntoView({ behavior: "smooth", block: "start" });
}
function contato(){
  const ig=CONTACT.instagram, wa=CONTACT.whatsapp;
  view.innerHTML=`<section class="contact-card">${logo()}<h2 class="section-heading">Mayck Fiuza</h2><p class="text-paragraph muted">Fale com o time pelos canais oficiais.</p><div class="contact-actions">${ig?`<a class="app-link contact-link" href="${ig}" target="_blank" rel="noopener"><b class="contact-name">INSTAGRAM</b><span class="contact-description">Abrir perfil →</span></a>`:`<div class="contact-link disabled"><b class="contact-name">INSTAGRAM</b><span class="contact-description">Link ainda não configurado</span></div>`}${wa?`<a class="app-link contact-link" href="${wa}" target="_blank" rel="noopener"><b class="contact-name">WHATSAPP</b><span class="contact-description">Iniciar conversa →</span></a>`:`<div class="contact-link disabled"><b class="contact-name">WHATSAPP</b><span class="contact-description">Link ainda não configurado</span></div>`}</div></section>`;
}

async function pagamentos() {
  const rows = await req("/payments");
  const alerts = rows.flatMap(x => x.payments.filter(p => p.alert).map(p => ({name:x.student_name, due:p.due_date})));
  view.innerHTML = `<div class="payment-page"><section class="card"><h2 class="section-heading">Conferência de pagamentos</h2><p class="muted">Configure a data inicial e a periodicidade de cada aluno. Os próximos vencimentos serão gerados automaticamente.</p>${alerts.length ? `<div class="payment-alert" role="alert"><b>Pagamentos atrasados (${alerts.length})</b>${alerts.map(a=>`<p>${safe(a.name)} — vencimento ${new Date(a.due+'T12:00:00').toLocaleDateString('pt-BR')}</p>`).join('')}</div>` : `<p class="muted">Nenhum aviso de atraso no momento.</p>`}</section>${rows.map(x=>`<section class="card payment-student"><h2 class="section-heading">${safe(x.student_name)}</h2><form class="app-form payment-plan" data-student="${x.student_id}"><label class="field">Primeiro vencimento<input class="form-control" type="date" name="start_date" value="${x.start_date || ''}" required></label><label class="field">Periodicidade<select class="form-select" name="cycle">${[['mensal','Mensal'],['trimestral','Trimestral'],['semestral','Semestral'],['anual','Anual']].map(([key,label])=>`<option value="${key}" ${x.cycle===key?'selected':''}>${label}</option>`).join('')}</select></label><label class="field">Valor (R$) — opcional<input class="form-control" type="number" min="0" step="0.01" name="amount" value="${x.amount ?? ''}"></label><button class="ui-button btn">Salvar vencimentos</button></form><div class="payment-items">${x.payments.length ? x.payments.filter(p=>p.due_date <= new Date(new Date().setFullYear(new Date().getFullYear()+1)).toISOString().slice(0,10)).map(p=>`<div class="row"><div><b>${new Date(p.due_date+'T12:00:00').toLocaleDateString('pt-BR')}</b><div class="muted">${p.paid?'Pago':p.overdue?'Atrasado':'Pendente'}</div></div><label class="payment-check"><input type="checkbox" data-payment="${p.id}" ${p.paid?'checked':''}> Pago</label></div>`).join('') : '<p class="muted">Configure o primeiro vencimento para gerar as cobranças.</p>'}</div></section>`).join('') || '<section class="card">Cadastre um aluno primeiro para configurar os pagamentos.</section>'}</div>`;
  document.querySelectorAll('.payment-plan').forEach(form=>form.addEventListener('submit',async e=>{
    e.preventDefault(); const data = new FormData(form);
    try { await req('/payments/plan',{method:'PUT',body:JSON.stringify({student_id:Number(form.dataset.student),start_date:data.get('start_date'),cycle:data.get('cycle'),amount:data.get('amount')===''?null:Number(data.get('amount'))})}); await pagamentos(); }
    catch(err){ alert(err.message); }
  }));
  document.querySelectorAll('[data-payment]').forEach(input=>input.addEventListener('change',async()=>{
    try {await req('/payments/'+input.dataset.payment,{method:'PATCH',body:JSON.stringify({paid:input.checked})});await pagamentos();}
    catch(err){alert(err.message); input.checked=!input.checked;}
  }));
}

function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  token = null;
  user = null;
  login();
}

// Funções usadas pelos atributos onclick do HTML gerado dinamicamente.
// Como app.js é carregado como ES module no Vite, elas precisam ser
// expostas explicitamente no objeto window.
Object.assign(window, {
  login,
  forgotPassword,
  register,
  setTab,
  toggleMenu,
  delLesson,
  finishLesson,
  studentLessons,
  changeStudentLessonMonth,
  workout,
  treino,
  treinoDetalhe,
  startWorkoutTimer,
  finishWorkoutTimer,
  openStudentPhotos,
  logout,
});

render();

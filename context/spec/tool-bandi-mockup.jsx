import { useState, useMemo, useCallback } from "react";

/* ══════════════════════════════════════════════════════════════
   MOCK DATA
   ══════════════════════════════════════════════════════════════ */

const SOGGETTI = [
  { id:1, nome:"La Monica Luciano", tipo:"reale", forma:"Impresa individuale", regime:"Forfettario", piva:"07104590828", ateco:"62.20.10", dipendenti:0, fatturato:85000, regione:"Sicilia", comune:"Palermo", zes:true, mezzogiorno:true, under35:true, annoCostituzione:2023, soa:false, completezza:90,
    hardStops:[{label:"SRL obbligatoria",bandi:34,azione:"Costituire SRL sblocca 34 bandi"},{label:"Fatturato min > 85k",bandi:18,azione:"Passaggio a regime ordinario"},{label:"SOA richiesta",bandi:12,azione:"Non prioritario — solo lavori pubblici"},{label:"Min 1 dipendente",bandi:8,azione:"Assunzione agevolata under 36"}],
    vantaggi:[{label:"Under 35",dettaglio:"Bonus giovani imprenditori"},{label:"ZES Sicilia",dettaglio:"Credito d'imposta 40-50%"},{label:"ATECO 62.20 digitale",dettaglio:"Prioritario PNRR"},{label:"Nuova impresa (2023)",dettaglio:"Bandi startup / neocostituite"}]
  },
  { id:2, nome:"[Sim] La Monica SRL", tipo:"simulazione", simulazioneDi:1, forma:"SRL unipersonale", regime:"Ordinario", piva:"—", ateco:"62.20.10", dipendenti:0, fatturato:85000, regione:"Sicilia", comune:"Palermo", zes:true, mezzogiorno:true, under35:false, annoCostituzione:null, soa:false, completezza:75,
    hardStops:[{label:"Fatturato min > 85k",bandi:18,azione:"Crescita fatturato necessaria"},{label:"SOA richiesta",bandi:12,azione:"Non prioritario"}],
    vantaggi:[{label:"ZES Sicilia",dettaglio:"Credito d'imposta 40-50%"},{label:"ATECO 62.20 digitale",dettaglio:"Prioritario PNRR"}]
  },
  { id:3, nome:"Rossi Mario", tipo:"reale", forma:"SRL", regime:"Ordinario", piva:"09876543210", ateco:"55.10.00", dipendenti:4, fatturato:320000, regione:"Toscana", comune:"Firenze", zes:false, mezzogiorno:false, under35:false, annoCostituzione:2019, soa:false, completezza:95,
    hardStops:[{label:"SOA richiesta",bandi:12,azione:"Non prioritario"}],
    vantaggi:[{label:"PMI innovativa",dettaglio:"Accesso a bandi MISE"}]
  },
];

const PROGETTI = [
  { id:1, nome:"La Monica ICT", soggettoId:1, settore:"ICT", descBreve:"Consulenza IT e digitalizzazione PA — servizi cloud, cybersecurity per enti pubblici siciliani", costituita:true, budgetMin:20000, budgetMax:200000, cofiPerc:10, completezza:45, bandiMatch:8, candidatureAttive:3, scoreMedio:68 },
  { id:2, nome:"Paese Delle Stelle", soggettoId:1, settore:"Turismo", descBreve:"Turismo astronomico a Roccapalumba — osservatorio, percorsi notturni, planetario immersivo", costituita:false, budgetMin:100000, budgetMax:800000, cofiPerc:20, completezza:65, bandiMatch:5, candidatureAttive:1, scoreMedio:52 },
  { id:3, nome:"Progetto Hospitality", soggettoId:3, settore:"Turismo", descBreve:"Boutique hotel con ristorante km0 nel centro storico di Firenze", costituita:true, budgetMin:200000, budgetMax:500000, cofiPerc:30, completezza:55, bandiMatch:3, candidatureAttive:0, scoreMedio:44 },
];

const BANDI = [
  { id:1, titolo:"Smart&Start Italia 2026", ente:"Invitalia", portale:"invitalia.it", tipo:"fondo_perduto", tipoPerc:"70%", budget:"€1.5M", scadenza:"2026-06-30", stato:"aperto",
    valutazioni:[
      {progettoId:1,score:72,idoneo:true,hardStop:null,pro:[{l:"Regione Sicilia compatibile",p:15},{l:"ATECO 62.20 prioritario",p:10},{l:"Under 35",p:8},{l:"Startup innovativa",p:12}],contro:[{l:"Cofinanziamento 30% richiesto",t:"gap"},{l:"Business plan triennale mancante",t:"gap"}],gaps:["Cofinanziamento 30%","Business plan triennale"]},
      {progettoId:2,score:45,idoneo:true,hardStop:null,pro:[{l:"Regione Sicilia",p:15},{l:"Turismo innovativo",p:8}],contro:[{l:"Non ancora costituita",t:"yellow"},{l:"Settore non prioritario",t:"gap"}],gaps:["Costituzione impresa","Settore non allineato"]},
    ]},
  { id:2, titolo:"FESR Sicilia — Turismo Esperienziale", ente:"Regione Sicilia", portale:"euroinfosicilia.it", tipo:"fondo_perduto", tipoPerc:"80%", budget:"€500k", scadenza:"2026-04-15", stato:"aperto",
    valutazioni:[
      {progettoId:2,score:65,idoneo:false,hardStop:"SRL o APS obbligatoria",pro:[{l:"Turismo esperienziale perfetto",p:20},{l:"Borgo < 5000 ab.",p:15},{l:"ZES Sicilia",p:12}],contro:[{l:"SRL o APS obbligatoria",t:"hard_stop"},{l:"Cofinanziamento 20% minimo",t:"gap"}],gaps:["Forma giuridica","Cofinanziamento 20%"]},
      {progettoId:1,score:28,idoneo:false,hardStop:"Settore non ammissibile",pro:[{l:"ZES Sicilia",p:12}],contro:[{l:"Settore ICT non ammissibile",t:"hard_stop"}],gaps:["Settore non compatibile"]},
    ]},
  { id:3, titolo:"Voucher Digitalizzazione PMI", ente:"MIMIT", portale:"mise.gov.it", tipo:"voucher", tipoPerc:"100%", budget:"€10k", scadenza:"2026-05-31", stato:"aperto",
    valutazioni:[
      {progettoId:1,score:85,idoneo:true,hardStop:null,pro:[{l:"Digitalizzazione PA perfetto",p:25},{l:"ATECO prioritario",p:15},{l:"PMI ammissibile",p:10}],contro:[{l:"Budget limitato",t:"yellow"}],gaps:[]},
    ]},
  { id:4, titolo:"Bando Borghi PNRR — Linea B", ente:"MiC", portale:"cultura.gov.it", tipo:"fondo_perduto", tipoPerc:"100%", budget:"€2M", scadenza:"2026-03-28", stato:"aperto",
    valutazioni:[
      {progettoId:2,score:58,idoneo:false,hardStop:"Min 10 dipendenti",pro:[{l:"Borgo < 5000 ab. perfetto",p:20},{l:"Cultura/turismo",p:12},{l:"Sicilia Mezzogiorno",p:10}],contro:[{l:"Min 10 dipendenti",t:"hard_stop"},{l:"Piano triennale mancante",t:"gap"}],gaps:["Dipendenti insufficienti","Piano triennale"]},
    ]},
  { id:5, titolo:"Credito d'Imposta Mezzogiorno 2026", ente:"Agenzia Entrate", portale:"agenziaentrate.gov.it", tipo:"credito_imposta", tipoPerc:"45%", budget:"illimitato", scadenza:"2026-12-31", stato:"aperto",
    valutazioni:[
      {progettoId:1,score:61,idoneo:true,hardStop:null,pro:[{l:"Mezzogiorno automatico",p:20},{l:"ZES bonus aggiuntivo",p:15}],contro:[{l:"Solo investimenti materiali",t:"yellow"}],gaps:["Verificare tipologia investimento"]},
      {progettoId:2,score:55,idoneo:true,hardStop:null,pro:[{l:"Mezzogiorno",p:20},{l:"ZES",p:15}],contro:[{l:"Non ancora costituita",t:"yellow"}],gaps:["Costituzione"]},
    ]},
  { id:6, titolo:"ON — Oltre Nuove Imprese a Tasso Zero", ente:"Invitalia", portale:"invitalia.it", tipo:"mix", tipoPerc:"70% FP + 30% prestito", budget:"€3M", scadenza:"2026-09-30", stato:"aperto",
    valutazioni:[
      {progettoId:1,score:77,idoneo:true,hardStop:null,pro:[{l:"Under 35 prioritario",p:20},{l:"Nuova impresa",p:15},{l:"Sicilia",p:10}],contro:[{l:"Mix FP + prestito",t:"yellow"},{l:"Business plan dettagliato",t:"gap"}],gaps:["Business plan"]},
    ]},
];

const CANDIDATURE = [
  { id:1, bandoId:1, progettoId:1, soggettoId:1, stato:"lavorazione", score:72, progresso:60, dataCreazione:"2026-03-15",
    checklist:[{label:"Verifica requisiti ammissibilità",done:true,nota:""},{label:"Preparazione business plan triennale",done:false,nota:"In attesa dati Q1"},{label:"Calcolo cofinanziamento 30%",done:true,nota:"Mezzi propri + partner"},{label:"Firma digitale documenti",done:false,nota:""},{label:"Compilazione formulario online",done:false,nota:""}],
    documenti:[{nome:"Proposta tecnica",versione:"v2",stato:"approvato"},{nome:"Dichiarazione sostitutiva",versione:"v1",stato:"bozza"},{nome:"CV impresa",versione:"v1",stato:"approvato"}],
    note:[{testo:"Contattato commercialista per verifica cofinanziamento",ts:"2026-03-18 10:30",tipo:"nota"},{testo:"Business plan da completare entro fine marzo",ts:"2026-03-16 14:00",tipo:"decisione"}]
  },
  { id:2, bandoId:3, progettoId:1, soggettoId:1, stato:"pronta", score:85, progresso:90, dataCreazione:"2026-03-10",
    checklist:[{label:"Verifica requisiti",done:true,nota:""},{label:"Preventivi fornitori",done:true,nota:"3 preventivi raccolti"},{label:"DSAN",done:true,nota:""},{label:"Upload allegati",done:false,nota:"Manca visura camerale aggiornata"}],
    documenti:[{nome:"Domanda voucher",versione:"v1",stato:"approvato"},{nome:"Preventivi",versione:"v1",stato:"approvato"},{nome:"Visura camerale",versione:"—",stato:"da_generare"}],
    note:[{testo:"Pronta per invio, manca solo visura aggiornata",ts:"2026-03-19 09:00",tipo:"nota"}]
  },
  { id:3, bandoId:6, progettoId:1, soggettoId:1, stato:"bozza", score:77, progresso:10, dataCreazione:"2026-03-18",
    checklist:[{label:"Verifica requisiti under 35",done:true,nota:""},{label:"Business plan dettagliato",done:false,nota:""},{label:"Piano investimenti",done:false,nota:""},{label:"Preventivi",done:false,nota:""}],
    documenti:[],
    note:[]
  },
  { id:4, bandoId:5, progettoId:2, soggettoId:1, stato:"sospesa", score:55, progresso:30, dataCreazione:"2026-03-12",
    checklist:[{label:"Verifica investimenti materiali",done:true,nota:"Solo planetario e strumentazione"},{label:"Costituzione impresa",done:false,nota:"In attesa decisione SRL"},{label:"Documentazione tecnica",done:false,nota:""}],
    documenti:[{nome:"Scheda investimento",versione:"v1",stato:"bozza"}],
    note:[{testo:"Sospesa in attesa decisione su costituzione SRL — sblocca anche FESR",ts:"2026-03-14 16:00",tipo:"decisione"}]
  },
  { id:5, bandoId:1, progettoId:1, soggettoId:1, stato:"inviata", score:72, progresso:100, dataCreazione:"2026-02-20", dataInvio:"2026-03-10", protocollo:"SS2026-00847",
    checklist:[{label:"Tutto completato",done:true,nota:""}],
    documenti:[{nome:"Domanda completa",versione:"v3",stato:"approvato"}],
    note:[{testo:"Inviata con protocollo SS2026-00847",ts:"2026-03-10 11:22",tipo:"nota"}]
  },
];

const TIMELINE = [
  {data:"19/03 14:30",tipo:"scan",testo:"Scansione completata: 4 nuovi bandi trovati"},
  {data:"18/03 16:00",tipo:"cand",testo:"Candidatura ON — Tasso Zero creata per La Monica ICT"},
  {data:"18/03 10:30",tipo:"nota",testo:"Nota aggiunta su Smart&Start: contattato commercialista"},
  {data:"17/03 09:15",tipo:"prog",testo:"Progetto PDS: aggiunto partner Comune di Roccapalumba"},
  {data:"16/03 14:00",tipo:"cand",testo:"Smart&Start: business plan da completare entro fine marzo"},
  {data:"15/03 11:00",tipo:"cand",testo:"Candidatura Smart&Start avviata per La Monica ICT"},
  {data:"14/03 16:00",tipo:"cand",testo:"Candidatura Credito Mezzogiorno sospesa — attesa decisione SRL"},
  {data:"12/03 10:00",tipo:"scan",testo:"Scansione completata: 2 nuovi bandi trovati"},
  {data:"10/03 11:22",tipo:"cand",testo:"Smart&Start (seconda candidatura) inviata — prot. SS2026-00847"},
];

const SCANSIONI = [
  {data:"19/03/2026 14:30",stato:"success",durata:"4m 32s",trovati:12,nuovi:4,errori:0},
  {data:"17/03/2026 14:30",stato:"success",durata:"3m 58s",trovati:10,nuovi:2,errori:0},
  {data:"15/03/2026 14:30",stato:"failed",durata:"1m 12s",trovati:0,nuovi:0,errori:3},
  {data:"13/03/2026 14:30",stato:"success",durata:"5m 01s",trovati:15,nuovi:6,errori:0},
  {data:"11/03/2026 14:30",stato:"success",durata:"4m 10s",trovati:11,nuovi:1,errori:0},
];

/* ══════════════════════════════════════════════════════════════
   UTILITIES
   ══════════════════════════════════════════════════════════════ */

const daysUntil = (d) => { const now=new Date("2026-03-19"); const t=new Date(d); return Math.ceil((t-now)/(1000*60*60*24)); };

const Badge = ({children,color="gray",small=false}) => {
  const colors = {
    green:"bg-emerald-100 text-emerald-800", red:"bg-red-100 text-red-800", orange:"bg-orange-100 text-orange-800",
    blue:"bg-blue-100 text-blue-800", purple:"bg-violet-100 text-violet-800", yellow:"bg-yellow-100 text-yellow-800",
    gold:"bg-amber-100 text-amber-800", gray:"bg-slate-100 text-slate-600", cyan:"bg-cyan-100 text-cyan-800",
    redlight:"bg-red-50 text-red-400",
  };
  return <span className={`${colors[color]||colors.gray} ${small?"text-[10px] px-1.5 py-0.5":"text-xs px-2 py-1"} rounded-full font-semibold inline-flex items-center gap-1 whitespace-nowrap`}>{children}</span>;
};

const ScoreBadge = ({score}) => {
  if(score==null) return <Badge color="gray">—</Badge>;
  const c = score>=60?"green":score>=40?"orange":"red";
  return <Badge color={c}>{score}/100</Badge>;
};

const StatoBadge = ({stato}) => {
  const map = {bozza:["Bozza","gray"],lavorazione:["Lavorazione","blue"],sospesa:["Sospesa","yellow"],pronta:["Pronta","purple"],inviata:["Inviata","gold"],abbandonata:["Abbandonata","redlight"]};
  const [l,c] = map[stato]||["—","gray"];
  return <Badge color={c}>{l}</Badge>;
};

const TipoBadge = ({tipo,perc}) => {
  const map = {fondo_perduto:["FP","green"],prestito_agevolato:["Prestito","yellow"],credito_imposta:["Credito imp.","blue"],voucher:["Voucher","cyan"],mix:["Mix","green"]};
  const [l,c] = map[tipo]||["—","gray"];
  return <Badge color={c}>{l} {perc}</Badge>;
};

const UrgenzaBadge = ({giorni}) => {
  if(giorni<=7) return <span className="text-red-600 font-bold text-xs">🔴 {giorni}gg URGENTE</span>;
  if(giorni<=14) return <span className="text-orange-600 font-semibold text-xs">🟠 {giorni}gg</span>;
  if(giorni<=30) return <span className="text-yellow-600 text-xs">🟡 {giorni}gg</span>;
  return <span className="text-slate-500 text-xs">{giorni}gg</span>;
};

const ProgBar = ({value,className=""}) => (
  <div className={`h-2 bg-slate-200 rounded-full overflow-hidden ${className}`} style={{minWidth:60}}>
    <div className={`h-full rounded-full ${value>=80?"bg-emerald-500":value>=50?"bg-blue-500":value>=30?"bg-yellow-500":"bg-red-400"}`} style={{width:`${value}%`}}/>
  </div>
);

const Tabs = ({tabs,active,onChange}) => (
  <div className="flex gap-0 border-b border-slate-200 mb-4">
    {tabs.map(t=>(
      <button key={t.id} onClick={()=>onChange(t.id)}
        className={`px-4 py-2.5 text-sm font-medium transition-colors relative ${active===t.id?"text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600":"text-slate-500 hover:text-slate-700"}`}>
        {t.label}{t.count!=null&&<span className="ml-1.5 text-xs bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded-full">{t.count}</span>}
      </button>
    ))}
  </div>
);

const Card = ({children,className=""}) => <div className={`bg-white rounded-lg border border-slate-200 shadow-sm ${className}`}>{children}</div>;

const PageHeader = ({back,backLabel,title,subtitle,children,warning}) => (
  <div className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-10">
    {back && <button onClick={back} className="text-sm text-blue-600 hover:text-blue-800 mb-1 flex items-center gap-1">← {backLabel||"Indietro"}</button>}
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-xl font-bold text-slate-900 truncate">{title}</h1>
        {subtitle && <p className="text-sm text-slate-500 mt-0.5">{subtitle}</p>}
        {warning && <p className="text-sm text-amber-600 mt-1 flex items-center gap-1">⚠️ {warning}</p>}
      </div>
      <div className="flex items-center gap-2 shrink-0">{children}</div>
    </div>
  </div>
);

const StatCard = ({label,value,sub,color="blue"}) => {
  const bg = {blue:"from-blue-500 to-blue-600",green:"from-emerald-500 to-emerald-600",orange:"from-orange-500 to-orange-600",purple:"from-violet-500 to-violet-600"}[color]||"from-blue-500 to-blue-600";
  return (
    <div className={`bg-gradient-to-br ${bg} rounded-lg p-4 text-white shadow-sm`}>
      <p className="text-sm opacity-80">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs opacity-70 mt-1">{sub}</p>}
    </div>
  );
};

const EmptyState = ({icon="📭",text,action,onAction}) => (
  <div className="text-center py-12 text-slate-400">
    <p className="text-4xl mb-3">{icon}</p>
    <p className="text-sm">{text}</p>
    {action && <button onClick={onAction} className="mt-3 text-sm text-blue-600 hover:underline">{action}</button>}
  </div>
);

/* ══════════════════════════════════════════════════════════════
   PAGES
   ══════════════════════════════════════════════════════════════ */

// ──── DASHBOARD ────
const DashboardPage = ({nav}) => {
  const urgenti = CANDIDATURE.filter(c=>c.stato!=="inviata"&&c.stato!=="abbandonata").map(c=>{
    const b=BANDI.find(x=>x.id===c.bandoId); const p=PROGETTI.find(x=>x.id===c.progettoId); const s=SOGGETTI.find(x=>x.id===c.soggettoId);
    return {...c,bando:b,progetto:p,soggetto:s,giorni:daysUntil(b.scadenza)};
  }).sort((a,b)=>a.giorni-b.giorni);

  const perStato = {bozza:CANDIDATURE.filter(c=>c.stato==="bozza").length,lavorazione:CANDIDATURE.filter(c=>c.stato==="lavorazione").length,sospesa:CANDIDATURE.filter(c=>c.stato==="sospesa").length,pronta:CANDIDATURE.filter(c=>c.stato==="pronta").length,inviata:CANDIDATURE.filter(c=>c.stato==="inviata").length};
  const progettiIncompleti = PROGETTI.filter(p=>p.completezza<100).sort((a,b)=>a.completezza-b.completezza);

  return (
    <div className="p-6 space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Candidature attive" value={CANDIDATURE.filter(c=>!["inviata","abbandonata"].includes(c.stato)).length} sub="in lavorazione" color="blue"/>
        <StatCard label="Scadono in 14gg" value={urgenti.filter(u=>u.giorni<=14).length} sub="richiedono attenzione" color="orange"/>
        <StatCard label="Nuovi bandi" value={4} sub="ultima scansione" color="green"/>
        <StatCard label="Ultima scansione" value="19/03" sub="14:30 · 12 bandi" color="purple"/>
      </div>

      {/* Candidature urgenti */}
      <Card className="overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100"><h2 className="font-semibold text-slate-800 text-sm">Candidature — Scadenze imminenti</h2></div>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-slate-400 border-b border-slate-100">
            <th className="px-4 py-2 font-medium">Bando</th><th className="px-4 py-2 font-medium">Progetto</th><th className="px-4 py-2 font-medium">Soggetto</th><th className="px-4 py-2 font-medium">Stato</th><th className="px-4 py-2 font-medium">Score</th><th className="px-4 py-2 font-medium">Scadenza</th>
          </tr></thead>
          <tbody>
            {urgenti.map(u=>(
              <tr key={u.id} className="border-b border-slate-50 hover:bg-slate-50 cursor-pointer" onClick={()=>nav("candidatura",u.id)}>
                <td className="px-4 py-3 font-medium text-slate-800">{u.bando.titolo}</td>
                <td className="px-4 py-3 text-slate-600">{u.progetto.nome}</td>
                <td className="px-4 py-3 text-slate-600">{u.soggetto.nome}</td>
                <td className="px-4 py-3"><StatoBadge stato={u.stato}/></td>
                <td className="px-4 py-3"><ScoreBadge score={u.score}/></td>
                <td className="px-4 py-3"><UrgenzaBadge giorni={u.giorni}/></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <div className="grid grid-cols-2 gap-4">
        {/* Left col */}
        <div className="space-y-4">
          <Card className="p-4">
            <h3 className="font-semibold text-slate-800 text-sm mb-3">Candidature per stato</h3>
            <div className="space-y-2">
              {Object.entries(perStato).map(([s,n])=>(
                <div key={s} className="flex items-center justify-between">
                  <StatoBadge stato={s}/><span className="text-lg font-bold text-slate-700">{n}</span>
                </div>
              ))}
            </div>
          </Card>
          <Card className="p-4">
            <h3 className="font-semibold text-slate-800 text-sm mb-3">Nuovi bandi</h3>
            {BANDI.slice(0,3).map(b=>(
              <div key={b.id} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0 cursor-pointer hover:bg-slate-50 -mx-2 px-2 rounded" onClick={()=>nav("bando",b.id)}>
                <div className="min-w-0"><p className="text-sm font-medium text-slate-700 truncate">{b.titolo}</p><p className="text-xs text-slate-400">{b.ente}</p></div>
                <UrgenzaBadge giorni={daysUntil(b.scadenza)}/>
              </div>
            ))}
            <button onClick={()=>nav("bandi")} className="text-xs text-blue-600 hover:underline mt-2">Vedi tutti →</button>
          </Card>
        </div>

        {/* Right col */}
        <div className="space-y-4">
          <Card className="p-4">
            <h3 className="font-semibold text-slate-800 text-sm mb-3">Progetti incompleti</h3>
            {progettiIncompleti.map(p=>(
              <div key={p.id} className="flex items-center gap-3 py-2 border-b border-slate-50 last:border-0 cursor-pointer hover:bg-slate-50 -mx-2 px-2 rounded" onClick={()=>nav("progetto",p.id)}>
                <div className="flex-1 min-w-0"><p className="text-sm font-medium text-slate-700 truncate">{p.nome}</p></div>
                <span className="text-xs text-slate-500 shrink-0">{p.completezza}%</span>
                <ProgBar value={p.completezza} className="w-20"/>
              </div>
            ))}
          </Card>
          <Card className="p-4">
            <h3 className="font-semibold text-slate-800 text-sm mb-3">Hard stop più impattanti</h3>
            {SOGGETTI.filter(s=>s.tipo==="reale").flatMap(s=>s.hardStops.map(h=>({...h,soggetto:s.nome}))).sort((a,b)=>b.bandi-a.bandi).slice(0,4).map((h,i)=>(
              <div key={i} className="py-2 border-b border-slate-50 last:border-0">
                <div className="flex items-center gap-2"><span className="text-red-500 text-xs">❌</span><span className="text-sm font-medium text-slate-700">{h.label}</span><span className="text-xs text-red-500 font-semibold">→ {h.bandi} bandi</span></div>
                <p className="text-xs text-slate-400 ml-5">← {h.soggetto}</p>
              </div>
            ))}
          </Card>
        </div>
      </div>

      {/* Timeline */}
      <Card className="p-4">
        <h3 className="font-semibold text-slate-800 text-sm mb-3">Attività recenti</h3>
        <div className="space-y-2">
          {TIMELINE.map((t,i)=>{
            const icon = {scan:"⚙️",cand:"📁",nota:"📝",prog:"🌟"}[t.tipo]||"•";
            return <div key={i} className="flex items-start gap-3 text-sm py-1"><span className="text-slate-400 text-xs shrink-0 w-24 pt-0.5">{t.data}</span><span>{icon}</span><span className="text-slate-600">{t.testo}</span></div>;
          })}
        </div>
      </Card>
    </div>
  );
};

// ──── SOGGETTI ────
const SoggettiPage = ({nav}) => {
  const [tab,setTab]=useState("reali");
  const [selId,setSelId]=useState(null);
  const [detTab,setDetTab]=useState("anagrafica");
  const filtered = SOGGETTI.filter(s=>tab==="reali"?s.tipo==="reale":s.tipo==="simulazione");
  const sel = selId?SOGGETTI.find(s=>s.id===selId):null;

  if(sel) {
    const progetti = PROGETTI.filter(p=>p.soggettoId===sel.id);
    return (
      <div>
        <PageHeader back={()=>setSelId(null)} backLabel="Soggetti" title={sel.nome}
          subtitle={`${sel.forma} · ${sel.regime}${sel.tipo==="simulazione"?" · 🧪 Simulazione":""}`}>
          <button className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700">Salva</button>
          {sel.tipo==="reale"&&<button className="px-3 py-1.5 text-xs border border-slate-300 rounded-lg hover:bg-slate-50">Duplica come simulazione</button>}
        </PageHeader>
        <div className="p-6">
          <Tabs active={detTab} onChange={setDetTab} tabs={[{id:"anagrafica",label:"Anagrafica"},{id:"vincoli",label:"Vincoli & Vantaggi"},{id:"progetti",label:"Progetti",count:progetti.length}]}/>

          {detTab==="anagrafica"&&(
            <div className="grid grid-cols-2 gap-6">
              <Card className="p-4 space-y-4">
                <h3 className="font-semibold text-sm text-slate-800">Identità</h3>
                <div className="space-y-3">
                  {[["Nome",sel.nome],["Forma giuridica",sel.forma],["Regime fiscale",sel.regime],["P.IVA",sel.piva]].map(([l,v])=>(
                    <div key={l}><label className="text-xs text-slate-500">{l}</label><input className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm" defaultValue={v}/></div>
                  ))}
                </div>
              </Card>
              <div className="space-y-4">
                <Card className="p-4 space-y-3">
                  <h3 className="font-semibold text-sm text-slate-800">Attività</h3>
                  {[["Codice ATECO",sel.ateco],["Dipendenti",sel.dipendenti],["Fatturato max","€"+sel.fatturato.toLocaleString()],["Anno costituzione",sel.annoCostituzione||"—"]].map(([l,v])=>(
                    <div key={l}><label className="text-xs text-slate-500">{l}</label><input className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm" defaultValue={v}/></div>
                  ))}
                </Card>
                <Card className="p-4 space-y-3">
                  <h3 className="font-semibold text-sm text-slate-800">Sede e zone</h3>
                  <div className="grid grid-cols-2 gap-3">
                    {[["Regione",sel.regione],["Comune",sel.comune]].map(([l,v])=>(
                      <div key={l}><label className="text-xs text-slate-500">{l}</label><input className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm" defaultValue={v}/></div>
                    ))}
                  </div>
                  <div className="flex items-center gap-6 pt-2">
                    <label className="flex items-center gap-2 text-sm"><input type="checkbox" defaultChecked={sel.zes} className="rounded"/> ZES</label>
                    <label className="flex items-center gap-2 text-sm"><input type="checkbox" defaultChecked={sel.under35} className="rounded"/> Under 35</label>
                    <label className="flex items-center gap-2 text-sm"><input type="checkbox" defaultChecked={sel.soa} className="rounded"/> SOA</label>
                  </div>
                </Card>
              </div>
              <div className="col-span-2 flex items-center gap-2 text-sm text-slate-500">Completezza: <ProgBar value={sel.completezza} className="w-32"/> <span className="font-medium text-slate-700">{sel.completezza}%</span></div>
            </div>
          )}

          {detTab==="vincoli"&&(
            <div className="grid grid-cols-2 gap-6">
              <Card className="p-4">
                <h3 className="font-semibold text-sm text-red-700 mb-3">❌ Hard Stop ({sel.hardStops.length})</h3>
                {sel.hardStops.length===0?<p className="text-sm text-emerald-600">✅ Nessun vincolo bloccante attivo</p>:
                  <div className="space-y-3">{sel.hardStops.map((h,i)=>(
                    <div key={i} className="p-3 bg-red-50 rounded-lg border border-red-100">
                      <div className="flex items-center gap-2"><span className="text-red-500">❌</span><span className="text-sm font-semibold text-red-800">{h.label}</span></div>
                      <p className="text-xs text-red-600 mt-1 ml-6">→ {h.bandi} bandi bloccati</p>
                      <p className="text-xs text-slate-500 mt-1 ml-6">Azione: {h.azione}</p>
                    </div>
                  ))}</div>
                }
              </Card>
              <Card className="p-4">
                <h3 className="font-semibold text-sm text-emerald-700 mb-3">✅ Vantaggi ({sel.vantaggi.length})</h3>
                {sel.vantaggi.length===0?<p className="text-sm text-slate-400">Nessun vantaggio specifico rilevato</p>:
                  <div className="space-y-3">{sel.vantaggi.map((v,i)=>(
                    <div key={i} className="p-3 bg-emerald-50 rounded-lg border border-emerald-100">
                      <div className="flex items-center gap-2"><span className="text-emerald-500">✅</span><span className="text-sm font-semibold text-emerald-800">{v.label}</span></div>
                      <p className="text-xs text-slate-500 mt-1 ml-6">{v.dettaglio}</p>
                    </div>
                  ))}</div>
                }
              </Card>
            </div>
          )}

          {detTab==="progetti"&&(
            <Card className="overflow-hidden">
              {progetti.length===0?<EmptyState text="Nessun progetto associato" action="Crea il primo progetto →" onAction={()=>nav("progetti")}/>:
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs text-slate-400 border-b border-slate-100"><th className="px-4 py-2">Progetto</th><th className="px-4 py-2">Settore</th><th className="px-4 py-2">Completezza</th><th className="px-4 py-2">Candidature</th></tr></thead>
                <tbody>{progetti.map(p=>(
                  <tr key={p.id} className="border-b border-slate-50 hover:bg-slate-50 cursor-pointer" onClick={()=>nav("progetto",p.id)}>
                    <td className="px-4 py-3 font-medium text-slate-800">{p.nome}</td>
                    <td className="px-4 py-3 text-slate-600">{p.settore}</td>
                    <td className="px-4 py-3"><div className="flex items-center gap-2"><ProgBar value={p.completezza} className="w-16"/><span className="text-xs text-slate-500">{p.completezza}%</span></div></td>
                    <td className="px-4 py-3 text-slate-600">{p.candidatureAttive}</td>
                  </tr>
                ))}</tbody>
              </table>}
            </Card>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Soggetti" subtitle={`${SOGGETTI.filter(s=>s.tipo==="reale").length} reali · ${SOGGETTI.filter(s=>s.tipo==="simulazione").length} simulazioni`}>
        <button className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700">+ Nuovo soggetto</button>
      </PageHeader>
      <div className="p-6">
        <Tabs active={tab} onChange={setTab} tabs={[{id:"reali",label:"Reali",count:SOGGETTI.filter(s=>s.tipo==="reale").length},{id:"simulazioni",label:"Simulazioni",count:SOGGETTI.filter(s=>s.tipo==="simulazione").length}]}/>
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-slate-400 border-b border-slate-100">
              <th className="px-4 py-2 font-medium">Nome</th><th className="px-4 py-2 font-medium">Forma</th><th className="px-4 py-2 font-medium">Regime</th><th className="px-4 py-2 font-medium">Progetti</th><th className="px-4 py-2 font-medium">Hard stop</th><th className="px-4 py-2 font-medium">Bandi bloccati</th><th className="px-4 py-2 font-medium">Completezza</th>
            </tr></thead>
            <tbody>{filtered.map(s=>{
              const pc=PROGETTI.filter(p=>p.soggettoId===s.id).length;
              const bb=s.hardStops.reduce((a,h)=>a+h.bandi,0);
              return (
                <tr key={s.id} className="border-b border-slate-50 hover:bg-slate-50 cursor-pointer" onClick={()=>setSelId(s.id)}>
                  <td className="px-4 py-3"><span className="font-medium text-slate-800">{s.nome}</span>{s.tipo==="simulazione"&&<Badge color="purple" small>SIM</Badge>}</td>
                  <td className="px-4 py-3 text-slate-600">{s.forma}</td>
                  <td className="px-4 py-3 text-slate-600">{s.regime}</td>
                  <td className="px-4 py-3 text-slate-700 font-medium">{pc}</td>
                  <td className="px-4 py-3">{s.hardStops.length>0?<Badge color="red">{s.hardStops.length}</Badge>:<span className="text-emerald-500 text-xs">✅</span>}</td>
                  <td className="px-4 py-3 text-red-600 font-medium">{bb>0?bb:"—"}</td>
                  <td className="px-4 py-3"><div className="flex items-center gap-2"><ProgBar value={s.completezza} className="w-16"/><span className="text-xs text-slate-500">{s.completezza}%</span></div></td>
                </tr>
              );
            })}</tbody>
          </table>
        </Card>
      </div>
    </div>
  );
};

// ──── PROGETTI ────
const ProgettiPage = ({nav}) => {
  const [selId,setSelId]=useState(null);
  const [tab,setTab]=useState("opportunita");
  const sel = selId?PROGETTI.find(p=>p.id===selId):null;
  const grouped = useMemo(()=>{
    const g={};
    SOGGETTI.filter(s=>s.tipo==="reale").forEach(s=>{g[s.id]={soggetto:s,progetti:PROGETTI.filter(p=>p.soggettoId===s.id)};});
    return Object.values(g);
  },[]);

  if(sel) {
    const soggetto = SOGGETTI.find(s=>s.id===sel.soggettoId);
    const bandiMatch = BANDI.map(b=>{const v=b.valutazioni.find(v=>v.progettoId===sel.id); return v?{...b,val:v}:null;}).filter(Boolean).sort((a,b)=>(b.val.score||0)-(a.val.score||0));
    const candidature = CANDIDATURE.filter(c=>c.progettoId===sel.id);

    return (
      <div>
        <PageHeader back={()=>{setSelId(null);setTab("opportunita");}} backLabel="Progetti" title={`🌟 ${sel.nome}`}
          subtitle={`${soggetto.nome} · ${sel.settore} · Completezza ${sel.completezza}%`}
          warning={!sel.costituita?"Non ancora costituita":null}>
          <div className="flex items-center gap-2"><ProgBar value={sel.completezza} className="w-24"/><span className="text-xs font-semibold text-slate-600">{sel.completezza}%</span></div>
          <button className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700">Avvia scansione ▶</button>
        </PageHeader>
        <div className="p-6">
          <Tabs active={tab} onChange={setTab} tabs={[
            {id:"opportunita",label:"Opportunità",count:bandiMatch.length},
            {id:"candidature",label:"Candidature",count:candidature.length},
            {id:"profilo",label:"Profilo"},
            {id:"analisi",label:"Analisi"},
          ]}/>

          {tab==="opportunita"&&(
            <div>
              <div className="grid grid-cols-4 gap-3 mb-4">
                <div className="bg-blue-50 rounded-lg p-3 text-center"><p className="text-2xl font-bold text-blue-700">{bandiMatch.length}</p><p className="text-xs text-blue-500">Bandi compatibili</p></div>
                <div className="bg-emerald-50 rounded-lg p-3 text-center"><p className="text-2xl font-bold text-emerald-700">{bandiMatch.filter(b=>b.val.idoneo).length}</p><p className="text-xs text-emerald-500">Idonei</p></div>
                <div className="bg-orange-50 rounded-lg p-3 text-center"><p className="text-2xl font-bold text-orange-700">{sel.scoreMedio}</p><p className="text-xs text-orange-500">Score medio</p></div>
                <div className="bg-violet-50 rounded-lg p-3 text-center"><p className="text-2xl font-bold text-violet-700">{bandiMatch.length>0?daysUntil(bandiMatch.sort((a,b)=>daysUntil(a.scadenza)-daysUntil(b.scadenza))[0].scadenza)+"gg":"—"}</p><p className="text-xs text-violet-500">Prossima scadenza</p></div>
              </div>
              <Card className="overflow-hidden">
                <table className="w-full text-sm">
                  <thead><tr className="text-left text-xs text-slate-400 border-b border-slate-100">
                    <th className="px-4 py-2">Titolo</th><th className="px-4 py-2">Ente</th><th className="px-4 py-2">Score</th><th className="px-4 py-2">Idoneità</th><th className="px-4 py-2">Budget</th><th className="px-4 py-2">Scadenza</th><th className="px-4 py-2">Tipo</th><th className="px-4 py-2"></th>
                  </tr></thead>
                  <tbody>{bandiMatch.map(b=>(
                    <tr key={b.id} className="border-b border-slate-50 hover:bg-slate-50 cursor-pointer" onClick={()=>nav("bando",b.id)}>
                      <td className="px-4 py-3 font-medium text-slate-800">{b.titolo}</td>
                      <td className="px-4 py-3 text-slate-600">{b.ente}</td>
                      <td className="px-4 py-3"><ScoreBadge score={b.val.score}/></td>
                      <td className="px-4 py-3">{b.val.idoneo?<span className="text-emerald-600 text-xs font-semibold">✅ Idoneo</span>:<span className="text-red-600 text-xs font-semibold">🔒 {b.val.hardStop}</span>}</td>
                      <td className="px-4 py-3 text-slate-600">{b.budget}</td>
                      <td className="px-4 py-3"><UrgenzaBadge giorni={daysUntil(b.scadenza)}/></td>
                      <td className="px-4 py-3"><TipoBadge tipo={b.tipo} perc={b.tipoPerc}/></td>
                      <td className="px-4 py-3">{b.val.idoneo&&<button className="text-xs text-blue-600 hover:underline whitespace-nowrap" onClick={e=>{e.stopPropagation();}}>Crea candidatura</button>}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </Card>
            </div>
          )}

          {tab==="candidature"&&(
            <Card className="overflow-hidden">
              {candidature.length===0?<EmptyState text="Nessuna candidatura attiva" action="Vai alla tab Opportunità →" onAction={()=>setTab("opportunita")}/>:
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs text-slate-400 border-b border-slate-100">
                  <th className="px-4 py-2">Bando</th><th className="px-4 py-2">Soggetto</th><th className="px-4 py-2">Score</th><th className="px-4 py-2">Stato</th><th className="px-4 py-2">Scadenza</th><th className="px-4 py-2">Progresso</th>
                </tr></thead>
                <tbody>{candidature.map(c=>{
                  const b=BANDI.find(x=>x.id===c.bandoId); const s=SOGGETTI.find(x=>x.id===c.soggettoId);
                  return (
                    <tr key={c.id} className="border-b border-slate-50 hover:bg-slate-50 cursor-pointer" onClick={()=>nav("candidatura",c.id)}>
                      <td className="px-4 py-3 font-medium text-slate-800">{b.titolo}</td>
                      <td className="px-4 py-3 text-slate-600">{s.nome}</td>
                      <td className="px-4 py-3"><ScoreBadge score={c.score}/></td>
                      <td className="px-4 py-3"><StatoBadge stato={c.stato}/></td>
                      <td className="px-4 py-3"><UrgenzaBadge giorni={daysUntil(b.scadenza)}/></td>
                      <td className="px-4 py-3"><div className="flex items-center gap-2"><ProgBar value={c.progresso} className="w-16"/><span className="text-xs text-slate-500">{c.progresso}%</span></div></td>
                    </tr>
                  );
                })}</tbody>
              </table>}
            </Card>
          )}

          {tab==="profilo"&&(
            <div className="grid grid-cols-3 gap-6">
              <div className="col-span-2 space-y-4">
                <Card className="p-4 space-y-3">
                  <h3 className="font-semibold text-sm text-slate-800">Identità</h3>
                  <div><label className="text-xs text-slate-500">Nome progetto</label><input className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm" defaultValue={sel.nome}/></div>
                  <div><label className="text-xs text-slate-500">Descrizione breve <span className="text-slate-400">({sel.descBreve.length}/140)</span></label><textarea className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm h-16" defaultValue={sel.descBreve}/></div>
                  <div className="grid grid-cols-2 gap-3">
                    <div><label className="text-xs text-slate-500">Settore</label><select className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm"><option>{sel.settore}</option></select></div>
                    <div><label className="text-xs text-slate-500">Costituita</label><div className="mt-1 flex items-center gap-2"><input type="checkbox" defaultChecked={sel.costituita}/><span className="text-sm">{sel.costituita?"Sì":"No"}</span></div></div>
                  </div>
                </Card>
                <Card className="p-4 space-y-3">
                  <h3 className="font-semibold text-sm text-slate-800">Aspetti economici</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <div><label className="text-xs text-slate-500">Budget min (€)</label><input className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm" defaultValue={sel.budgetMin}/></div>
                    <div><label className="text-xs text-slate-500">Budget max (€)</label><input className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm" defaultValue={sel.budgetMax}/></div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div><label className="text-xs text-slate-500">Cofinanziamento %</label><input className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm" defaultValue={sel.cofiPerc}/></div>
                    <div><label className="text-xs text-slate-500">Fonte</label><input className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm" defaultValue="Mezzi propri"/></div>
                  </div>
                </Card>
                <Card className="p-4">
                  <h3 className="font-semibold text-sm text-slate-800 mb-2">Soggetto applicante</h3>
                  <div className="bg-slate-50 rounded-lg p-3">
                    <p className="text-sm font-medium">{soggetto.nome}</p>
                    <p className="text-xs text-slate-500">{soggetto.forma} · {soggetto.regime} · ATECO {soggetto.ateco} · {soggetto.dipendenti} dip.</p>
                    <div className="flex gap-4 mt-2">
                      <div>{soggetto.hardStops.slice(0,2).map((h,i)=><p key={i} className="text-xs text-red-600">❌ {h.label}</p>)}{soggetto.hardStops.length>2&&<p className="text-xs text-slate-400">+{soggetto.hardStops.length-2} altri</p>}</div>
                      <div>{soggetto.vantaggi.slice(0,2).map((v,i)=><p key={i} className="text-xs text-emerald-600">✅ {v.label}</p>)}</div>
                    </div>
                    <button className="text-xs text-blue-600 hover:underline mt-2" onClick={()=>nav("soggetto",soggetto.id)}>Vai al soggetto →</button>
                  </div>
                </Card>
                {/* Accordion sections placeholder */}
                {["Descrizione estesa","Partner previsti","Piano di lavoro","KPI","Punti di forza"].map(s=>(
                  <Card key={s} className="p-4">
                    <button className="w-full flex items-center justify-between text-sm font-semibold text-slate-700 hover:text-slate-900">
                      <span>{s}</span><span className="text-slate-400">▸</span>
                    </button>
                  </Card>
                ))}
              </div>
              <div>
                <Card className="p-4 sticky top-24">
                  <h3 className="font-semibold text-sm text-slate-800 mb-3">Checklist completezza</h3>
                  <div className="space-y-2">
                    {(sel.id===2?[
                      {l:"Descrizione breve",ok:true},{l:"Settore",ok:true},{l:"Keywords",ok:true},{l:"Comuni target",ok:true},{l:"Costituita",ok:false},{l:"Descrizione estesa",ok:false},{l:"Budget",ok:true},{l:"Cofinanziamento",ok:true},{l:"Partner previsti",ok:true},{l:"Piano di lavoro",ok:true},{l:"KPI",ok:true},{l:"Punti di forza",ok:false}
                    ]:[
                      {l:"Descrizione breve",ok:true},{l:"Settore",ok:true},{l:"Keywords",ok:true},{l:"Comuni target",ok:true},{l:"Costituita",ok:true},{l:"Descrizione estesa",ok:false},{l:"Budget",ok:true},{l:"Cofinanziamento",ok:true},{l:"Partner previsti",ok:false},{l:"Piano di lavoro",ok:false},{l:"KPI",ok:false},{l:"Punti di forza",ok:false}
                    ]).map((c,i)=>(
                      <div key={i} className={`flex items-center gap-2 text-xs ${c.ok?"text-emerald-600":"text-slate-500"}`}>
                        {c.ok?"✅":"⬜"} {c.l}
                      </div>
                    ))}
                  </div>
                </Card>
              </div>
            </div>
          )}

          {tab==="analisi"&&(
            <div className="space-y-4">
              <Card className="p-4">
                <h3 className="font-semibold text-sm text-slate-800 mb-3">Gap Analysis Aggregata</h3>
                <div className="space-y-2">
                  {[
                    {label:"Forma giuridica: SRL richiesta",bandi:34,gravita:"Critico",fonte:"SOGGETTO"},
                    {label:"Cofinanziamento ≥ 30%",bandi:22,gravita:"Medio",fonte:"PROGETTO"},
                    {label:"Fatturato minimo 50-100k",bandi:18,gravita:"Critico",fonte:"SOGGETTO"},
                    {label:"Sede operativa nel comune",bandi:14,gravita:"Risolvibile",fonte:"PROGETTO"},
                    {label:"Business plan triennale",bandi:10,gravita:"Medio",fonte:"PROGETTO"},
                    {label:"Dipendenti minimo",bandi:8,gravita:"Critico",fonte:"SOGGETTO"},
                  ].map((g,i)=>(
                    <div key={i} className="flex items-center gap-3 py-2 border-b border-slate-50">
                      <span className="text-sm text-slate-700 flex-1">{g.label}</span>
                      <span className="text-xs text-slate-400 w-20 text-right">{g.bandi} bandi</span>
                      <Badge color={g.gravita==="Critico"?"red":g.gravita==="Medio"?"orange":"green"} small>{g.gravita}</Badge>
                      <Badge color={g.fonte==="SOGGETTO"?"orange":"blue"} small>← {g.fonte}</Badge>
                    </div>
                  ))}
                </div>
              </Card>
              <Card className="p-4">
                <h3 className="font-semibold text-sm text-slate-800 mb-3">Note strategiche</h3>
                <div className="space-y-2 mb-3">
                  <div className="p-3 bg-amber-50 rounded-lg border border-amber-100">
                    <p className="text-sm text-slate-700">Costituire SRL per sbloccare 34 bandi — valutare entro Q2 2026</p>
                    <p className="text-xs text-slate-400 mt-1">16/03/2026 · Decisione</p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                    <p className="text-sm text-slate-700">Verificare partnership con Comune Roccapalumba per FESR</p>
                    <p className="text-xs text-slate-400 mt-1">14/03/2026 · Nota</p>
                  </div>
                </div>
                <div className="flex gap-2"><textarea className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="Aggiungi nota..."/><button className="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">Salva</button></div>
              </Card>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Lista progetti raggruppata
  return (
    <div>
      <PageHeader title="Progetti" subtitle={`${PROGETTI.length} progetti · ${SOGGETTI.filter(s=>s.tipo==="reale").length} soggetti`}>
        <button className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700">+ Nuovo progetto</button>
      </PageHeader>
      <div className="p-6 space-y-4">
        {grouped.map(g=>(
          <Card key={g.soggetto.id} className="overflow-hidden">
            <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center gap-3">
              <span className="text-sm font-semibold text-slate-700">👤 {g.soggetto.nome}</span>
              <span className="text-xs text-slate-400">{g.soggetto.forma}</span>
              <span className="text-xs text-slate-400">· {g.progetti.length} progetti</span>
              {g.soggetto.hardStops.length>0&&<Badge color="red" small>{g.soggetto.hardStops.length} hard stop</Badge>}
            </div>
            {g.progetti.length===0?(
              <div className="px-4 py-6 text-sm text-slate-400 text-center">Nessun progetto. <button className="text-blue-600 hover:underline">Crea progetto →</button></div>
            ):(
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs text-slate-400 border-b border-slate-100">
                  <th className="px-4 py-2">Progetto</th><th className="px-4 py-2">Settore</th><th className="px-4 py-2">Completezza</th><th className="px-4 py-2">Bandi match</th><th className="px-4 py-2">Candidature</th><th className="px-4 py-2">Score medio</th>
                </tr></thead>
                <tbody>{g.progetti.map(p=>(
                  <tr key={p.id} className="border-b border-slate-50 hover:bg-slate-50 cursor-pointer" onClick={()=>setSelId(p.id)}>
                    <td className="px-4 py-3"><span className="font-medium text-slate-800">🌟 {p.nome}</span>{!p.costituita&&<span className="text-amber-500 text-xs ml-2">⚠️ non costituita</span>}</td>
                    <td className="px-4 py-3 text-slate-600">{p.settore}</td>
                    <td className="px-4 py-3"><div className="flex items-center gap-2"><ProgBar value={p.completezza} className="w-16"/><span className="text-xs text-slate-500">{p.completezza}%</span></div></td>
                    <td className="px-4 py-3 text-slate-700 font-medium">{p.bandiMatch}</td>
                    <td className="px-4 py-3 text-slate-700">{p.candidatureAttive}</td>
                    <td className="px-4 py-3"><ScoreBadge score={p.scoreMedio}/></td>
                  </tr>
                ))}</tbody>
              </table>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
};

// ──── BANDI ────
const BandiPage = ({nav,preselProgettoId=null}) => {
  const [selProg,setSelProg]=useState(preselProgettoId);
  const [selBandoId,setSelBandoId]=useState(null);
  const [bandoTab,setBandoTab]=useState("decisione");
  const [soloAperti,setSoloAperti]=useState(true);
  const selBando = selBandoId?BANDI.find(b=>b.id===selBandoId):null;

  if(selBando) {
    const val = selProg?selBando.valutazioni.find(v=>v.progettoId===selProg):null;
    const prog = selProg?PROGETTI.find(p=>p.id===selProg):null;
    const sogg = prog?SOGGETTI.find(s=>s.id===prog.soggettoId):null;
    const giorni = daysUntil(selBando.scadenza);
    return (
      <div>
        <PageHeader back={()=>{setSelBandoId(null);setBandoTab("decisione");}} backLabel="Bandi" title={selBando.titolo}
          subtitle={`${selBando.ente} · Scade ${selBando.scadenza} (${giorni}gg)${giorni<=14?" 🔴":""}`}>
          {val&&val.idoneo&&<button className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700">Crea candidatura ▶</button>}
        </PageHeader>
        <div className="px-6 pt-3">
          <div className="flex items-center gap-2 mb-3 text-sm">
            <span className="text-slate-500">Contesto:</span>
            <select className="px-2 py-1 border border-slate-200 rounded text-sm" value={selProg||""} onChange={e=>setSelProg(e.target.value?Number(e.target.value):null)}>
              <option value="">Nessun progetto</option>
              {PROGETTI.map(p=><option key={p.id} value={p.id}>{p.nome}</option>)}
            </select>
            {sogg&&<span className="text-xs text-slate-400">→ Soggetto: {sogg.nome}</span>}
          </div>
          {/* Decision strip */}
          <div className={`grid ${val?"grid-cols-6":"grid-cols-4"} gap-2 mb-4`}>
            {val&&<div className={`rounded-lg p-3 text-center ${val.idoneo?"bg-emerald-50 border border-emerald-200":"bg-red-50 border border-red-200"}`}><p className="text-xs text-slate-500">Idoneità</p><p className={`text-sm font-bold ${val.idoneo?"text-emerald-700":"text-red-700"}`}>{val.idoneo?"✅ Idoneo":"❌ Hard stop"}</p></div>}
            {val&&<div className="bg-slate-50 rounded-lg p-3 text-center border border-slate-200"><p className="text-xs text-slate-500">Score</p><ScoreBadge score={val.idoneo?val.score:null}/></div>}
            <div className={`rounded-lg p-3 text-center border ${giorni<=14?"bg-red-50 border-red-200":"bg-slate-50 border-slate-200"}`}><p className="text-xs text-slate-500">Scadenza</p><UrgenzaBadge giorni={giorni}/></div>
            <div className="bg-slate-50 rounded-lg p-3 text-center border border-slate-200"><p className="text-xs text-slate-500">Tipo</p><TipoBadge tipo={selBando.tipo} perc={selBando.tipoPerc}/></div>
            <div className="bg-slate-50 rounded-lg p-3 text-center border border-slate-200"><p className="text-xs text-slate-500">Budget</p><p className="text-sm font-bold text-slate-700">{selBando.budget}</p></div>
            {val&&<div className={`rounded-lg p-3 text-center border ${val.hardStop?"bg-red-50 border-red-200":"bg-slate-50 border-slate-200"}`}><p className="text-xs text-slate-500">Vincolo sogg.</p>{val.hardStop?<p className="text-xs font-semibold text-red-700">🔒 {val.hardStop}</p>:<p className="text-xs text-emerald-600">—</p>}</div>}
          </div>
        </div>
        <div className="px-6">
          <Tabs active={bandoTab} onChange={setBandoTab} tabs={[
            ...(val?[{id:"decisione",label:"Decisione rapida"}]:[]),
            {id:"dettaglio",label:"Dettaglio bando"},
            {id:"testo",label:"Testo & PDF"},
          ]}/>

          {bandoTab==="decisione"&&val&&(
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <Card className="p-4">
                  <h3 className="font-semibold text-sm text-emerald-700 mb-3">✅ PRO</h3>
                  {val.pro.map((p,i)=><div key={i} className="flex items-center gap-2 py-1"><span className="text-emerald-500">•</span><span className="text-sm text-slate-700">{p.l}</span><span className="text-xs text-emerald-600 font-medium">+{p.p}</span></div>)}
                </Card>
                <Card className="p-4">
                  <h3 className="font-semibold text-sm text-red-700 mb-3">❌ CONTRO</h3>
                  {val.contro.map((c,i)=><div key={i} className="flex items-center gap-2 py-1"><span className={c.t==="hard_stop"?"text-red-500":c.t==="yellow"?"text-amber-500":"text-slate-400"}>{c.t==="hard_stop"?"❌":c.t==="yellow"?"⚠️":"•"}</span><span className="text-sm text-slate-700">{c.l}</span></div>)}
                </Card>
              </div>
              {val.gaps.length>0&&(
                <Card className="p-4">
                  <h3 className="font-semibold text-sm text-amber-700 mb-3">⚠️ Gap da coprire</h3>
                  {val.gaps.map((g,i)=><div key={i} className="flex items-center gap-2 py-1"><span className="text-amber-500">⚠️</span><span className="text-sm text-slate-700">{g}</span></div>)}
                </Card>
              )}
              {val.idoneo&&(
                <button className="w-full py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition-colors">
                  Crea candidatura per "{prog.nome}" →
                </button>
              )}
            </div>
          )}

          {bandoTab==="dettaglio"&&(
            <Card className="p-4 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                {[["Portale",selBando.portale],["Ente",selBando.ente],["Scadenza",selBando.scadenza],["Budget",selBando.budget],["Tipo",`${selBando.tipo} ${selBando.tipoPerc}`],["Stato",selBando.stato]].map(([l,v])=>(
                  <div key={l}><p className="text-xs text-slate-500">{l}</p><p className="text-sm font-medium text-slate-700">{v}</p></div>
                ))}
              </div>
              <div><p className="text-xs text-slate-500 mb-1">URL fonte</p><a className="text-sm text-blue-600 hover:underline" href="#">{selBando.url||selBando.portale}</a></div>
            </Card>
          )}

          {bandoTab==="testo"&&(
            <Card className="p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-sm text-slate-800">Testo estratto dal PDF</h3>
                <button className="text-xs text-blue-600 hover:underline">Scarica PDF originale</button>
              </div>
              <div className="bg-slate-50 rounded-lg p-4 font-mono text-xs text-slate-600 leading-relaxed max-h-96 overflow-auto">
                [Testo estratto dal PDF del bando tramite Docling + Claude]<br/><br/>
                BANDO: {selBando.titolo}<br/>
                ENTE: {selBando.ente}<br/><br/>
                Art. 1 — Finalità e ambito di applicazione<br/>
                Il presente bando intende sostenere lo sviluppo di...<br/><br/>
                Art. 2 — Soggetti beneficiari<br/>
                Possono presentare domanda le imprese che...<br/><br/>
                Art. 3 — Interventi ammissibili<br/>
                Sono ammissibili gli investimenti in...<br/><br/>
                [... testo completo del bando ...]
              </div>
              <div className="mt-3 text-xs text-slate-400">Analizzato il 15/03/2026 · Modello: Claude Sonnet · Confidence: 94%</div>
            </Card>
          )}
        </div>
      </div>
    );
  }

  // Lista bandi
  const lista = BANDI.filter(b=>!soloAperti||b.stato==="aperto").map(b=>{
    const val = selProg?b.valutazioni.find(v=>v.progettoId===selProg):null;
    return {...b,val,giorni:daysUntil(b.scadenza)};
  }).sort((a,b)=>selProg?((b.val?.score||0)-(a.val?.score||0)):(a.giorni-b.giorni));

  return (
    <div>
      <PageHeader title="Bandi" subtitle={`${lista.length} bandi${soloAperti?" aperti":""}`}/>
      <div className="px-6 pt-3">
        <div className="flex items-center gap-4 mb-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-600 font-medium">Valuta per:</span>
            <select className="px-3 py-1.5 border border-slate-200 rounded-lg text-sm" value={selProg||""} onChange={e=>setSelProg(e.target.value?Number(e.target.value):null)}>
              <option value="">Nessun progetto</option>
              {PROGETTI.map(p=><option key={p.id} value={p.id}>{p.nome}</option>)}
            </select>
            {selProg&&<span className="text-xs text-slate-400">→ {SOGGETTI.find(s=>s.id===PROGETTI.find(p=>p.id===selProg)?.soggettoId)?.nome}</span>}
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <label className="flex items-center gap-1.5 text-sm text-slate-600"><input type="checkbox" checked={soloAperti} onChange={e=>setSoloAperti(e.target.checked)} className="rounded"/> Solo aperti</label>
          </div>
        </div>
        <Card className="overflow-hidden">
          {lista.length===0?<EmptyState text="Nessun bando trovato" action="Avvia scansione ▶"/>:
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-slate-400 border-b border-slate-100">
              <th className="px-4 py-2">Titolo</th><th className="px-4 py-2">Ente</th><th className="px-4 py-2">Score</th><th className="px-4 py-2">Idoneità</th><th className="px-4 py-2">Budget</th><th className="px-4 py-2">Scadenza</th><th className="px-4 py-2">Tipo</th><th className="px-4 py-2">Portale</th>
            </tr></thead>
            <tbody>{lista.map(b=>(
              <tr key={b.id} className="border-b border-slate-50 hover:bg-slate-50 cursor-pointer" onClick={()=>{setSelBandoId(b.id);setBandoTab(b.val?"decisione":"dettaglio");}}>
                <td className="px-4 py-3 font-medium text-slate-800 max-w-xs truncate">{b.titolo}</td>
                <td className="px-4 py-3 text-slate-600 text-xs">{b.ente}</td>
                <td className="px-4 py-3"><ScoreBadge score={b.val?.score??null}/></td>
                <td className="px-4 py-3">{b.val?(b.val.idoneo?<span className="text-emerald-600 text-xs">✅</span>:<span className="text-red-600 text-xs">🔒</span>):<span className="text-slate-300">—</span>}</td>
                <td className="px-4 py-3 text-slate-600 text-xs">{b.budget}</td>
                <td className="px-4 py-3"><UrgenzaBadge giorni={b.giorni}/></td>
                <td className="px-4 py-3"><TipoBadge tipo={b.tipo} perc={b.tipoPerc}/></td>
                <td className="px-4 py-3 text-xs text-slate-400">{b.portale}</td>
              </tr>
            ))}</tbody>
          </table>}
        </Card>
      </div>
    </div>
  );
};

// ──── CANDIDATURE ────
const CandidaturePage = ({nav,selId=null}) => {
  const [viewId,setViewId]=useState(selId);
  const [tab,setTab]=useState("valutazione");
  const [filtroStato,setFiltroStato]=useState("tutti");
  const cand = viewId?CANDIDATURE.find(c=>c.id===viewId):null;

  if(cand) {
    const bando=BANDI.find(b=>b.id===cand.bandoId); const prog=PROGETTI.find(p=>p.id===cand.progettoId); const sogg=SOGGETTI.find(s=>s.id===cand.soggettoId);
    const val=bando.valutazioni.find(v=>v.progettoId===cand.progettoId);
    const giorni=daysUntil(bando.scadenza);
    const checkDone=cand.checklist.filter(c=>c.done).length;
    return (
      <div>
        <PageHeader back={()=>{setViewId(null);setTab("valutazione");}} backLabel="Candidature"
          title={`📁 ${bando.titolo}`}
          subtitle={`${bando.ente} · Scade ${bando.scadenza} (${giorni}gg) · 🌟 ${prog.nome} · 👤 ${sogg.nome} (${sogg.forma})`}>
          <StatoBadge stato={cand.stato}/>
          <ScoreBadge score={cand.score}/>
          <TipoBadge tipo={bando.tipo} perc={bando.tipoPerc}/>
          <select className="px-2 py-1 border border-slate-200 rounded text-xs">
            <option>Cambia stato ▾</option>
            <option>→ Lavorazione</option><option>→ Pronta</option><option>→ Sospesa</option><option>→ Abbandonata</option>
          </select>
        </PageHeader>
        <div className="px-6 pt-2">
          <div className="flex items-center gap-3 mb-3 text-xs text-slate-500">
            <span>Progresso:</span><ProgBar value={cand.progresso} className="w-32"/><span className="font-medium">{cand.progresso}%</span>
            <span className="ml-4">Checklist: {checkDone}/{cand.checklist.length}</span>
          </div>
        </div>
        <div className="px-6">
          <Tabs active={tab} onChange={setTab} tabs={[
            {id:"valutazione",label:"Valutazione"},
            {id:"documenti",label:"Documenti",count:cand.documenti.length},
            {id:"checklist",label:"Checklist",count:`${checkDone}/${cand.checklist.length}`},
            {id:"note",label:"Note & Invio",count:cand.note.length},
          ]}/>

          {tab==="valutazione"&&val&&(
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <Card className="p-4">
                  <h3 className="font-semibold text-sm text-emerald-700 mb-3">✅ PRO</h3>
                  {val.pro.map((p,i)=><div key={i} className="flex items-center gap-2 py-1"><span className="text-emerald-500">•</span><span className="text-sm">{p.l}</span><span className="text-xs text-emerald-600">+{p.p}</span></div>)}
                </Card>
                <Card className="p-4">
                  <h3 className="font-semibold text-sm text-red-700 mb-3">❌ CONTRO</h3>
                  {val.contro.map((c,i)=><div key={i} className="flex items-center gap-2 py-1"><span>{c.t==="hard_stop"?"❌":c.t==="yellow"?"⚠️":"•"}</span><span className="text-sm">{c.l}</span></div>)}
                </Card>
              </div>
              <div className="text-xs text-slate-400"><button onClick={()=>nav("bando",bando.id)} className="text-blue-600 hover:underline">Vedi valutazione completa → Scheda bando</button></div>
            </div>
          )}

          {tab==="documenti"&&(
            <div className="space-y-4">
              <button className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700">▶ Genera documenti</button>
              {cand.documenti.length===0?<EmptyState icon="📄" text="Nessun documento generato" action="Genera documenti per iniziare"/>:
              <Card className="overflow-hidden">
                <table className="w-full text-sm">
                  <thead><tr className="text-left text-xs text-slate-400 border-b border-slate-100">
                    <th className="px-4 py-2">Documento</th><th className="px-4 py-2">Versione</th><th className="px-4 py-2">Stato</th><th className="px-4 py-2">Azioni</th>
                  </tr></thead>
                  <tbody>{cand.documenti.map((d,i)=>(
                    <tr key={i} className="border-b border-slate-50">
                      <td className="px-4 py-3 font-medium text-slate-800">{d.nome}</td>
                      <td className="px-4 py-3 text-slate-500">{d.versione}</td>
                      <td className="px-4 py-3"><Badge color={d.stato==="approvato"?"green":d.stato==="bozza"?"gray":"purple"}>{d.stato}</Badge></td>
                      <td className="px-4 py-3 flex gap-2">
                        <button className="text-xs text-blue-600 hover:underline">Anteprima</button>
                        <button className="text-xs text-blue-600 hover:underline">Scarica</button>
                        {d.stato==="bozza"&&<button className="text-xs text-emerald-600 hover:underline">Approva</button>}
                      </td>
                    </tr>
                  ))}</tbody>
                </table>
              </Card>}
              {cand.documenti.length>0&&<button className="text-xs text-blue-600 hover:underline">Scarica tutto ZIP</button>}
            </div>
          )}

          {tab==="checklist"&&(
            <div className="space-y-3">
              <div className="flex items-center gap-3 mb-2"><ProgBar value={(checkDone/cand.checklist.length)*100} className="w-40"/><span className="text-sm text-slate-600">{checkDone}/{cand.checklist.length} completati</span></div>
              <Card className="divide-y divide-slate-100">
                {cand.checklist.map((c,i)=>(
                  <div key={i} className="flex items-center gap-3 px-4 py-3">
                    <input type="checkbox" defaultChecked={c.done} className="rounded"/>
                    <span className={`text-sm flex-1 ${c.done?"text-slate-400 line-through":"text-slate-700"}`}>{c.label}</span>
                    <input className="text-xs border border-slate-200 rounded px-2 py-1 w-48" placeholder="Nota..." defaultValue={c.nota}/>
                  </div>
                ))}
              </Card>
              <button className="text-xs text-blue-600 hover:underline">+ Aggiungi requisito manuale</button>
            </div>
          )}

          {tab==="note"&&(
            <div className="space-y-4">
              <div className="flex gap-2"><textarea className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="Aggiungi nota..."/><button className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">Salva</button></div>
              <Card className="divide-y divide-slate-100">
                {cand.note.length===0?<div className="p-4 text-sm text-slate-400 text-center">Nessuna nota</div>:
                cand.note.map((n,i)=>(
                  <div key={i} className="px-4 py-3">
                    <div className="flex items-center gap-2"><Badge color={n.tipo==="decisione"?"orange":"gray"} small>{n.tipo}</Badge><span className="text-xs text-slate-400">{n.ts}</span></div>
                    <p className="text-sm text-slate-700 mt-1">{n.testo}</p>
                  </div>
                ))}
              </Card>
              {cand.stato==="pronta"&&(
                <Card className="p-4">
                  <h3 className="font-semibold text-sm text-slate-800 mb-3">📮 Invio candidatura</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <div><label className="text-xs text-slate-500">Data invio</label><input type="date" className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm"/></div>
                    <div><label className="text-xs text-slate-500">Protocollo</label><input className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="es: SS2026-00847"/></div>
                  </div>
                  <button className="mt-3 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-semibold hover:bg-emerald-700">Conferma invio →</button>
                </Card>
              )}
              {cand.dataInvio&&(
                <Card className="p-4">
                  <h3 className="font-semibold text-sm text-slate-800 mb-2">📮 Dati invio</h3>
                  <p className="text-sm text-slate-600">Data: {cand.dataInvio} · Protocollo: {cand.protocollo}</p>
                </Card>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Lista candidature
  const lista = CANDIDATURE.filter(c=>filtroStato==="tutti"||c.stato===filtroStato).map(c=>{
    const b=BANDI.find(x=>x.id===c.bandoId); const p=PROGETTI.find(x=>x.id===c.progettoId); const s=SOGGETTI.find(x=>x.id===c.soggettoId);
    return {...c,bando:b,progetto:p,soggetto:s,giorni:daysUntil(b.scadenza)};
  }).sort((a,b)=>a.giorni-b.giorni);

  return (
    <div>
      <PageHeader title="Candidature" subtitle={`${CANDIDATURE.length} totali`}/>
      <div className="px-6 pt-3">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-sm text-slate-600">Stato:</span>
          {["tutti","bozza","lavorazione","sospesa","pronta","inviata","abbandonata"].map(s=>(
            <button key={s} onClick={()=>setFiltroStato(s)} className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${filtroStato===s?"bg-blue-100 text-blue-700":"bg-slate-100 text-slate-500 hover:bg-slate-200"}`}>
              {s==="tutti"?"Tutti":s.charAt(0).toUpperCase()+s.slice(1)}
            </button>
          ))}
        </div>
        <Card className="overflow-hidden">
          {lista.length===0?<EmptyState text="Nessuna candidatura per questo filtro"/>:
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-slate-400 border-b border-slate-100">
              <th className="px-4 py-2">Bando</th><th className="px-4 py-2">Progetto</th><th className="px-4 py-2">Soggetto</th><th className="px-4 py-2">Score</th><th className="px-4 py-2">Stato</th><th className="px-4 py-2">Scadenza</th><th className="px-4 py-2">Progresso</th>
            </tr></thead>
            <tbody>{lista.map(c=>(
              <tr key={c.id} className="border-b border-slate-50 hover:bg-slate-50 cursor-pointer" onClick={()=>setViewId(c.id)}>
                <td className="px-4 py-3 font-medium text-slate-800 max-w-xs truncate">{c.bando.titolo}</td>
                <td className="px-4 py-3 text-slate-600">{c.progetto.nome}</td>
                <td className="px-4 py-3 text-slate-600 text-xs">{c.soggetto.nome}</td>
                <td className="px-4 py-3"><ScoreBadge score={c.score}/></td>
                <td className="px-4 py-3"><StatoBadge stato={c.stato}/></td>
                <td className="px-4 py-3"><UrgenzaBadge giorni={c.giorni}/></td>
                <td className="px-4 py-3"><div className="flex items-center gap-2"><ProgBar value={c.progresso} className="w-16"/><span className="text-xs text-slate-500">{c.progresso}%</span></div></td>
              </tr>
            ))}</tbody>
          </table>}
        </Card>
      </div>
    </div>
  );
};

// ──── PIPELINE ────
const PipelinePage = () => (
  <div>
    <PageHeader title="Pipeline" subtitle="Gestione scansioni bandi"/>
    <div className="p-6 space-y-4">
      <Card className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-500">Ultima scansione</p>
            <p className="text-lg font-bold text-slate-800">19/03/2026 14:30</p>
            <p className="text-sm text-emerald-600 mt-1">✅ Completata · Durata: 4m 32s · 12 bandi trovati (4 nuovi)</p>
          </div>
          <button className="px-4 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700">▶ Avvia nuova scansione</button>
        </div>
      </Card>
      <Card className="overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100"><h3 className="font-semibold text-sm text-slate-800">Storico scansioni</h3></div>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-slate-400 border-b border-slate-100">
            <th className="px-4 py-2">Data/ora</th><th className="px-4 py-2">Stato</th><th className="px-4 py-2">Durata</th><th className="px-4 py-2">Bandi trovati</th><th className="px-4 py-2">Nuovi</th><th className="px-4 py-2">Errori</th>
          </tr></thead>
          <tbody>{SCANSIONI.map((s,i)=>(
            <tr key={i} className="border-b border-slate-50">
              <td className="px-4 py-3 text-slate-700">{s.data}</td>
              <td className="px-4 py-3">{s.stato==="success"?<span className="text-emerald-600">✅</span>:s.stato==="failed"?<span className="text-red-500">❌</span>:<span className="text-blue-500">🔄</span>}</td>
              <td className="px-4 py-3 text-slate-500">{s.durata}</td>
              <td className="px-4 py-3 text-slate-700 font-medium">{s.trovati}</td>
              <td className="px-4 py-3 text-slate-600">{s.nuovi}</td>
              <td className="px-4 py-3">{s.errori>0?<span className="text-red-500 font-medium">{s.errori}</span>:<span className="text-slate-300">—</span>}</td>
            </tr>
          ))}</tbody>
        </table>
      </Card>
    </div>
  </div>
);

/* ══════════════════════════════════════════════════════════════
   MAIN APP
   ══════════════════════════════════════════════════════════════ */

const SIDEBAR_ITEMS = [
  {id:"dashboard",icon:"📊",label:"Dashboard"},
  {id:"soggetti",icon:"👤",label:"Soggetti"},
  {id:"progetti",icon:"🌟",label:"Progetti"},
  {id:"bandi",icon:"📋",label:"Bandi"},
  {id:"candidature",icon:"📁",label:"Candidature"},
  {id:"pipeline",icon:"⚙️",label:"Pipeline"},
];

export default function App() {
  const [page,setPage]=useState("dashboard");
  const [detailId,setDetailId]=useState(null);

  const nav = useCallback((target,id=null)=>{
    setPage(target);
    setDetailId(id);
  },[]);

  const renderPage = () => {
    switch(page) {
      case "dashboard": return <DashboardPage nav={nav}/>;
      case "soggetti": case "soggetto": return <SoggettiPage nav={nav}/>;
      case "progetti": case "progetto": return <ProgettiPage nav={nav}/>;
      case "bandi": case "bando": return <BandiPage nav={nav}/>;
      case "candidature": case "candidatura": return <CandidaturePage nav={nav} selId={detailId}/>;
      case "pipeline": return <PipelinePage/>;
      default: return <DashboardPage nav={nav}/>;
    }
  };

  return (
    <div className="flex h-screen bg-slate-50" style={{fontFamily:"'DM Sans',system-ui,sans-serif"}}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet"/>
      {/* Sidebar */}
      <aside className="w-56 bg-slate-900 text-white flex flex-col shrink-0">
        <div className="px-4 py-5 border-b border-slate-700">
          <h1 className="text-base font-bold tracking-tight">🔍 Tool Bandi</h1>
          <p className="text-[10px] text-slate-400 mt-0.5">Gestione bandi pubblici</p>
        </div>
        <nav className="flex-1 py-2">
          {SIDEBAR_ITEMS.map(item=>{
            const isActive = page===item.id || page===item.id.slice(0,-1);
            return (
              <button key={item.id} onClick={()=>{setPage(item.id);setDetailId(null);}}
                className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${isActive?"bg-blue-600/20 text-blue-300 border-r-2 border-blue-400":"text-slate-400 hover:bg-slate-800 hover:text-slate-200"}`}>
                <span className="text-base">{item.icon}</span>
                <span className="font-medium">{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="p-4 border-t border-slate-700">
          <p className="text-[10px] text-slate-500">v0.1 — Mockup UI</p>
        </div>
      </aside>
      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {renderPage()}
      </main>
    </div>
  );
}

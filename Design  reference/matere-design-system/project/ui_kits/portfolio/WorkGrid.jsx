(function() {
  const { useState } = React;

  const PROJECTS = [
    {
      id: 'atardecer', tag: 'APP', year: '2025', featured: true,
      bg: '#b8491f',
      title: { es: 'Atardecer UI Kit', en: 'Atardecer UI Kit' },
      desc:  { es: 'Paleta y componentes cálidos para apps de lectura.', en: 'Warm palette and components for reading apps.' },
      sprite: [[0,0,64,40,'#b8491f'],[0,24,64,4,'#7a2e15'],[0,28,64,4,'#5a2e15'],[0,32,64,8,'#3d1f10'],[4,8,4,4,'#f7e4c9'],[16,6,4,4,'#fad98a'],[40,10,4,4,'#f0c59a'],[52,4,4,4,'#e8a76b'],[12,18,8,4,'#1a0f08'],[36,20,12,4,'#1a0f08'],[24,32,8,4,'#c79828'],[48,30,12,4,'#d97a3c']],
    },
    {
      id: 'pixeljournal', tag: 'WEB', year: '2025',
      bg: '#241509',
      title: { es: 'Pixel Journal', en: 'Pixel Journal' },
      desc:  { es: 'Diario con retícula pixel y tipografía cálida.', en: 'Journal with pixel grid and warm typography.' },
      sprite: [[0,0,64,40,'#241509'],[4,4,56,32,'#3d1f10'],[8,8,48,2,'#6b4423'],[8,14,40,2,'#6b4423'],[8,20,44,2,'#6b4423'],[8,26,32,2,'#6b4423'],[48,28,8,4,'#b8491f']],
    },
    {
      id: 'ember-shop', tag: 'SHOP', year: '2024',
      bg: '#3d1f10',
      title: { es: 'Ember Shop', en: 'Ember Shop' },
      desc:  { es: 'E-commerce de cerámica artesanal.', en: 'Handmade ceramics e-commerce.' },
      sprite: [[0,0,64,40,'#3d1f10'],[10,8,12,16,'#c79828'],[26,12,12,12,'#b8491f'],[42,10,14,14,'#9c3a1a'],[10,28,46,2,'#5a2e15'],[12,24,8,2,'#1a0f08'],[28,22,8,2,'#1a0f08'],[44,22,10,2,'#1a0f08']],
    },
    {
      id: 'crt-tools', tag: 'TOOL', year: '2024',
      bg: '#1a0f08',
      title: { es: 'CRT Tools', en: 'CRT Tools' },
      desc:  { es: 'Dashboard retro para monitoreo de builds.', en: 'Retro dashboard for build monitoring.' },
      sprite: [[0,0,64,40,'#1a0f08'],[4,4,28,16,'#3d1f10'],[34,4,26,16,'#3d1f10'],[4,22,56,14,'#3d1f10'],[6,8,16,2,'#b8491f'],[6,12,10,2,'#d97a3c'],[36,8,10,2,'#7a9a4a'],[36,12,16,2,'#fad98a'],[6,26,40,2,'#c79828'],[6,30,28,2,'#b8491f']],
    },
    {
      id: 'sage-garden', tag: 'APP', year: '2023',
      bg: '#3a3a22',
      title: { es: 'Sage Garden', en: 'Sage Garden' },
      desc:  { es: 'Tracker de plantas con recordatorios suaves.', en: 'Plant tracker with gentle reminders.' },
      sprite: [[0,0,64,40,'#3a3a22'],[8,20,8,16,'#5a2e15'],[6,14,12,6,'#6b6a3a'],[10,10,8,6,'#9a9966'],[28,24,6,12,'#5a2e15'],[26,16,10,8,'#9a9966'],[46,22,8,14,'#5a2e15'],[44,14,12,8,'#6b6a3a'],[0,36,64,4,'#241509']],
    },
    {
      id: 'marca-type', tag: 'TYPE', year: '2023',
      bg: '#f7e4c9',
      title: { es: 'Marca — pixel type', en: 'Marca — pixel type' },
      desc:  { es: 'Familia display pixel con 3 pesos.', en: 'Display pixel family, 3 weights.' },
      sprite: [[0,0,64,40,'#f7e4c9'],[4,8,4,24,'#1a0f08'],[10,8,4,24,'#1a0f08'],[8,8,4,4,'#1a0f08'],[12,8,4,4,'#1a0f08'],[14,14,4,4,'#1a0f08'],[20,12,4,20,'#b8491f'],[26,12,8,4,'#b8491f'],[26,20,6,4,'#b8491f'],[26,28,8,4,'#b8491f'],[38,8,4,24,'#1a0f08'],[42,8,10,4,'#1a0f08'],[42,18,8,4,'#1a0f08'],[42,28,10,4,'#1a0f08']],
    },
  ];

  const FILTERS = {
    es: [['all','Todos'], ['APP','Apps'], ['WEB','Web'], ['SHOP','Shop'], ['TOOL','Herramientas'], ['TYPE','Tipografía']],
    en: [['all','All'], ['APP','Apps'], ['WEB','Web'], ['SHOP','Shop'], ['TOOL','Tools'], ['TYPE','Type']],
  };

  window.WorkGrid = function WorkGrid({ lang }) {
    const [f, setF] = useState('all');
    const filtered = f === 'all' ? PROJECTS : PROJECTS.filter(p => p.tag === f);
    return (
      <section className="mtr-work">
        <header className="mtr-section__head">
          <div className="eyebrow">{lang==='es'?'SELECCIONADO · 2023–2026':'SELECTED · 2023–2026'}</div>
          <h2>{lang==='es'?'Trabajo':'Work'}</h2>
        </header>
        <div className="mtr-work__filters">
          {FILTERS[lang].map(([id, label]) => (
            <button key={id} className={'chip' + (f===id?' chip--on':'')} onClick={() => setF(id)}>{label}</button>
          ))}
        </div>
        <div className="mtr-work__grid">
          {filtered.map(p => <ProjectCard key={p.id} p={p} lang={lang}/>)}
        </div>
      </section>
    );
  };
})();

(function() {
  const { useState, useEffect } = React;

  const COPY = {
    es: {
      eyebrow: 'DISEÑO DE INTERFACES · 2026',
      h1: 'Interfaces con alma retro.',
      sub: 'Construyo productos digitales cálidos. Un píxel a la vez, con cuidado por el detalle y la tipografía.',
      cta1: 'Ver trabajo',
      cta2: 'Contáctame',
      sel1: 'Seleccionado',
      now: 'Disponible desde Abr · 2026',
    },
    en: {
      eyebrow: 'INTERFACE DESIGN · 2026',
      h1: 'Interfaces with a retro soul.',
      sub: 'I build warm digital products. One pixel at a time, with care for detail and typography.',
      cta1: 'See work',
      cta2: 'Contact me',
      sel1: 'Selected',
      now: 'Available from Apr · 2026',
    },
  };

  window.Hero = function Hero({ lang, goWork, goContact }) {
    const t = COPY[lang];
    return (
      <section className="mtr-hero grain crt">
        <div className="mtr-hero__inner">
          <div className="mtr-hero__eyebrow">{t.eyebrow}</div>
          <h1 className="mtr-hero__title">{t.h1}</h1>
          <p className="mtr-hero__sub">{t.sub}</p>
          <div className="mtr-hero__ctas">
            <button className="btn btn--primary" onClick={goWork}>{t.cta1}</button>
            <button className="btn btn--ghost" onClick={goContact}>{t.cta2}</button>
          </div>
          <div className="mtr-hero__meta">
            <span className="mtr-hero__pip"></span>
            <span>{t.now}</span>
          </div>
        </div>
        <div className="mtr-hero__sprite">
          <img src="../../assets/matere-mark-large.svg" width="220" height="220" className="pixelated"/>
        </div>
      </section>
    );
  };
})();

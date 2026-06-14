(function() {
  const COPY = {
    es: {
      eyebrow: 'SOBRE',
      h: 'Un diseñador, un píxel.',
      body: [
        'Soy un diseñador de interfaces obsesionado con el detalle. Mezclo la calidez del papel envejecido con la precisión del píxel y la claridad de la tipografía moderna.',
        'He trabajado con estudios, startups y equipos solitarios construyendo productos cálidos que no se sienten tecnológicos — se sienten hechos a mano.',
      ],
      skillsT: 'Habilidades',
      skills: [
        ['Interfaz & sistemas', 92],
        ['Pixel art & iconografía', 85],
        ['Tipografía', 78],
        ['Front-end (HTML/CSS)', 70],
      ],
      nowT: 'Ahora',
      now: 'Construyendo Matere. Leyendo sobre fotografía analógica. Escuchando vinilos.',
    },
    en: {
      eyebrow: 'ABOUT',
      h: 'One designer, one pixel.',
      body: [
        "I'm an interface designer obsessed with detail. I mix the warmth of aged paper with pixel precision and the clarity of modern typography.",
        "I've worked with studios, startups, and solo teams building warm products that don't feel tech — they feel handmade.",
      ],
      skillsT: 'Skills',
      skills: [
        ['Interface & systems', 92],
        ['Pixel art & icons', 85],
        ['Typography', 78],
        ['Front-end (HTML/CSS)', 70],
      ],
      nowT: 'Now',
      now: 'Building Matere. Reading about analog photography. Listening to vinyl.',
    },
  };

  window.AboutPanel = function AboutPanel({ lang }) {
    const t = COPY[lang];
    return (
      <section className="mtr-about">
        <div className="mtr-about__paper grain">
          <div className="eyebrow" style={{color:'var(--ember-500)'}}>{t.eyebrow}</div>
          <h2 className="mtr-about__h">{t.h}</h2>
          {t.body.map((p, i) => <p key={i} className="mtr-about__p">{p}</p>)}
        </div>
        <aside className="mtr-about__side">
          <h3 className="mtr-about__sideH">{t.skillsT}</h3>
          <div className="mtr-about__bars">
            {t.skills.map(([label, v]) => (
              <div key={label} className="mtr-bar">
                <div className="mtr-bar__row"><span>{label}</span><span>{v}</span></div>
                <div className="mtr-bar__track"><div className="mtr-bar__fill" style={{width: v+'%'}}/></div>
              </div>
            ))}
          </div>
          <div className="mtr-about__now">
            <div className="eyebrow">{t.nowT}</div>
            <p>{t.now}</p>
          </div>
        </aside>
      </section>
    );
  };
})();

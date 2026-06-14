/* Nav */
(function() {
  const { useState } = React;

  window.Nav = function Nav({ section, setSection, lang, setLang }) {
    const items = [
      { id: 'home', es: 'Inicio', en: 'Home' },
      { id: 'work', es: 'Trabajo', en: 'Work' },
      { id: 'about', es: 'Sobre', en: 'About' },
      { id: 'contact', es: 'Contacto', en: 'Contact' },
    ];
    return (
      <header className="mtr-nav">
        <div className="mtr-nav__brand" onClick={() => setSection('home')}>
          <img src="../../assets/matere-mark.svg" width="32" height="32" className="pixelated" />
          <span className="mtr-nav__word">MATERE</span>
        </div>
        <nav className="mtr-nav__links">
          {items.map(it => (
            <button
              key={it.id}
              className={'mtr-nav__link' + (section === it.id ? ' is-active' : '')}
              onClick={() => setSection(it.id)}
            >
              {it[lang]}
            </button>
          ))}
        </nav>
        <div className="mtr-nav__lang">
          <button className={lang==='es' ? 'on':''} onClick={() => setLang('es')}>ES</button>
          <span>/</span>
          <button className={lang==='en' ? 'on':''} onClick={() => setLang('en')}>EN</button>
        </div>
      </header>
    );
  };
})();

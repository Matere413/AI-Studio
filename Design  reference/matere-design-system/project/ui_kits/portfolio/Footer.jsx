(function() {
  window.Footer = function Footer({ lang }) {
    return (
      <footer className="mtr-foot">
        <div className="mtr-foot__l">
          <img src="../../assets/matere-mark.svg" width="24" height="24" className="pixelated"/>
          <span className="mtr-foot__word">MATERE · 2026</span>
        </div>
        <div className="mtr-foot__r">
          <span>{lang==='es'?'Hecho un píxel a la vez':'Made one pixel at a time'}</span>
          <span className="mtr-foot__dot">●</span>
          <a href="#">rss</a>
          <a href="#">colophon</a>
        </div>
      </footer>
    );
  };
})();

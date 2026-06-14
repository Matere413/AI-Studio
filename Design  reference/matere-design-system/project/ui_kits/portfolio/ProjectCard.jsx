(function() {
  window.ProjectCard = function ProjectCard({ p, lang }) {
    return (
      <article className={'mtr-proj ' + (p.featured ? 'mtr-proj--feat' : '')}>
        <div className="mtr-proj__thumb" style={{background: p.bg}}>
          {/* simple pixel pattern composition */}
          <svg viewBox="0 0 64 40" shapeRendering="crispEdges" width="100%" height="100%">
            {p.sprite.map((rect, i) => (
              <rect key={i} x={rect[0]} y={rect[1]} width={rect[2]} height={rect[3]} fill={rect[4]}/>
            ))}
          </svg>
        </div>
        <div className="mtr-proj__body">
          <div className="mtr-proj__meta">
            <span className="mtr-proj__tag">{p.tag}</span>
            <span className="mtr-proj__year">{p.year}</span>
          </div>
          <h3 className="mtr-proj__title">{p.title[lang]}</h3>
          <p className="mtr-proj__desc">{p.desc[lang]}</p>
        </div>
      </article>
    );
  };
})();

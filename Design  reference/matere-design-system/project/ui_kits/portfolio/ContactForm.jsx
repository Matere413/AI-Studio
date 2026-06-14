(function() {
  const { useState } = React;

  const COPY = {
    es: {
      eyebrow: 'CONTACTO',
      h: 'Escríbeme.',
      prompt: 'matere:~ $',
      name: 'tu-nombre',
      email: 'tu@email',
      msg: 'cuéntame algo...',
      send: 'ENVIAR',
      sent: '✓ Mensaje enviado. Responderé pronto.',
      or: 'O por aquí:',
    },
    en: {
      eyebrow: 'CONTACT',
      h: 'Drop a line.',
      prompt: 'matere:~ $',
      name: 'your-name',
      email: 'you@email',
      msg: 'tell me something...',
      send: 'SEND',
      sent: '✓ Sent. Will reply soon.',
      or: 'Or here:',
    },
  };

  window.ContactForm = function ContactForm({ lang }) {
    const t = COPY[lang];
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [msg, setMsg] = useState('');
    const [sent, setSent] = useState(false);
    const [focus, setFocus] = useState('name');

    const submit = (e) => { e.preventDefault(); setSent(true); };

    return (
      <section className="mtr-contact">
        <header className="mtr-section__head">
          <div className="eyebrow">{t.eyebrow}</div>
          <h2>{t.h}</h2>
        </header>
        <div className="mtr-term crt">
          <div className="mtr-term__bar">
            <span className="mtr-term__dot"></span>
            <span className="mtr-term__dot"></span>
            <span className="mtr-term__dot"></span>
            <span className="mtr-term__title">~/matere/contact</span>
          </div>
          {sent ? (
            <div className="mtr-term__body">
              <div className="mtr-term__line"><span className="mtr-term__prompt">{t.prompt}</span> send --to matere</div>
              <div className="mtr-term__line mtr-term__ok">{t.sent}</div>
              <div className="mtr-term__line"><span className="mtr-term__prompt">{t.prompt}</span><span className="cursor"></span></div>
            </div>
          ) : (
            <form className="mtr-term__body" onSubmit={submit}>
              <label className="mtr-term__line">
                <span className="mtr-term__prompt">{t.prompt}</span>
                <span className="mtr-term__k">name =</span>
                <input className="mtr-term__in" placeholder={t.name} value={name}
                       onChange={e=>setName(e.target.value)} onFocus={()=>setFocus('name')}/>
                {focus==='name' && !name && <span className="cursor"></span>}
              </label>
              <label className="mtr-term__line">
                <span className="mtr-term__prompt">{t.prompt}</span>
                <span className="mtr-term__k">email =</span>
                <input className="mtr-term__in" placeholder={t.email} value={email}
                       onChange={e=>setEmail(e.target.value)} onFocus={()=>setFocus('email')}/>
                {focus==='email' && !email && <span className="cursor"></span>}
              </label>
              <label className="mtr-term__line mtr-term__line--multi">
                <span className="mtr-term__prompt">{t.prompt}</span>
                <span className="mtr-term__k">message =</span>
                <textarea className="mtr-term__ta" rows="3" placeholder={t.msg} value={msg}
                       onChange={e=>setMsg(e.target.value)} onFocus={()=>setFocus('msg')}/>
              </label>
              <div className="mtr-term__line" style={{justifyContent:'flex-end'}}>
                <button className="btn btn--primary" type="submit">{t.send}</button>
              </div>
            </form>
          )}
        </div>
        <div className="mtr-contact__aside">
          <div className="eyebrow" style={{color:'var(--fg-muted)'}}>{t.or}</div>
          <div className="mtr-contact__links">
            <a href="#">github.com/matere</a>
            <a href="#">@matere</a>
            <a href="#">hola@matere.studio</a>
          </div>
        </div>
      </section>
    );
  };
})();

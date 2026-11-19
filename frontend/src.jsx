import React,{useState,useEffect} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

async function api(path, body) {
  const res = await fetch('/api/'+path, body===undefined ? {} : {
    method:'POST', headers:{'Content-Type':'application/json'},body:JSON.stringify(body)
  });
  const data = await res.json();
  if(!res.ok) throw Error(typeof data.detail==='string'?data.detail:'Проверьте введённые значения');
  return data;
}

function OfferField() {
  const listId = React.useId();
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(null);
  const [matches, setMatches] = useState([]);
  const [error, setError] = useState('');
  const label = offer => offer.name + ' #' + offer.id;

  useEffect(() => {
    if (selected || !query.trim()) return;
    let current = true;
    const timer = setTimeout(async () => {
      try {
        const offers = await api('offers?q=' + encodeURIComponent(query.trim()));
        if (current) setMatches(offers);
      } catch (err) {
        if (current) setError(err.message);
      }
    }, 250);
    return () => { current = false; clearTimeout(timer); };
  }, [query, selected]);

  return <label>Оффер
    <input required list={listId} placeholder="ID или название оффера"
      value={query} onChange={event => {
        const value = event.target.value;
        const offer = matches.find(item => label(item) === value);
        event.target.setCustomValidity(offer || !value ? '' : 'Выберите оффер из списка');
        setSelected(offer || null);
        setQuery(value);
        setMatches([]);
        setError('');
      }}/>
    <datalist id={listId}>{matches.map(offer =>
      <option key={offer.id} value={label(offer)}/>)}</datalist>
    <input type="hidden" name="offer_id" value={selected?.id ?? ''}/>
    {error && <small role="alert">{error}</small>}
  </label>;
}

function Stream({s, run, update}) {
  const [searchKey, resetSearch] = useState(0);
  const [percent,setPercent]=useState({});
  const action=(op,id,extra={})=>run(async()=>{
    update(await api('streams/'+s.id+'/offers/'+op,{offer_id:id,...extra}));
    setPercent({});
    if (op === 'add') resetSearch(key => key + 1);
  });
  return <article className={s.dirty?'dirty':''}><h2>{s.name} <small>#{s.id}</small></h2>
    {s.dirty && <p>Есть неопубликованные изменения</p>}
    {!!s.offers.length && <><div className="table-scroll"><table><thead><tr><th>Оффер</th><th>Доля</th><th>Закрепление</th><th></th></tr></thead><tbody>
    {s.offers.map(r=><tr key={r.id} className={r.state==='active'?'':'archived'}><td>{r.name} <small className="offer-id">#{r.id}</small></td><td>{r.share}%</td>
      <td>{r.state==='active' && <><input type="checkbox" aria-label="Закрепить долю" checked={r.pin} onChange={()=>action(r.pin?'unlock':'lock',r.id)}/>
      {r.pin && <><input type="number" aria-label="Процент" min="0" max="100" value={percent[r.id]??r.share} onChange={e=>setPercent({...percent,[r.id]:e.target.value})}/><button onClick={()=>action('pin',r.id,{percent:Number(percent[r.id]??r.share)})}>Применить</button></>}</>}</td>
      <td><button onClick={()=>action(r.state==='removed'?'restore':'remove',r.id)}>{r.state==='removed'?'Bring back':'Remove'}</button></td></tr>)}</tbody></table></div>
    <form onSubmit={event => {
      event.preventDefault();
      action('add', Number(new FormData(event.currentTarget).get('offer_id')));
    }}><OfferField key={searchKey}/><button>Добавить</button></form>
    {s.dirty && <footer>{['push','cancel'].map(op=><button key={op} onClick={()=>run(async()=>{update(await api('streams/'+s.id+'/'+op,{}));setPercent({})})}>{op==='push'?'Push':'Cancel'}</button>)}</footer>}</>}
    </article>
}

function App(){
  const [page,pageSet]=useState('editor'),[list,setCampaigns]=useState([]),[options,setOptions]=useState(null);
  const [id,setCampaignId]=useState(localStorage.getItem('campaign')||''),[campaign,setCampaign]=useState(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  async function run(fn){setBusy(true);setError('');try{await fn()}catch(e){setError(e.message)}finally{setBusy(false)}}
  function show(c){setCampaign(c);setCampaignId(String(c.id));localStorage.setItem('campaign',c.id);pageSet('editor')}
  useEffect(()=>{run(async()=>{setCampaigns(await api('campaigns'));if(id)show(await api('campaigns/'+id))})},[]);
  const optionsRequest = React.useRef(0);
  const submitting = React.useRef(false);
  async function createPage(){
    const request = ++optionsRequest.current;
    pageSet('create');
    setOptions(null);
    setError('');
    try {
      const data = await api('options');
      if (request === optionsRequest.current) setOptions(data);
    } catch (err) {
      if (request === optionsRequest.current) setError(err.message);
    }
  }
  async function submitCampaign(event){
    event.preventDefault();
    if (!options || submitting.current) return;
    const body = Object.fromEntries(new FormData(event.currentTarget));
    submitting.current = true;
    try {
      await run(async () => {
        show(await api('campaigns', body));
        setCampaigns(await api('campaigns'));
      });
    } finally {
      submitting.current = false;
    }
  }
  const [dark, setDark] = useState(() => localStorage.getItem('adrobot-theme') !== 'light');
  useEffect(() => {
    const theme = dark ? 'dark' : 'light';
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('adrobot-theme', theme);
  }, [dark]);
  const [collapsed, setCollapsed] = useState(false);
  return <div className={'shell' + (collapsed ? ' compact' : '')}>
    <header><button className="menu" aria-label="Свернуть или развернуть меню" aria-expanded={!collapsed} onClick={()=>setCollapsed(!collapsed)}>☰</button><img className="app-icon" src="/adrobot.svg" alt=""/><strong>Adrobot</strong>
      <button className="theme-switch" type="button" role="switch" aria-label="Тёмная тема"
        aria-checked={dark} onClick={() => setDark(value => !value)}>
        <span>Тема</span><svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></svg>
        <i className="theme-track" aria-hidden="true"/><svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20.8 15A9.5 9.5 0 0 1 9 3.2 9.5 9.5 0 1 0 20.8 15Z"/></svg>
      </button>
    </header>
    <nav aria-label="Навигация">
      <button title="Кампании" aria-current={page==='editor'?'page':undefined} disabled={busy} onClick={()=>{optionsRequest.current++;pageSet('editor');setError('')}}><span aria-hidden="true">◎</span><b>Кампании</b></button>
      <button title="Создать кампанию" aria-current={page==='create'?'page':undefined} disabled={busy} onClick={createPage}><span aria-hidden="true">＋</span><b>Создать кампанию</b></button>
    </nav><main>
    {error && <p role="alert">{error}</p>}
    <fieldset disabled={busy}>{page==='create'?<><h1>Новая кампания</h1>{<form className="create" onSubmit={submitCampaign}>{[['name','Название','text'],['country','Код страны','text']].map(([key,label,type])=><label key={key}>{label}<input required name={key} type={type} min={1} pattern={key==='country'?'[A-Z]{2}':undefined} placeholder={key==='country'?'AU':''}/></label>)}
    <OfferField/>
    {[['domains','domain_id','Домен'],['groups','group_id','Группа'],['sources','traffic_source_id','Источник']].map(([key,name,label])=><label key={key}>{label}<select name={name} required disabled={!options}>{!options && <option value="">{error ? "Недоступно" : "Загрузка…"}</option>}{(options?.[key]||[]).map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label>)}<button disabled={!options}>Создать</button></form>}</>:<>
    <h1>Кампании</h1><section className="campaign-tools"><form onSubmit={e=>{e.preventDefault();run(async()=>{show(await api('campaigns/'+id+'/fetch',{}));setCampaigns(await api('campaigns'))})}}>
    <label>ID кампании <input type="number" min="1" required value={id} onChange={e=>setCampaignId(e.target.value)}/></label><button>Загрузить потоки</button></form>
    {!!list.length && <label>Локальные кампании <select value={campaign?.id||''} onChange={e=>{const val=e.target.value;run(async()=>show(await api('campaigns/'+val)))}}><option disabled value="">Выбрать</option>{list.map(c=><option key={c.id} value={c.id}>{c.name} #{c.id}</option>)}</select></label>}
    </section>
    {!campaign && <section className="empty-grid" aria-label="Потоки"><div className="columns"><span>ID</span><span>Поток</span><span>Офферы</span></div><p>Введите ID кампании, чтобы загрузить потоки</p></section>}
    {campaign && <><h2>{campaign.name} <small>#{campaign.id}</small></h2>{campaign.streams.map(s=><Stream key={s.id} s={s} run={run} update={show}/>)}</>}</>}</fieldset></main></div>
}
createRoot(document.getElementById('root')).render(<App/>);

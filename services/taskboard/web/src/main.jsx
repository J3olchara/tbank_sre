import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const empty = { title: '', description: '', status: 'todo' };
const statuses = { todo: 'Запланировано', doing: 'В работе', done: 'Готово' };
async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Ошибка запроса');
  return data;
}
function App() {
  const [tasks, setTasks] = useState([]);
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  async function load() {
    try { setTasks(await api('/api/tasks')); setError(''); }
    catch (e) { setError(e.message); } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);
  function reset() { setForm(empty); setEditing(null); }
  function change(event) { setForm({ ...form, [event.target.name]: event.target.value }); }
  async function save(event) {
    event.preventDefault(); setBusy(true);
    try {
      await api(editing === null ? '/api/tasks' : `/api/tasks/${editing}`, {
        method: editing === null ? 'POST' : 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form)
      });
      reset(); await load();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function remove(task) {
    if (!confirm(`Удалить задачу «${task.title}»?`)) return;
    setBusy(true);
    try { await api(`/api/tasks/${task.id}`, { method: 'DELETE' }); if (editing === task.id) reset(); await load(); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <main>
    <h1>Трекер задач</h1>
    <form onSubmit={save}>
      <h2>{editing === null ? 'Новая задача' : `Редактирование #${editing}`}</h2>
      <label>Название<input name="title" value={form.title} onChange={change} maxLength={200} required /></label>
      <label>Описание<textarea name="description" value={form.description} onChange={change} maxLength={2000} rows={3} /></label>
      <label>Статус<select name="status" value={form.status} onChange={change}>{Object.entries(statuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <button disabled={busy}>Сохранить</button>{editing !== null && <button type="button" onClick={reset} disabled={busy}>Отмена</button>}
    </form>
    {error && <p role="alert" className="error">{error}</p>}
    <h2>Задачи <button onClick={load} disabled={busy}>Обновить</button></h2>
    {loading ? <p>Загрузка…</p> : tasks.length === 0 && !error ? <p>Нет задач. Добавьте первую.</p> : null}
    {tasks.map(task => <article key={task.id}>
      <h3>{task.title}</h3><span>{statuses[task.status]}</span><p>{task.description}</p>
      <button disabled={busy} onClick={() => { setEditing(task.id); setForm({title:task.title,description:task.description,status:task.status}); }}>Изменить</button>
      <button disabled={busy} onClick={() => remove(task)}>Удалить</button>
    </article>)}
    <footer>Показано {tasks.length} задач · до 500 последних</footer>
  </main>;
}
createRoot(document.getElementById('root')).render(<App />);

const status = document.getElementById('status');
const buttons = [...document.querySelectorAll('button')];
window.launcher.onStatus(update => { status.textContent = update.message; status.classList.toggle('error', update.failed); });
async function start(mode, url) {
  buttons.forEach(button => button.disabled = true);
  try { const result = await window.launcher.start(mode, url); if (!result.ok) { status.textContent = result.message; status.classList.add('error'); } }
  catch { status.textContent = 'Запуск не выполнен. Повторите выбор режима.'; status.classList.add('error'); }
  finally { buttons.forEach(button => button.disabled = false); }
}
document.getElementById('local').addEventListener('click', () => start('offline'));
document.getElementById('remote').addEventListener('submit', event => { event.preventDefault(); start('connected', document.getElementById('url').value.trim()); });

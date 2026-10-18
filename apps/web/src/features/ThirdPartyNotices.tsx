import { useState } from 'react';
import { useI18n } from '../i18n';
import { Modal } from '../components/ui';
import notices from '../generated/third-party-notices.txt?raw';

export function ThirdPartyNotices() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return <div className="system-card">
    <h2>{t('Сторонние компоненты')}</h2>
    <p className="muted">{t('Лицензии интерфейса и шрифта сохранены в приложении и доступны без сети.')}</p>
    <p className="muted small">{t('В Windows сведения Electron и Chromium находятся в LICENSE.electron.txt и LICENSES.chromium.html рядом с EXE. Состав backend указан в его manifest.json. Это не подтверждение полной проверки прав распространения.')}</p>
    <button className="button secondary" onClick={() => setOpen(true)}>{t('Открыть лицензии интерфейса')}</button>
    {open && <Modal wide title={t('Лицензии интерфейса')} close={() => setOpen(false)}>
      <pre className="third-party-notices">{notices}</pre>
    </Modal>}
  </div>;
}

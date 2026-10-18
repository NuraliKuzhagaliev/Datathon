import { useI18n } from '../i18n';
import { UploadCloud, ScanLine, BookOpen, FileCheck2, ChevronDown, ChevronUp, ArrowRight } from 'lucide-react';

const steps = [
  { icon: UploadCloud, title: 'Загрузите видео', text: 'Выберите MOV до 128 МБ. Дождитесь завершения анализа.' },
  { icon: ScanLine, title: 'Изучите события', text: 'Откройте момент, исходные кадры и доступный контекст.' },
  { icon: BookOpen, title: 'Проверьте норму', text: 'Сопоставьте наблюдение с источником и его ограничениями.' },
  { icon: FileCheck2, title: 'Сохраните решение', text: 'Подтвердите, отклоните или отметьте сомнение. Добавьте заметку.' },
];

export function QuickStart({ expanded, toggle, synthetic, start }: {
  expanded: boolean; toggle: () => void; synthetic: boolean; start: () => void;
}) {
  const { t } = useI18n();
  return <section className="quick-start" aria-labelledby="quick-start-title">
    <header className="quick-start-heading"><div><div className="eyebrow">{t("ОТ ВИДЕО К РЕШЕНИЮ")}</div><h2 id="quick-start-title">{t("Четыре шага проверки")}</h2></div>
      <button className="text-button" aria-expanded={expanded} aria-controls="quick-start-steps" onClick={toggle}>{expanded ? t("Свернуть инструкцию") : t("Как начать")}{expanded ? <ChevronUp size={17}/> : <ChevronDown size={17}/>}</button>
    </header>
    <div id="quick-start-steps" hidden={!expanded}>
      <ol className="quick-start-steps">{steps.map(({icon: Icon, title, text}, i) => <li key={title}><div className="quick-start-step-top"><span className="quick-start-number">0{i + 1}</span><Icon size={19}/></div><h3>{t(title)}</h3><p>{t(text)}</p></li>)}</ol>
      <div className="quick-start-bottom"><p>{synthetic ? t("Сейчас открыты синтетические примеры. Загрузка и анализ доступны после подключения сервера.") : t("Если событий нет, изучите покрытие и ограничения анализа. Окончательная оценка остаётся за вами.")}</p>
        <button className="text-button" onClick={start}>{synthetic ? t("Разобрать демопример") : t("Добавить видео")}<ArrowRight size={16}/></button>
      </div>
    </div>
  </section>;
}

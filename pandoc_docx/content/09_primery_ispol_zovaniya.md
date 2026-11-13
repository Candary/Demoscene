# 9. Примеры использования

## 9.1. Простой вопрос

> ?почему вариадик-указатель ломает float ABI?

Ведущий «?» → обсуждение, файл-отчёт не требуется. Отвечаю сразу, без блока.

## 9.2. Новая функция (минимальная форма)

> !feat nebula background in main fragment shader, replaces gradient+stars
>
> after: contains(\"\[OK\] nebula bg rendered\")

Действие по коду, ведущего «?» нет → trace.log нужен. after задаёт специфичный признак успеха: в trace.log должна появиться строка \[OK\] nebula bg rendered.

## 9.3. Новая функция (детальная форма)

> !feat nebula background (domain-warped FBM, 4 octaves; 5 light nodes) in main fragment shader
>
> scope: только шейдеры --- не трогай загрузчик и build-скрипты
>
> after: nebula bg rendered
>
> revert: lastgood
>
> prio: optional
>
> notes: палитра deep indigo + vibrant purple / electric cyan / neon orange / hot pink;
>
> без звёзд; мы уже делали небулу и откатили --- сделай аккуратнее, не ломай ACES

Та же задача, но с явными ограничениями и заметками. scope записан словами, без номеров строк --- я сам маплю на конкретные файлы.

## 9.4. Удаление функции (новое в v0.2)

> !remove nebula background from main fragment shader
>
> after: grep(\"nebula\", trace.log) == 0 AND contains(\"First frame rendered\")
>
> notes: верни gradient+stars как было до небулы; не трогай огонь и частицы

Хирургическое удаление одной фичи с сохранением всего остального. trace.log нужен (проверить, что после удаления программа не развалилась). Перед удалением --- backup, так что всегда обратимо.

## 9.5. Диагностика сбоя

> !diag чёрный экран после «Window shown --- entering main loop»

Обязательно прикрепить trace.log. Я читаю его, ищу последний успех перед падением, сравниваю с эталонным хорошим trace.log --- и называю причину за один шаг.

## 9.6. Откат к последней рабочей версии

> !revert lastgood

lastgood --- автотокен: я сам нахожу в журнале последнюю версию со статусом «работает». Вам не нужно помнить номер. trace.log не нужен --- откат не правка кода.

## 9.7. Заморозка и новое правило

> #milestone v45-nebula-working \@md5=latestZip \@status=working
>
> #proto avoid:default += shaders_uniforms_table.h (предложить)

#milestone --- заморозить копию как эталон. #proto --- предложить изменение протокола; substantive-правки требуют вашего подтверждения.

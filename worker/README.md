# Бесплатный API-релей для Antigravity CLI

Экспериментальный [Cloudflare Worker](https://developers.cloudflare.com/workers/get-started/guide/) для **Antigravity CLI с собственным ключом Gemini API**. Не требует VPN в Windows или своего VPS. Работает только как заранее ограниченный HTTPS-шлюз к `generativelanguage.googleapis.com` для запросов `/v1`, `/v1beta` и `/upload/v1*`; Google-login, сайт Gemini и десктопная IDE этим способом не подключаются.

## Развёртывание

1. Создайте бесплатный аккаунт Cloudflare и получите собственный [ключ Gemini API](https://aistudio.google.com/app/api-keys) в доступном для API регионе. Нужен установленный Node.js.
2. В корне репозитория выполните `npx wrangler@latest login`, затем `npx wrangler@latest deploy --config worker/wrangler.jsonc`. Запишите адрес вида `https://geminipath-api-relay.<ваш-subdomain>.workers.dev`.
3. Локально вычислите SHA-256 **своего** API-ключа, не добавляя сам ключ в командную строку или Git:

   ```powershell
   py -c "import getpass,hashlib; print(hashlib.sha256(getpass.getpass('API key: ').encode()).hexdigest())"
   ```

   Выполните `npx wrangler@latest secret put ALLOWED_API_KEY_SHA256 --config worker/wrangler.jsonc` и вставьте полученный хеш. Worker без него отказывает в модельных запросах. Проверка `https://<адрес-worker>/health` не требует ключа.
4. Согласно [официальной инструкции Antigravity CLI](https://antigravity.google/docs/cli/install/#using-a-gemini-api-key), добавьте `"modelProvider": "gemini"` в `%USERPROFILE%\.gemini\antigravity-cli\settings.json` (сохраните остальные настройки) и установите `GEMINI_API_KEY` **только в используемой сессии**. В том же окне PowerShell запустите:

   ```powershell
   $env:GOOGLE_GEMINI_BASE_URL = "https://geminipath-api-relay.<ваш-subdomain>.workers.dev"
   agy
   ```

   Сделайте реальный запрос к модели. Если он не прошёл, проверьте точный HTTP-код и сообщение CLI; удачная проверка `/health` ещё не говорит о доступности моделей.

Worker пересылает API-ключ в заголовке только к Google, не пересылает браузерные cookies и OAuth-заголовки, не логирует запросы самостоятельно и отказывает чужим API-ключам. **Ваш Cloudflare-аккаунт и платформа Cloudflare всё равно обрабатывают запросы и ключ**; в ней нельзя хранить то, что вы не готовы ей доверить. Не публикуйте ключ, хеш или URL с `?key=` в репозитории/логах.

## Границы эксперимента

- [Workers Free](https://developers.cloudflare.com/workers/platform/limits/) — 100 000 запросов в сутки и 10 мс CPU на запрос; время ожидания сети не входит в CPU. Квота Gemini API отдельная.
- В `wrangler.jsonc` указан [placement hint](https://developers.cloudflare.com/workers/configuration/placement/) у европейского региона. Это пожелание о месте *исполнения*, **не обещание** европейского выходного IP, одобрения Google или пригодности аккаунта. При ошибке региона нужен фактический тест модельного запроса.
- Cloudflare Worker [не принимает входящие TCP CONNECT](https://developers.cloudflare.com/workers/runtime-apis/tcp-sockets/#considerations), поэтому адрес Worker нельзя просто прописать как HTTP-прокси для браузера, Gemini или всей Antigravity IDE.
- Для проверки кода без деплоя: `node --test worker/test.mjs`. Тесты проверяют маршрутизацию и защиту шлюза, но не Google API и не географию Cloudflare.

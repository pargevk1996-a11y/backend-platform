# Backend Platform: подробная книга проекта

## Глава 1. Что это за проект

`backend-platform` - это security-first backend-платформа в микросервисном стиле. Проект не пытается быть большим монолитом с одной точкой отказа. Вместо этого он разделяет ответственность между сервисами и собирает вокруг этого набора production-like практики: Docker, CI, policy guardrails, rate limiting, audit и безопасную обработку секретов.

Сейчас платформа состоит из пяти основных частей:

- `services/auth-service` - identity lifecycle: регистрация, логин, TOTP 2FA, refresh rotation, revoke, password reset, audit.
- `services/user-service` - пользовательский контекст, профили, роли, permissions, RBAC.
- `services/api-gateway` - edge-вход, same-origin browser auth, cookie/session orchestration, CSRF guard, proxy hardening.
- `services/notification-service` - WIP health-only сервис, который уже собирается, тестируется и сканируется как часть платформы.
- `shared/python` - заготовка для versioned internal contracts и общих утилит.

Главная идея проекта не в количестве endpoint'ов, а в том, как они собраны: токены не светятся браузеру, brute-force ключи не раскрывают email в Redis, локальные env-файлы генерируются со strong secrets, а security-политики закреплены в тестах и workflow'ах.

## Глава 2. Общая архитектура

Проект использует layered architecture. Внутри сервисов код разложен по слоям:

- `api/` - FastAPI routers и HTTP-contract;
- `core/` - config, middleware, security helpers, constants, validation;
- `services/` - бизнес-логика;
- `repositories/` - доступ к БД;
- `models/` - SQLAlchemy модели;
- `schemas/` - Pydantic request/response схемы;
- `integrations/` - Redis, email, TOTP и внешние технические зависимости;
- `tests/` - unit, integration, security, e2e.

Типичный путь запроса выглядит так:

1. Gateway принимает внешний HTTP-запрос.
2. Gateway определяет, публичный endpoint или защищенный.
3. Для browser session flow gateway работает через HttpOnly cookies и CSRF.
4. Дальше запрос отправляется в allowlist-based downstream service.
5. Downstream service валидирует контракт и выполняет бизнес-логику.
6. Ответ возвращается через gateway уже в санитизированной форме для браузера.

Такой расклад позволяет держать security-политику централизованно на edge и при этом не смешивать бизнес-правила с транспортным слоем.

## Глава 3. Auth Service

`auth-service` - центр безопасности проекта. Он отвечает за:

- регистрацию;
- логин;
- challenge-based 2FA;
- refresh token rotation и revoke;
- password reset;
- audit events;
- persistent account lock;
- выдачу JWT.

### Регистрация

Flow регистрации:

1. Email валидируется и нормализуется.
2. Проверяется уникальность пользователя.
3. Пароль хешируется через Argon2.
4. Создается пользователь.
5. Выпускается access/refresh token pair.
6. Пишется audit event.
7. Транзакция коммитится.

Важный нюанс: браузер не получает эти токены напрямую. Для browser flow gateway перехватывает ответ auth-service, кладет токены в HttpOnly cookies и отдает фронту только безопасный status JSON.

### Логин

Логин сделан с учетом anti-enumeration и brute-force защиты:

1. Сервис проверяет lock по privacy-safe identifier.
2. Ищет пользователя с `SELECT ... FOR UPDATE`.
3. Для несуществующего пользователя выполняет dummy password verification.
4. Для неверного пароля пишет audit event и увеличивает counters.
5. После трех неверных паролей аккаунт получает persistent lock.
6. Снять lock может только успешный password reset.

### 2FA challenge

Если `two_factor_enabled=true`, токены не выдаются сразу. Вместо этого создается challenge в Redis.

Challenge содержит только то, что реально нужно для безопасной проверки:

- `user_id`;
- fingerprint IP;
- optional gateway-bound challenge nonce для browser flow;
- TTL.

При подтверждении challenge:

1. challenge читается из Redis;
2. для browser flow сначала проверяется gateway-bound nonce, а для прямого API flow остается fallback на IP fingerprint;
3. валидируется TOTP или backup code;
4. challenge удаляется;
5. только после этого выдаются токены.

### Password reset

Password reset остается privacy-safe:

- endpoint отвечает одинаково, даже если email не существует;
- reset code имеет TTL;
- после успешного reset меняется пароль;
- refresh tokens и access sessions отзываются;
- persistent account lock очищается.

Именно password reset является единственным штатным способом разблокировать аккаунт после трех неверных попыток логина.

## Глава 4. JWT стратегия

JWT в проекте завязаны на `PyJWT` и единый policy across services.

Ключевые решения:

- алгоритм по умолчанию - `RS256`;
- `python-jose` запрещен workflow-политикой;
- в deployed env запрещены HS-algorithms;
- access token и refresh token разделены по `type`;
- `iss`, `aud`, `exp`, `nbf`, `iat` валидируются;
- access token несет `sid`;
- refresh token несет `sid` и `family_id`.

Это нужно не только ради "чистой" JWT-теории. `sid` позволяет быстро отзывать access session через Redis marker, а `family_id` нужен для корректного revoke/reuse handling у refresh tokens. Для refresh rotation также добавлено короткое retry-safe окно, чтобы легитимные дубли refresh-запросов не отзывали всю token family мгновенно.

## Глава 5. Anti-Abuse: Rate Limiting, Brute-Force, Account Lock

В проекте есть два слоя защиты от перебора:

1. rate limiting;
2. brute-force state с lock windows и account-level counters.

Основные скоупы:

- `login`;
- `login_account`;
- `2fa`;
- `password_reset`;
- `password_reset_account`;
- `password_reset_confirm`;
- `register`, `refresh`, `revoke`;
- `2fa_setup`, `2fa_enable`, `2fa_disable`, `2fa_regenerate`;
- `public_auth`, `protected` на gateway.

Redis keys не используют email, IP или другие identifiers в открытом виде. Вместо этого применяются HMAC-based privacy-safe fingerprints. Это важно, потому что Redis keyspace нередко попадает в отладку, дампы и инцидентные снимки.

Отдельно от временных lock windows есть persistent account lock:

- после трех неверных паролей пользователь блокируется;
- блокировка хранится в БД (`locked_at`, `lock_reason`);
- обычный повторный логин ее не снимает;
- пароль нужно сбросить через password reset flow.

## Глава 6. User Service и RBAC

`user-service` хранит authorization context и профиль пользователя.

Главные сущности:

- `app_users`;
- `user_profiles`;
- `roles`;
- `permissions`;
- `user_roles`;
- `role_permissions`;
- `audit_events`.

Базовые endpoints:

- `GET /v1/users/me`;
- `GET /v1/profiles/me`;
- `PATCH /v1/profiles/me`;
- `GET /v1/roles/me`;
- `GET /v1/permissions/me`.

RBAC здесь сделан как нормализованная модель, а не как набор случайных строк в controller-коде. Это дает нормальную точку роста для fine-grained authorization.

## Глава 7. API Gateway

`api-gateway` - не просто proxy. Он реализует browser auth contract для всей платформы.

Что делает gateway:

- маршрутизирует запросы только в allowlist сервисов;
- различает public/protected endpoints;
- проверяет JWT на защищенных маршрутах;
- умеет принимать access token из bearer header или из cookie;
- ставит HttpOnly access/refresh cookies;
- требует CSRF для state-changing cookie-auth запросов;
- фильтрует опасные request/response headers;
- отдает фронту безопасный JSON вместо сырого token pair.

Browser contract сейчас такой:

1. Браузер работает только через gateway на том же origin.
2. После register/login/refresh браузер получает не токены, а status JSON.
3. Реальные access/refresh values лежат в cookies.
4. Во время login -> login/2fa gateway держит временный HttpOnly challenge cookie и сам пробрасывает nonce в auth-service.
5. Для `POST/PUT/PATCH/DELETE` в cookie-auth flow нужен `X-CSRF-Token`.
6. Downstream services по-прежнему получают `Authorization: Bearer <access-token>` от gateway, а не cookie.

Для UI также добавлен `GET /v1/sessions/me`, который возвращает безопасный session snapshot, включая `two_factor_enabled`. Это позволяет фронту показывать только релевантные 2FA-действия.

## Глава 8. Notification Service

`notification-service` сейчас честно помечен как WIP.

Что у него уже есть:

- health endpoints;
- базовый config;
- security middleware;
- Docker image;
- тесты;
- участие в CI/security workflows.

Чего у него пока нет:

- real delivery provider;
- queue boundary;
- retry policy;
- delivery audit trail;
- полноценных delivery tests.

Это правильное состояние для WIP-сервиса: он не притворяется production-ready.

## Глава 9. Конфигурация и секреты

Конфигурация построена на `pydantic-settings`.

Что важно:

- чувствительные значения описаны через `SecretStr`;
- deploy validators запрещают опасные production defaults;
- wildcard CORS запрещен в deployed env;
- asymmetric JWT обязателен вне development;
- PEM-like public keys проверяются;
- cookie security defaults завязаны на environment;
- локальные env-файлы генерируются через `infra/scripts/bootstrap.sh`.

Bootstrap генерирует сильные локальные значения для:

- `services/auth-service/.env`;
- `services/user-service/.env`;
- `services/api-gateway/.env`;
- `infra/compose/.env.compose`.

Это лучше, чем хранить слабые дефолты в репозитории и надеяться, что их кто-то потом заменит.

## Глава 10. Cookies и CSRF

Browser auth в проекте построен на трех основных cookie и одной временной login-challenge cookie:

- access token cookie;
- refresh token cookie;
- CSRF cookie.
- temporary login challenge cookie.

Для access/refresh cookies задаются:

- `HttpOnly`;
- `Secure`;
- `SameSite`;
- `Path=/`;
- controlled max-age.

CSRF cookie намеренно не `HttpOnly`, потому что фронт должен прочитать его и отправить значение в `X-CSRF-Token`.

Временная login-challenge cookie тоже `HttpOnly`, живет короткое время и нужна только для безопасной связки шагов `/login` и `/login/2fa` в browser flow.

CSRF-проверка срабатывает не для любого POST подряд, а именно для state-changing запросов, где gateway использует cookie auth. Это важный баланс между безопасностью и предсказуемым поведением API.

Отдельно auth-service и gateway помечают auth-sensitive ответы как `Cache-Control: no-store`, чтобы логин, refresh, revoke, setup 2FA и backup codes не кэшировались браузером или промежуточным слоем.

## Глава 11. Middleware и security headers

Во всех сервисах есть:

- request context middleware;
- security headers middleware.

В `auth-service` и `api-gateway` дополнительно есть middleware, который навешивает `no-store` на auth-sensitive endpoints.

Что делают middleware:

1. генерируют или принимают `X-Request-ID`;
2. кладут `request_id` в state;
3. измеряют `X-Process-Time-Ms`;
4. ставят security headers;
5. для чувствительных auth-ответов отключают кэширование.

Основные headers:

- `X-Content-Type-Options: nosniff`;
- `X-Frame-Options: DENY`;
- `Referrer-Policy: same-origin`;
- `Permissions-Policy`;
- `Content-Security-Policy`.

Для API и UI CSP отличается: у API политика максимально строгая, у UI достаточно мягкая, чтобы браузерная консоль работала предсказуемо.

## Глава 12. Docker

Все runtime images собраны через multi-stage Dockerfiles.

Это дает такие преимущества:

- build dependencies не попадают в финальный слой;
- runtime меньше;
- attack surface меньше;
- контейнеры стартуют от non-root user;
- healthcheck не требует `curl`.

В runtime-образах не нужно держать лишние инструменты. Чем меньше внутри контейнера утилит и build chain, тем лучше для базового hardening.

## Глава 13. Docker Compose

В проекте есть два compose-файла:

- `infra/compose/docker-compose.dev.yml`;
- `infra/compose/docker-compose.prod.yml`.

### Dev stack

Dev compose:

- публикует сервисы на `127.0.0.1`;
- поднимает Postgres для auth и user;
- поднимает Redis с паролем;
- стартует `auth-service`, `user-service`, `api-gateway`.

После `make up` нужно выполнить:

```bash
make migrate-auth
make migrate-user
```

Без миграций сервисы на пустых БД не смогут нормально стартовать.

### Prod stack

Prod compose добавляет runtime hardening:

- `read_only: true`;
- `tmpfs: /tmp`;
- `cap_drop: ALL`;
- `no-new-privileges:true`;
- internal backend network;
- отдельную edge network для gateway.

## Глава 14. CI/CD

В репозитории сейчас три workflow:

- `ci.yml`;
- `security.yml`;
- `deploy.yml`.

### CI

`ci.yml` делает:

1. установку зависимостей;
2. compile check через `python -m compileall`;
3. тесты всех сервисов;
4. e2e stack test через `infra/scripts/run_e2e_stack.sh`.

### Security

`security.yml` делает:

1. policy guardrail против `python-jose`;
2. guardrail против runtime `assert` в service code;
3. Bandit scan;
4. auth security tests;
5. gateway security tests;
6. Trivy scan Docker images.

### Deploy

`deploy.yml` не деплоит напрямую в cluster. Сейчас он собирает service images при `workflow_dispatch` и на тегах `v*`. Это аккуратный build workflow, не притворяющийся готовым production CD.

## Глава 15. Dependabot и supply chain

`/.github/dependabot.yml` следит за:

- pip dependencies сервисов;
- `shared/python`;
- GitHub Actions;
- Docker dependencies.

Pinned dependencies без автоматического пересмотра быстро превращаются в техдолг. Dependabot не решает supply-chain security сам по себе, но он гарантирует, что обновления и CVE-fixes не забудутся просто потому, что о них никто не вспомнил.

## Глава 16. Shared Python package

`shared/python` - это не просто "папка с общим кодом", а заготовка под versioned internal package.

Текущий принцип:

- shared code существует отдельно;
- сервисы могут использовать его локально;
- долгосрочно он должен публиковаться как внутренний versioned artifact.

Идея здесь простая: контракты между сервисами должны иметь explicit version boundary. Иначе rolling deploy легко приводит к рассинхрону между producer и consumer.

## Глава 17. Observability

В проекте уже заложены структурные места для observability, но это пока не полноценный OTel stack.

Что уже есть:

- request id;
- process time metrics на уровне response header;
- audit events;
- структурированное логирование в сервисах.

Что еще можно добавить:

- OpenTelemetry instrumentation;
- trace propagation через gateway;
- Prometheus metrics;
- dashboards;
- alerts;
- audit aggregation.

## Глава 18. Локальный запуск

Актуальный локальный путь такой:

1. Установить зависимости:

```bash
make deps
```

2. Сгенерировать локальные env-файлы:

```bash
infra/scripts/bootstrap.sh
```

3. Поднять dev stack:

```bash
make up
```

4. Применить миграции:

```bash
make migrate-auth
make migrate-user
```

5. Открыть UI:

```bash
http://localhost:8000/ui
```

6. Проверить health:

```bash
curl http://localhost:8000/v1/health/ready
curl http://localhost:8001/v1/health/ready
curl http://localhost:8002/v1/health/ready
```

## Глава 19. Тестирование

Тесты разбиты по уровням.

### Auth-service

Проверяются:

- JWT service;
- password reset;
- refresh rotation/reuse и retry-safe duplicate refresh;
- 2FA service;
- challenge flow, включая browser-bound nonce;
- audit sanitization;
- validation sanitization;
- brute-force privacy;
- session info response;
- no-store headers.

### User-service

Проверяются:

- access token validation;
- RBAC service;
- permission guards;
- validation sanitization;
- security helpers.

### API gateway

Проверяются:

- routing;
- public/protected endpoint policy;
- cookie auth helpers, включая login challenge cookie;
- header sanitization;
- CSRF behavior;
- client IP handling;
- no-store headers.

### Notification-service

Проверяются:

- live/ready handlers;
- security headers middleware.

### E2E

Есть минимум два полезных сценария:

- `make test-e2e-auth`;
- `make test-e2e-stack`.

Первый проверяет auth flow через gateway, второй гоняет полный docker stack.

## Глава 20. Production checklist

Перед production стоит проверить:

1. `SERVICE_ENV=production`.
2. JWT algorithm - asymmetric.
3. Public/private keys корректны и в правильном формате.
4. Explicit `CORS_ALLOWED_ORIGINS` заданы.
5. Gateway - единственная внешняя точка входа.
6. `COOKIE_SECURE=true`.
7. TLS termination настроен.
8. Redis защищен паролем.
9. DB credentials не дефолтные.
10. Prod compose hardening включен.
11. Миграции применены.
12. CI и security workflows зелёные.
13. Trivy не дает HIGH/CRITICAL.
14. Bandit не дает проблем в допустимом диапазоне.
15. Browser clients ходят только в gateway same-origin.
16. Прямой доступ к auth/user-service извне закрыт.

## Глава 21. Что еще можно улучшить

Следующий уровень зрелости для платформы:

1. gateway-level centralized authorization policy;
2. полноценный OpenTelemetry stack;
3. event-driven integration между сервисами;
4. versioned release pipeline для `shared/python`;
5. real notification delivery architecture;
6. SBOM generation и image signing;
7. более широкие integration tests c real infra;
8. deployment manifests для Kubernetes или Nomad.

## Глава 22. Краткая история актуальных исправлений

В текущей итерации проекта особенно важны такие изменения:

### 22.1. Browser auth перенесен на cookie contract

- gateway кладет access/refresh в HttpOnly cookies;
- браузер больше не должен хранить bearer tokens;
- `/refresh` и `/revoke` умеют работать от browser session;
- login 2FA handshake использует временную HttpOnly challenge cookie;
- auth-sensitive browser ответы помечаются как `no-store`.

### 22.2. Persistent account lock

- после трех неверных паролей аккаунт блокируется;
- повторный логин lock не снимает;
- password reset очищает lock и session state.

### 22.3. Session introspection для UI

- `GET /v1/sessions/me` отдает безопасный session snapshot;
- UI получает `two_factor_enabled` и не показывает конфликтующие действия.

### 22.4. Browser UI стал осторожнее

- `Disable 2FA` в UI теперь идет через password + TOTP;
- поле `Backup code` убрано из браузерной формы;
- статусная зона показывает только безопасные summary, без сырого JSON payload.

## Глава 23. Итог

На текущем этапе `backend-platform` - это уже не просто учебный набор FastAPI-сервисов. Это аккуратно собранная security-first платформа с:

- browser cookie auth через gateway;
- browser-bound 2FA challenge вместо brittle IP-only browser binding;
- persistent account lock;
- challenge-based 2FA;
- refresh rotation, retry-safe duplicate handling и revoke;
- RBAC и user context;
- hardened Docker/runtime policy;
- CI/security guardrails;
- локальным dev stack, который реально можно поднять и прогнать end-to-end.

Это хорошая база как для дальнейшего hardening, так и для роста функциональности.

## Глава 24. Последний цикл hardening и UX-выравнивания

Последний цикл изменений был уже не про "добавить фичу", а про выровнять поведение платформы до предсказуемого и безопасного состояния.

### 24.1. 2FA UI теперь соответствует реальному состоянию аккаунта

UI больше не показывает одновременно `Enable 2FA` и `Disable 2FA`. Сначала через `sessions/me` подгружается реальный флаг, и только после этого интерфейс решает, какое действие вообще доступно пользователю.

### 24.2. Popup setup flow стал читаемым

Popup для подключения Google Authenticator теперь разделен на нормальные шаги:

- отдельный блок для QR;
- отдельный блок для кода;
- отдельный блок для backup codes.

Это уменьшает вероятность пользовательской ошибки и делает flow заметно чище.

### 24.3. Статусная панель больше не светит лишнее

Главный UI не выводит raw JSON с потенциально чувствительными полями. Пользователь видит короткий безопасный summary:

- сессия восстановлена;
- 2FA требуется;
- операция завершена;
- ошибка с пользовательским message.

Backup codes остаются только в dedicated setup popup, где они действительно нужны один раз после включения 2FA.

# Backend Platform: подробная книга проекта

## Глава 1. Что это за проект

`backend-platform` - это производственная микросервисная backend-платформа на Python. Проект построен вокруг трех основных идей:

1. Безопасная аутентификация.
2. Чистая layered architecture.
3. Production-like инфраструктура с Docker, CI, security checks и observability-заготовками.

Главная ценность проекта не в том, что он просто запускает FastAPI endpoints. Его ценность в том, что он показывает инженерный подход: сервисы разделены по ответственности, секреты валидируются, JWT сделан аккуратно, brute-force protection учитывает privacy, а CI не только запускает тесты, но и проверяет security guardrails.

Проект состоит из нескольких сервисов:

- `auth-service` - регистрация, логин, JWT, refresh token rotation, 2FA, password reset, audit events.
- `user-service` - пользовательский контекст, профили, роли, permissions, RBAC.
- `api-gateway` - входная точка, проксирование запросов, JWT verification, rate limiting.
- `notification-service` - пока WIP-сервис с health endpoints и базовой security-обвязкой.
- `shared/python` - общие контракты и утилиты, подготовленные к versioned internal package подходу.

Вместе эти части образуют основу backend-платформы, которую можно развивать дальше: добавлять billing, notification delivery, event bus, OpenTelemetry tracing, centralized policy enforcement и другие production-функции.

## Глава 2. Общая архитектура

Проект использует layered architecture. Это значит, что код не свален в один большой `main.py`, а разложен по слоям:

- `api/` - HTTP endpoints и FastAPI routers.
- `core/` - настройки, security helpers, middleware, constants, rate limiting.
- `services/` - бизнес-логика.
- `repositories/` - работа с базой данных.
- `models/` - SQLAlchemy модели.
- `schemas/` - Pydantic request/response модели.
- `integrations/` - Redis, email, TOTP и внешние технические зависимости.
- `observability/` - заготовки под tracing, metrics, audit.
- `tests/` - unit, integration и security tests.

Главный принцип такой: endpoint не должен знать детали базы данных, а repository не должен знать правила бизнеса. Например, endpoint `/auth/login` принимает payload, передает данные в `AuthService`, а уже `AuthService` решает, проверить ли пароль, создать ли 2FA challenge, выдать ли token pair, записать ли audit event.

Такой подход дает несколько преимуществ:

1. Код проще тестировать.
2. Бизнес-логику можно читать отдельно от HTTP-слоя.
3. Репозитории можно менять без переписывания endpoints.
4. Security checks легче держать в одном месте.
5. Проект легче масштабировать командой.

## Глава 3. Auth Service

`auth-service` - самый важный сервис с точки зрения безопасности. Он отвечает за identity lifecycle: регистрацию, логин, двухфакторную аутентификацию, refresh tokens, password reset и audit.

### Регистрация

Пользователь отправляет email и пароль. Endpoint валидирует request schema, затем передает управление в `AuthService.register`.

Пошагово:

1. Проверяется, существует ли пользователь с таким email.
2. Пароль хешируется через Argon2.
3. Создается пользователь.
4. Создается access token и refresh token.
5. Пишется audit event о регистрации.
6. Транзакция коммитится.
7. Клиент получает token pair.

Важно, что пароль не хранится в открытом виде. Хранится только password hash.

### Логин

Логин сделан аккуратно, с учетом security-рискoв.

Пошагово:

1. Email нормализуется.
2. Формируется brute-force identifier из email и IP.
3. Проверяется, не заблокирован ли identifier.
4. Пользователь ищется в базе.
5. Если пользователь не найден, выполняется dummy password verification.
6. Если пароль неверный, фиксируется failed attempt и audit event.
7. Если пароль верный, failed attempts очищаются.
8. Если включена 2FA, создается login challenge.
9. Если 2FA не включена, выдаются tokens.

Dummy password verification важен против timing attacks. Без него атакующий мог бы измерять разницу между "пользователь существует" и "пользователь не существует".

### 2FA login challenge

Если у пользователя включена двухфакторная аутентификация, сервис не выдает токены сразу. Вместо этого создается challenge.

Challenge содержит:

- user id;
- privacy-safe fingerprint IP;
- privacy-safe fingerprint user-agent;
- TTL в Redis.

Когда пользователь вводит TOTP или backup code, сервис:

1. Находит challenge.
2. Проверяет, что challenge context совпадает.
3. Проверяет TOTP или backup code.
4. Удаляет challenge.
5. Выдает token pair.
6. Пишет audit event.

Это защищает от простой подмены challenge id и повторного использования challenge после успешного входа.

### Refresh tokens

Refresh token flow построен вокруг rotation.

Идея такая: refresh token не должен жить как вечный bearer secret. После использования он должен заменяться новым. Если старый refresh token пытаются использовать повторно, это может означать кражу токена.

Поэтому сервис:

1. Декодирует refresh token.
2. Проверяет type claim.
3. Проверяет наличие токена в базе.
4. Проверяет, не revoked ли он.
5. Выпускает новую пару токенов.
6. Старый refresh token помечает как использованный/замененный.
7. При reuse фиксирует security event и отзывает family.

Refresh token хранится не как plain token, а через hash с pepper.

### Password reset

Password reset построен так, чтобы не раскрывать существование email.

Пошагово:

1. Клиент отправляет email.
2. Сервис всегда отвечает одинаково, даже если пользователя нет.
3. Если пользователь есть, создается reset code/token.
4. Токен хранится privacy-safe способом.
5. При подтверждении проверяется code, TTL и status.
6. Пароль меняется.
7. Refresh/session data пользователя отзывается.
8. Пишется audit event.

Такой подход снижает риск user enumeration.

## Глава 4. JWT стратегия

JWT в проекте сделан не как простой tutorial-вариант, а ближе к production-подходу.

Ключевые решения:

- алгоритм по умолчанию `RS256`;
- валидация algorithm через allowlist;
- `algorithms=[settings.jwt_algorithm]` передается списком;
- проверяются `aud`, `iss`, `nbf`, `exp`, `type`;
- обязательные claims задаются через `options={"require": [...]}`;
- access и refresh tokens разделены по `type`;
- production/staging запрещают HS algorithms;
- production/staging требуют PEM-like ключи.

Почему это важно:

1. RS256 использует асимметричные ключи.
2. Public key можно отдавать сервисам для верификации.
3. Private key остается только у auth-service.
4. Проверка `aud` и `iss` защищает от токенов из другого контекста.
5. Проверка `type` не дает использовать refresh token как access token.
6. Guardrail в CI запрещает `python-jose`, чтобы команда случайно не вернулась к нежелательной JWT-библиотеке.

## Глава 5. Brute-force protection

Brute-force protection вынесен в отдельный сервис и работает по скоупам:

- `login`;
- `2fa`;
- `password_reset`;
- `password_reset_confirm`;
- другие rate-limit scopes.

Идентификаторы не кладутся в Redis в plain form. Вместо этого используются HMAC-based privacy-safe keys.

Это важно, потому что Redis keys часто попадают в логи, debug dumps, monitoring или incident snapshots. Если в ключах лежит email или IP в открытом виде, это становится privacy leak.

Пошагово brute-force flow выглядит так:

1. Перед действием сервис проверяет lock state.
2. При неудачной попытке увеличивается счетчик.
3. Если лимит превышен, identifier блокируется на заданное время.
4. При успешном действии failed attempts очищаются.

Такой подход защищает логин и 2FA не только от прямого перебора паролей, но и от перебора TOTP/backup codes.

## Глава 6. User Service и RBAC

`user-service` отвечает за пользовательский контекст и authorization data.

Основные сущности:

- user;
- profile;
- role;
- permission;
- user_role;
- role_permission;
- audit_event.

RBAC нормализован через отдельные таблицы. Это правильный фундамент, потому что роли и permissions не зашиты в код как случайные строки в каждом endpoint.

Пример flow для `/users/me`:

1. Сервис получает access token.
2. Декодирует и валидирует token claims.
3. Находит user context.
4. Загружает roles.
5. Загружает permissions.
6. Возвращает пользователю его identity context.

Для endpoints, где нужна проверка прав, используется `ensure_permission`.

Например, чтение чужого user profile требует permission вроде `users:read`. Изменение своего profile требует permission вроде `profile:write:self`.

## Глава 7. API Gateway

`api-gateway` - входная точка для внешнего клиента. Он не реализует всю бизнес-логику, а маршрутизирует запросы в нужные downstream-сервисы.

Основные функции gateway:

- принимает external traffic;
- проверяет public/protected endpoint;
- валидирует access token для protected endpoints;
- применяет rate limiting;
- санитизирует headers;
- проксирует запросы в auth-service/user-service/notification-service;
- возвращает downstream response клиенту.

Gateway особенно важен как место, где можно централизовать edge security:

- request id;
- security headers;
- CORS;
- rate limiting;
- JWT verification;
- header sanitization;
- future policy enforcement.

Пока gateway проверяет JWT и route-level public/protected статус. Более глубокий permission enforcement еще остается roadmap-level задачей.

## Глава 8. Notification Service

`notification-service` сейчас намеренно помечен как WIP.

Раньше он выглядел как пустой скаффолд: файлы были, но реального сервиса, Dockerfile, lock-файла и тестов не было. Теперь он доведен до честного минимального состояния:

- есть `pyproject.toml`;
- есть `requirements.lock`;
- есть `app/main.py`;
- есть health endpoints;
- есть config;
- есть security middleware;
- есть schemas;
- есть tests;
- есть Dockerfile;
- сервис подключен в CI.

Важно: это не полноценная delivery-система. Он пока не отправляет email/SMS/push. В README прямо написано, что production traffic нельзя подключать до реализации:

- delivery provider;
- queue boundary;
- retry policy;
- delivery audit trail;
- tests around delivery.

Это честный подход. Лучше иметь WIP-сервис, явно помеченный как WIP, чем пустой каталог, который выглядит готовым.

## Глава 9. Конфигурация и секреты

Конфигурация реализована через `pydantic-settings`.

Важные решения:

- secrets описаны через `SecretStr`;
- peppers имеют минимальную длину;
- production/staging валидируют JWT algorithm;
- production/staging требуют explicit CORS origins;
- wildcard CORS запрещен в deployed environments;
- `COOKIE_SECURE` по умолчанию `true`;
- development env явно может переопределить `COOKIE_SECURE=false`;
- TOTP encryption key валидируется как Fernet key.

Почему `COOKIE_SECURE=true` по умолчанию:

Небезопасные дефолты опасны. Даже если production validator запрещает insecure cookies, staging часто использует реальные или semi-real данные. Поэтому безопаснее сделать secure default, а development пусть явно ослабляет настройку.

## Глава 10. Cookies и CSRF

Auth cookies создаются через централизованные helpers.

Для cookies задаются:

- `httponly`;
- `secure`;
- `samesite`;
- `domain`;
- `path`;
- expiration.

CSRF token cookie сделан не `httponly`, потому что frontend должен иметь возможность прочитать token и отправить его в header.

Security смысл:

- access/refresh cookies защищены от прямого чтения JS через `httponly`;
- `secure` требует HTTPS;
- `samesite` снижает риск CSRF;
- отдельный CSRF token помогает защитить state-changing requests.

## Глава 11. Middleware и security headers

В сервисах есть middleware для request context и security headers.

Request context middleware:

1. Берет `X-Request-ID` из запроса или генерирует новый.
2. Кладет request id в request state.
3. Измеряет время обработки.
4. Добавляет `X-Request-ID` и `X-Process-Time-Ms` в response.

Security headers middleware выставляет:

- `X-Content-Type-Options: nosniff`;
- `X-Frame-Options: DENY`;
- `Referrer-Policy`;
- `Permissions-Policy`;
- `Content-Security-Policy`.

CSP разделен по типам endpoints. Для API политика строгая. Для docs endpoints политика мягче, потому что Swagger/ReDoc требуют scripts/styles.

## Глава 12. Docker

Dockerfile'ы переведены на multi-stage build.

Раньше проблема была такая:

1. Использовался один runtime stage.
2. В runtime попадали `build-essential`, compiler toolchain и `curl`.
3. Образ был тяжелее.
4. Attack surface была больше.
5. `curl` мог быть инструментом post-exploitation.

Теперь схема такая:

1. `builder` stage ставит build tools.
2. В builder устанавливаются Python dependencies.
3. Runtime stage начинается с чистого `python:3.12-slim`.
4. В runtime копируется только установленный Python package set и service code.
5. Runtime запускается от non-root user.
6. Healthcheck использует стандартный Python `urllib.request`, а не `curl`.

Также добавлен `.dockerignore`, чтобы в Docker context не попадали:

- `.git`;
- `.venv`;
- `.codex`;
- caches;
- `.env` файлы;
- `__pycache__`.

Это ускоряет сборку, уменьшает риск случайной утечки secrets и предотвращает раздутый build context.

## Глава 13. Docker Compose

В проекте есть dev и prod compose-файлы.

Dev compose поднимает:

- Postgres для auth-service;
- Postgres для user-service;
- Redis;
- auth-service;
- user-service;
- api-gateway.

Prod compose дополнительно усиливает runtime:

- `read_only: true`;
- `tmpfs: /tmp`;
- `cap_drop: ALL`;
- `no-new-privileges:true`;
- internal backend network.

Healthcheck'и теперь тоже не используют `curl`. Они проверяют `/v1/health/live` через Python.

Это важно, потому что если убрать `curl` из runtime-образа, но оставить compose healthcheck на `curl`, контейнер будет падать в unhealthy state.

## Глава 14. CI/CD

GitHub Actions разделены на несколько workflow:

- `ci.yml`;
- `security.yml`;
- `deploy.yml`.

### CI

CI делает:

1. Checkout.
2. Setup Python.
3. Install dependencies.
4. Compile check.
5. Tests for auth-service.
6. Tests for user-service.
7. Tests for api-gateway.
8. Tests for notification-service.

### Security workflow

Security workflow теперь делает:

1. Устанавливает зависимости.
2. Запрещает `python-jose`.
3. Запрещает runtime `assert` в service code.
4. Запускает Bandit.
5. Запускает security/integration tests.
6. Собирает Docker images.
7. Сканирует images через Trivy.

Это важный шаг: security теперь не только "написана в коде", но и закреплена автоматикой.

### Deploy workflow

Deploy workflow собирает images для:

- auth-service;
- user-service;
- api-gateway;
- notification-service.

## Глава 15. Dependabot и supply chain

Добавлен `.github/dependabot.yml`.

Dependabot отслеживает:

- pip dependencies в `auth-service`;
- pip dependencies в `user-service`;
- pip dependencies в `api-gateway`;
- pip dependencies в `notification-service`;
- pip dependencies в `shared/python`;
- GitHub Actions;
- Docker dependencies.

Это важно, потому что locked dependencies безопасны только до момента появления CVE. Если никто не следит за обновлениями, pinned версии превращаются в долг.

Dependabot помогает не забывать о security updates.

## Глава 16. Shared Python package

`shared/python` содержит общие контракты и утилиты.

Раньше архитектурный риск был в том, что shared-код можно использовать через `PYTHONPATH`. Для локальной разработки это удобно, но для production rolling deploys это риск.

Проблема:

1. Один сервис может быть задеплоен со старой версией shared-контракта.
2. Другой сервис может ожидать новую версию.
3. Во время rolling update контракт может временно разъехаться.

Что сделано сейчас:

- добавлен `__version__`;
- добавлен README;
- зафиксировано правило: production должен ставить `shared-python` как versioned internal artifact.

Следующий шаг в будущем:

- настроить build/release pipeline для shared package;
- публиковать `shared-python==x.y.z` во внутренний package registry;
- сервисы должны зависеть от конкретной версии.

## Глава 17. Observability

В сервисах есть директории `observability/`.

Сейчас это заготовка, а не полноценный distributed tracing. Но сама структура уже показывает, что проект готов к расширению.

Что можно добавить дальше:

- OpenTelemetry instrumentation для FastAPI;
- trace propagation через gateway;
- spans для DB/Redis/httpx;
- Prometheus metrics;
- structured logs with request id;
- dashboards;
- alerts.

Это следующий уровень зрелости. Без tracing в production трудно разбирать latency и межсервисные проблемы.

## Глава 18. Локальный запуск

Базовый путь локального запуска:

1. Установить зависимости:

```bash
make deps
```

2. Сгенерировать env-файлы:

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

5. Проверить health:

```bash
curl http://localhost:8000/v1/health/live
curl http://localhost:8001/v1/health/live
curl http://localhost:8002/v1/health/live
```

6. Запустить тесты:

```bash
make test
```

Для notification-service сейчас есть локальная команда:

```bash
make run-notification
```

## Глава 19. Тестирование

Тесты разделены по сервисам.

Auth-service покрывает:

- JWT behavior;
- password service;
- refresh token rotation;
- 2FA flow;
- password reset;
- brute-force privacy;
- validation sanitization;
- audit sanitization;
- config security.

User-service покрывает:

- access token validation;
- RBAC service;
- permission guard;
- validation sanitization;
- security helpers.

API gateway покрывает:

- routing service;
- header sanitization;
- access token verification;
- public/protected endpoint logic;
- client IP handling.

Notification-service покрывает:

- health handlers;
- readiness;
- security headers middleware.

Есть также e2e auth security flow через gateway.

## Глава 20. Production checklist

Перед production нужно проверить:

1. `SERVICE_ENV=production`.
2. `COOKIE_SECURE=true`.
3. Explicit `CORS_ALLOWED_ORIGINS`.
4. Нет wildcard CORS.
5. JWT algorithm - asymmetric, например `RS256`.
6. Private/public keys в PEM format.
7. Peppers длинные и случайные.
8. Redis защищен паролем.
9. DB passwords не дефолтные.
10. TLS termination настроен.
11. Gateway стоит перед сервисами.
12. Internal network закрыта от внешнего мира.
13. CI проходит.
14. Trivy не находит HIGH/CRITICAL issues.
15. Bandit не находит medium/high issues.
16. Dependabot включен.
17. Secrets не попадают в image context.
18. Docker runtime работает non-root.
19. Capabilities сброшены.
20. Read-only filesystem включен там, где возможно.

## Глава 21. Что еще можно улучшить

Проект уже закрыл важные security и architecture issues, но следующие шаги остаются:

1. Полноценный OpenTelemetry tracing.
2. Centralized gateway-level permission policy.
3. Centralized rate limiting на gateway.
4. Internal package release pipeline для `shared-python`.
5. Настоящая notification delivery architecture.
6. Event-driven коммуникация через брокер.
7. More integration tests with real Postgres/Redis.
8. SBOM generation.
9. Image signing.
10. Deployment manifests для Kubernetes или Nomad.

Это уже не багфиксы, а следующий этап развития платформы.

## Глава 22. Краткая история исправлений

Ниже коротко перечислены проблемы, которые были найдены, и как они были решены.

### Проблема 1. Runtime `assert` в production-коде

`assert` может быть удален Python при запуске с `-O`. Поэтому использовать его для runtime checks опасно.

Решение:

- `assert tokens is not None` заменен на явный `RuntimeError`.
- `assert user is not None` заменен на явный `RuntimeError`.
- В CI добавлен guardrail, который запрещает runtime `assert` в service code.

### Проблема 2. Runtime Docker images содержали build tools и curl

В финальный образ попадали compiler toolchain и `curl`.

Решение:

- Dockerfile'ы переведены на multi-stage build.
- Build tools остались только в builder stage.
- Runtime stage стал легче и безопаснее.
- `curl` удален из runtime.
- Healthcheck переписан на Python `urllib.request`.

### Проблема 3. Не было Dependabot

Pinned dependencies были, но автоматического контроля security updates не было.

Решение:

- Добавлен `.github/dependabot.yml`.
- Dependabot следит за pip, Docker и GitHub Actions.

### Проблема 4. `lru_cache` на repository factories

Repository instances могли становиться process-wide singleton objects. Если в будущем в repository появится state, это приведет к трудным багам.

Решение:

- `lru_cache` снят с repository/service factories в auth-service и user-service.
- Stateless сервисы теперь создаются через FastAPI dependency flow без вечного process-level cache.

### Проблема 5. `COOKIE_SECURE=false` был небезопасным дефолтом

Даже если production валидировался, staging мог случайно работать с insecure cookies.

Решение:

- Default изменен на `true`.
- Development env явно задает `COOKIE_SECURE=false`.
- Staging/production требуют `COOKIE_SECURE=true`.
- Добавлены regression tests.

### Проблема 6. Security scanning в CI был недостаточным

Был grep guardrail против `python-jose`, но не было полноценного SAST/image scanning.

Решение:

- Добавлен Bandit.
- Добавлен Trivy image scan.
- Добавлен no-runtime-assert guardrail.

### Проблема 7. Notification-service был пустым scaffold

Файлы существовали, но сервис не был доведен до тестируемого состояния.

Решение:

- Добавлен минимальный health-only сервис.
- Добавлены config, schemas, middleware, tests, Dockerfile, requirements.lock.
- README явно помечает сервис как WIP.

### Проблема 8. Shared code не имел versioning boundary

Shared package был полезен, но production-подход через mutable `PYTHONPATH` рискован.

Решение:

- Добавлен `__version__`.
- Добавлен README с правилом versioned internal package.
- Следующий шаг - release pipeline для `shared-python`.

## Глава 23. Итог

Проект теперь выглядит как крепкая security-first backend platform foundation.

Самые критичные ошибки исправлены:

- runtime `assert` убраны;
- Docker runtime hardened;
- security scanning добавлен;
- dependency updates автоматизированы;
- cookie security усилена;
- repository cache risk снят;
- notification-service перестал быть пустым каталогом;
- shared package получил versioning direction.

Оставшиеся задачи - это уже не срочные уязвимости, а развитие архитектуры: tracing, centralized gateway policy, shared package release pipeline, полноценный notification delivery и более глубокая production automation.

## Глава 24. Второй цикл hardening после глубокого аудита

После следующего аудита проект прошел еще один цикл укрепления. На этом этапе фокус был уже не на очевидных ошибках вроде runtime `assert` или Docker runtime, а на более тонких production-рисках: рассинхрон политики JWT между сервисами, жизнь access token после logout, слабые границы proxy headers, distributed brute-force для password reset и риск случайного коммита локальной книги.

### 24.1. Единая JWT policy

Проблема была в том, что auth-service выпускал access tokens с `iat` и `nbf`, но api-gateway и user-service не требовали эти claims при валидации. Формально токен с валидной подписью, `exp`, `aud` и `iss` проходил бы gateway/user-service даже без temporal claims.

Решение:

- api-gateway теперь требует `iat` и `nbf` при decode access token;
- user-service теперь требует `iat` и `nbf` при decode access token;
- добавлены regression tests на токен без temporal claims;
- auth-service дополнительно требует `sid` для access token и `sid/family_id` для refresh token.

### 24.2. Access session revocation

Раньше logout и password reset отзывали refresh token family и sessions в auth database, но уже выданный access token мог жить до `exp`. Это стандартный компромисс JWT, но для security-first проекта лучше иметь механизм быстрой инвалидции хотя бы для текущей session.

Решение:

- добавлен Redis key `access_session_revoked:{sid}`;
- auth-service ставит этот marker при logout/revoke refresh token;
- auth-service ставит markers для активных sessions при password reset;
- refresh token reuse detection теперь передает `session_id`, чтобы можно было отозвать access session;
- api-gateway, user-service и auth-service проверяют Redis marker перед принятием access token.

Это не превращает JWT в полностью stateful token, но закрывает самый опасный сценарий: пользователь сделал logout или reset password, а старый access token продолжает спокойно работать на protected endpoints.

### 24.3. Production config validators в gateway и user-service

Auth-service уже запрещал опасные production-конфигурации, но gateway и user-service были мягче.

Решение:

- staging/production теперь требуют asymmetric JWT algorithm;
- wildcard CORS запрещен;
- пустой CORS в deployed env запрещен;
- public key в deployed env должен быть PEM-like;
- добавлены tests для production guardrails.

### 24.4. Password reset brute-force стал сильнее

Код password reset остается шестизначным, но brute-force защита теперь работает не только на пару `email:ip`, а также на account-level scope.

Решение:

- добавлен scope `password_reset_account`;
- неудачная попытка reset теперь увеличивает счетчик и по `email:ip`, и по `email`;
- успешный reset очищает оба scope;
- это уменьшает риск distributed brute-force с разных IP.

Следующий идеальный шаг - заменить шестизначный код на high-entropy reset token или добавить отдельную user-level attempt таблицу с audit trail.

### 24.5. Gateway header hardening

Gateway уже очищал request headers от hop-by-hop и forged forwarded headers. Но response headers от upstream были слишком свободными.

Решение:

- gateway теперь удаляет `Set-Cookie`, `Server`, `X-Powered-By` из upstream response;
- добавлен regression test;
- это снижает риск, что скомпрометированный downstream посадит cookie на gateway domain.

### 24.6. Git hygiene для книги и секретов

Книга проекта должна оставаться локальным рабочим документом и никогда не уходить в Git.

Решение:

- добавлен tracked `.gitignore`;
- `docs/project-book.md` добавлен в ignore rules;
- `.env`, PEM/secrets, caches и runtime artifacts тоже защищены ignore rules;
- новый code commit собирается от `origin/main`, чтобы не протащить старый локальный docs-коммит.

### 24.7. Code quality hardening

Также исправлены несколько менее заметных, но важных вещей:

- убраны private imports `httpx._types`;
- mutable default `{}` в shared audit contract заменен на `Field(default_factory=dict)`;
- `X-Request-ID` теперь нормализуется и ограничивается по длине;
- `/tokens/revoke` получил rate limiting.

### 24.8. Что было проблемой и как решено коротко

- Access token жил после logout/reset password - добавлен Redis marker revoked sessions и проверки во всех сервисах.
- JWT validation была разной в сервисах - выровнены required claims и добавлены tests.
- Gateway/user-service могли стартовать с плохим production config - добавлены deployed validators.
- Password reset был слабее против distributed brute-force - добавлен account-level brute-force scope.
- Gateway пропускал опасные response headers - добавлена фильтрация `Set-Cookie`, `Server`, `X-Powered-By`.
- Локальная книга могла случайно попасть в Git - добавлен `.gitignore`, книга остается ignored local file.

# Dark Mystery's — Modelo de datos

> Diccionario de datos completo. 24 tablas. Los libros (ledger) son
> **append-only**; las correcciones se hacen con asientos compensatorios.

Convenciones: toda tabla de negocio tiene `created_at`/`updated_at` (UTC) vía
`TimestampMixin`. Las claves foráneas están indexadas. Los importes de dinero y
los puntos son enteros (sin decimales).

---

## 1. Núcleo institucional

### `houses` — Casas
| Campo | Tipo | Notas |
|---|---|---|
| `id` | int PK | |
| `code` | str(20) UNIQUE | `CORVUS`, `AEGIS`, `UMBRA`, `NOCTURNA` |
| `name` | str(80) | Corvus, Aegis, Umbra, Casa Nocturna |
| `virtues` | str | Corvus: Ambición/Inteligencia/Independencia; Aegis: Disciplina/Protección/Compromiso; Umbra: Astucia/Sigilo/Oscuridad |
| `founder` | str | Aurelian Corvus (1706), Helios Aegis (1698), Nyxus Umbrae (1712) |
| `founded_year` | int | |
| `symbols` | str | Cuervo y serpiente / Dragón / Calavera y murciélago / Serpiente |
| `colors` | str | Azul profundo y negro / Verde y plata / Negro y blanco / Gris lunar |
| `heart_color` | str | azul / verde / morado / gris lunar |
| `heart_hex` | str(9) | `#3B82F6` / `#22C55E` / `#A855F7` / `#9CA3AF` |
| `is_competing` | bool | `false` para Casa Nocturna (no compite en la Copa) |
| `counter` | int | último número de cuenta emitido **en esa Casa** |
| `meta` | JSON | |

### `roles` — Roles (catálogo)
`code` UNIQUE, `name`, `description`. Semilla: ADMINISTRADOR, JEFE_DE_CASA,
SUBJEFE_DE_CASA, BANQUERO, ESTUDIANTE.

### `users` — Usuarios
| Campo | Tipo | Notas |
|---|---|---|
| `id` | int PK | |
| `identifier` | str(20) UNIQUE | `DU01` (inicial nombre + inicial Casa + nº) |
| `seq_number` | int | número dentro de la Casa |
| `display_name` | str(120) | |
| `email` | str(255) UNIQUE | obligatorio y verificado tras primer ingreso |
| `email_verified` | bool | |
| `photo_url` | str(500) | |
| `password_hash` | str(255) | bcrypt; nunca texto plano |
| `role` | str(40) | |
| `status` | str(40) | PENDIENTE_DE_ACTIVACION / ACTIVA / CONGELADA / DADA_DE_BAJA |
| `house_id` | FK houses | |
| `timezone` | str(64) | por usuario (default America/Argentina/Buenos_Aires) |
| `locale` | str(10) | |
| `token_version` | int | se incrementa para invalidar sesiones |
| `last_login_at` | datetime | |
| `failed_login_count` | int | |
| `locked_until` | datetime | bloqueo temporal por intentos |
| `is_director` | bool | las dos directoras |
| `meta` | JSON | |

Restricción única: `uq_user_house_seq` (`house_id`, `seq_number`).

### `auth_tokens` — Tokens de un solo uso
`user_id` FK, `token_hash` str(128) UNIQUE (SHA-256, nunca el token plano),
`purpose` (INVITACION / RESET_PASSWORD / VERIFICAR_EMAIL), `expires_at`,
`used_at`, `meta`.

---

## 2. Banco de Lunarias

### `wallets` — Billeteras
`user_id` FK UNIQUE, `balance` int firmado (puede ser negativo = deuda),
`currency` = `LUNARIAS`. La propiedad `debt` devuelve `-balance` si es negativo.

### `wallet_transactions` — Cabecera de movimiento
| Campo | Notas |
|---|---|
| `reference` | UNIQUE, legible (p. ej. `TX-20260101-XXXX`) |
| `type` | DEPOSITO, TRANSFERENCIA, COMPRA, REEMBOLSO, PENALIZACION, AJUSTE_POSITIVO/NEGATIVO, REVERSION, RECOMPENSA_ACTIVIDAD, CANCELACION |
| `amount` | importe total (positivo) |
| `status` | PENDIENTE_APROBACION / COMPLETADA / RECHAZADA / REVERTIDA |
| `author_id` | quién la ejecuta |
| `counterparty_id` | contraparte (transferencias) |
| `idempotency_key` | UNIQUE (anti-duplicados) |
| `purchase_id` / `refund_id` / `event_id` | vínculos |
| `reverses_transaction_id` | si es una reversión |
| `meta` | JSON |

### `wallet_entries` — Asientos (doble entrada)
`transaction_id` FK, `wallet_id` FK, `user_id` FK, `amount` int (+ crédito /
− débito), `balance_after` int. **Invariante:** para transferencias, la suma de
`amount` = 0; para cada wallet, `balance == último balance_after`.

### `approvals` — Aprobaciones de ajustes grandes
`transaction_id`, `requested_by`, `amount`, `reason`, `status`,
`resolved_by`, `resolved_at`. Se crea cuando el ajuste supera
`LARGE_ADJUSTMENT_THRESHOLD` (50 000).

---

## 3. Tienda

### `products` — Catálogo (configurable, sin tocar código)
`name`, `description`, `image_url`, `price`, `published`,
`purchase_limit_per_day`, `activation_limit_per_day`, `conditions`,
`activation_requirements`, `special_rules`, `availability`, `affects_points`,
`requires_approval`, `stock` (None = ilimitado), `meta`.

### `purchases` — Compras
`user_id`, `product_id`, **`product_name`** y **`price_paid`** (snapshots
históricos), `house_id` (Casa al momento), `status` (PENDIENTE_ACTIVACION /
ACTIVADO / RECHAZADO / CANCELADO / REEMBOLSADO), `conditions_snapshot`,
`idempotency_key` UNIQUE, `purchased_at`.

### `product_activations` — Activaciones (compra ≠ activación)
`purchase_id` FK UNIQUE, `user_id`, `event_id`, `status` (PENDIENTE / ACTIVADO /
RECHAZADO / CANCELADO / REEMBOLSADO), `reason`, `handled_by`, `handled_at`.

### `activation_history` — Historial de estados de activación
`activation_id`, `from_status`, `to_status`, `reason`, `author_id`.

### `refunds` — Reembolsos
`purchase_id`, `requested_by`, `amount`, `reason`, `status` (SOLICITADO /
APROBADO / RECHAZADO / PROCESADO), `processed_by`, `processed_at`,
`transaction_id`. Ventana de 15 días; solo si el producto no fue usado.

---

## 4. Copa (Puntos)

### `events` — Eventos / dinámicas
`name`, `type` (DINAMICA / RETO_GRUPAL / RETO_INDIVIDUAL / FLASH_STICKER /
ACTIVIDAD_ESPECIAL / DESEMPATE), `status` (BORRADOR / CONFIRMADA / RECTIFICADA /
CANCELADA), `house_responsible_id`, `responsible_user_id`, `scheduled_at`,
`double_points`, `rounds_played`, `created_by`, `confirmed_at`, `confirmed_by`,
`compensation_applied`, `meta`.

### `event_participants` — Participantes
`event_id`, `user_id` (opcional: permite registrar sin cuenta),
`display_name`, `house_id`, `arrival_order`, `effective_podium` (1/2/3/None),
`points_awarded`, `is_collaborator`, `answer_text`, `partis_awarded`, `meta`.

### `point_ledger` — Libro de puntos (append-only)
`house_id`, `user_id` (opcional), `event_id`, `type` (DINAMICA_PODIO,
PARTICIPACION, RETO_GRUPAL, RETO_INDIVIDUAL, COMPENSACION, PENALIZACION,
CASA_NOCTURNA, RECOMPENSA_ORGANIZACION, AJUSTE, RECTIFICACION), `points`
(firmado), `reason`, `author_id`, `reverses_id`, `meta`.

### `house_scores` — Caché de puntaje por Casa
`house_id` UNIQUE, `points`. **Invariante de reconciliación:**
`house_scores.points == sum(point_ledger.points where house_id = ...)`.

---

## 5. Partis

### `participation_records` — Registro de participación (append-only)
`user_id`, `house_id`, `event_id`, `partis`, `reason`, `author_id`,
`reverses_id`. Reglas: 4 rondas = 1 parti; >4 o completado = 2; <4 = 0; reto
grupal = 1 extra solo a colaboradores; reto individual = 1 por entrega válida;
flash sticker = 1 al primero; fuera de tiempo = 0.

---

## 6. Sanciones

### `sanctions` — Penalizaciones
`target_user_id` o `target_house_id`, `resource` (PUNTOS | LUNARIAS), `amount`,
`reason`, `rule_ref`, `author_id`, `transaction_id` (si es lunaria),
`ledger_id` (si es punto). Los administradores sancionan globalmente; los jefes
solo a su propia Casa.

---

## 7. Calendario

### `schedules` — Horarios
`week_start` (ISO lunes), `day_of_week` (0=lunes), `date`, `house_id`,
`activity_type`, `activity_name`, `start_time` (HH:MM), `end_time`,
`responsible_user_id`, `status` (PROGRAMADA / EN_CURSO / FINALIZADA / CANCELADA /
COMPENSADA), `notes`, `created_by`, `meta`.

### `schedule_changes` — Cambios de horario
`schedule_id`, `change_type` (HORARIO / CANCELACION / INTERCAMBIO /
COMPENSACION), `detail`, `author_id`.

---

## 8. Reclamaciones, auditoría, notificaciones, configuración

### `complaints` — Reclamaciones
`requester_id`, `event_id`, `subject`, `reason`, `status` (ABIERTA / EN_REVISION /
RESUELTA / RECHAZADA), `resolution`, `resolved_by`, `resolved_at`.

### `audit_logs` — Auditoría (append-only)
`actor_id`, `actor_identifier`, `action`, `entity_type`, `entity_id`, `before`
(JSON), `after` (JSON), `ip`, `meta`, `created_at`. Sin `updated_at`.

### `notifications` — Notificaciones internas
`user_id`, `kind` (SISTEMA / BANCO / TIENDA / COPA / RECLAMACION / ADMIN),
`title`, `body`, `link`, `read`, `created_at`.

### `settings` — Configuración
`key` PK, `value` JSON, `description`. Permite ajustar reglas sin desplegar
código (umbrales, límites, offsets de tienda, etc.).

---

## 9. Diagrama de relaciones (simplificado)

```
houses 1───* users 1───1 wallets 1───* wallet_entries
   │           │  │                          │
   │           │  └──* auth_tokens           └──* wallet_transactions
   │           │  │                                   │
   │           │  └──* participation_records          ├──* approvals
   │           │                                      ├──* refunds
   │           │                                      └──* sanctions
   │           ├──* purchases 1───1 product_activations 1───* activation_history
   │           │       │
   │           │       └──* refunds
   │           ├──* notifications
   │           └──* complaints
   │
   ├──1 house_scores
   ├──* point_ledger
   ├──* events 1───* event_participants
   └──* schedules 1───* schedule_changes
```

---

## 10. Invariantes de integridad

1. `wallet.balance` == suma de `wallet_entries.amount` de esa wallet.
2. `wallet_entries.balance_after` == saldo resultante tras aplicar el asiento.
3. Transferencia: suma de `amount` de sus asientos == 0.
4. `house_scores.points` == suma de `point_ledger.points` de esa Casa.
5. Ningún movimiento se borra; se revierte con asiento compensatorio.
6. `idempotency_key` única evita duplicar operaciones de dinero.
7. `identifier` único y permanente; `seq_number` único por Casa.

Estas invariantes se comprueban con los endpoints `…/reconcile` y con la suite de
pruebas (`tests/`).

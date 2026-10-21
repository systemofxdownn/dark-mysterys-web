# Dark Mystery's — Plan de pruebas

> Criterios de aceptación verificables. Ninguna función se marca como terminada
> sin que sus pruebas pasen. Ejecutar con `pytest` desde `backend/`.

```bash
cd backend
pytest -q
```

---

## 1. Estrategia

- **Pruebas de integración de API** con `fastapi.testclient.TestClient` sobre una
  base de datos SQLite temporal por sesión de test (aislada).
- Se cubren los **caminos críticos** de negocio y los **límites de seguridad**.
- Cada test es independiente y deja la base en estado consistente.

Fixtures (`tests/conftest.py`):
- `client`: app con base temporal y seed mínimo.
- `admin_token`, `leader_token`, `banker_token`, `student_token`: sesiones por rol.
- Helpers para crear usuarios y consultar saldos/puntajes.

---

## 2. Casos por área

### 2.1 Autenticación y cuentas
| # | Caso | Resultado esperado |
|---|---|---|
| A1 | Login con credenciales válidas | 200 + token |
| A2 | Login con contraseña incorrecta | 401 y cuenta de intentos |
| A3 | Bloqueo tras N intentos fallidos | 423/401 con `locked_until` |
| A4 | Crear usuario (admin) genera identificador por Casa | `DN01`, `CA01`… |
| A5 | Numeración independiente por Casa | Corvus #1 y Umbra #1 coexisten |
| A6 | Identificador único y no reutilizado | dos usuarios nunca comparten id |
| A7 | Primer ingreso con token de invitación | define contraseña + email verificado |
| A8 | Token de invitación de un solo uso | segundo uso falla |
| A9 | Recuperación de contraseña con email verificado | token válido cambia la clave |
| A10 | Congelar cuenta invalida sesiones previas | token anterior → 401/403 |
| A11 | Cuenta congelada no recibe nada | operaciones rechazadas |
| A12 | Contraseña se guarda hasheada | `password_hash` ≠ texto plano |

### 2.2 Banco (Lunarias)
| # | Caso | Resultado esperado |
|---|---|---|
| B1 | Depósito acredita saldo | balance += importe |
| B2 | Transferencia mueve saldo y crea 2 asientos | suma de asientos = 0 |
| B3 | Transferencia sin saldo suficiente | rechazada |
| B4 | Idempotencia de transferencia | reintento no duplica |
| B5 | Ajuste bajo umbral | se aplica directo |
| B6 | Ajuste sobre umbral | queda PENDIENTE_APROBACION |
| B7 | Aprobación de ajuste grande | se aplica tras aprobar |
| B8 | Penalización deja deuda (saldo negativo) | balance < 0 y `debt` > 0 |
| B9 | Ganancias futuras amortizan la deuda | saldo sube hacia 0 |
| B10 | Reversión crea asiento compensatorio | no se borra el original |
| B11 | Reconciliación de wallet | balance == suma de asientos |
| B12 | Reembolso acredita solo si aprobado y no usado | según reglas |

### 2.3 Tienda
| # | Caso | Resultado esperado |
|---|---|---|
| C1 | Compra debita saldo y crea compra + activación | estado PENDIENTE_ACTIVACION |
| C2 | Compra sin saldo | rechazada |
| C3 | Compra con cuenta congelada | rechazada |
| C4 | Límite 8 compras/día por Casa | la 9ª rechazada |
| C5 | Límite 4 activaciones/día por Casa | la 5ª rechazada |
| C6 | Tienda cerrada fuera de horario | rechazada |
| C7 | Activación hasta 15 min antes del evento | fuera de ventana rechazada |
| C8 | Reembolso solo dentro de 15 días | fuera de ventana rechazado |
| C9 | Reembolso solo si el producto no fue usado | usado → rechazado |
| C10 | Producto con stock limitado | se agota correctamente |
| C11 | Catálogo configurable sin código | crear/editar producto refleja en tienda |

### 2.4 Puntos / Copa
| # | Caso | Resultado esperado |
|---|---|---|
| D1 | Podio estándar 6000/5000/4000 + 1500 resto | puntos correctos |
| D2 | Máx. una persona por Casa en podio | posiciones se corren |
| D3 | Excepción 2 Casas: una Casa con dos lugares | 6000/5000/4000 por llegada |
| D4 | Reto grupal 40000/30000/20000 a la Casa | puntos correctos |
| D5 | Reto individual 16000 a la Casa | puntos correctos |
| D6 | Confirmar evento escribe puntos una sola vez | no hay doble conteo |
| D7 | Rectificar revierte asientos previos | vuelve a BORRADOR |
| D8 | Compensación 7500 | acreditada |
| D9 | Dinámica de doble puntaje | puntos ×2 |
| D10 | Penalización de puntos (admin global) | resta a la Casa |
| D11 | Penalización de jefe solo su Casa | otra Casa → rechazado |
| D12 | Reconciliación de puntos | house_scores == suma ledger |
| D13 | Partis: 4 rondas = 1; >4 = 2; <4 = 0 | según regla |
| D14 | Reto grupal: parti extra solo colaboradores | correcto |
| D15 | Flash sticker: 1 parti al primero | correcto |
| D16 | Fuera de tiempo = 0 partis | correcto |

### 2.5 Permisos (seguridad)
| # | Caso | Resultado esperado |
|---|---|---|
| E1 | Estudiante no ve el marcador | 403 |
| E2 | Estudiante no crea usuarios | 403 |
| E3 | Banquero no accede a Puntos | 403 |
| E4 | Jefe no carga puntos | 403 |
| E5 | Jefe no sanciona otra Casa | 403 |
| E6 | Solo admin ve auditoría | 403 para el resto |
| E7 | Solo admin gestiona configuración | 403 para el resto |
| E8 | Sin token → 401 | en todos los endpoints privados |
| E9 | Token de usuario congelado → bloqueado | 401/403 |

### 2.6 Reportes y auditoría
| # | Caso | Resultado esperado |
|---|---|---|
| F1 | Export CSV respeta permisos | solo lo permitido |
| F2 | Export XLSX válido | archivo abre y tiene filas |
| F3 | Operaciones sensibles quedan en auditoría | registro presente |
| F4 | Auditoría es append-only | sin updates/borrados |

---

## 3. Criterios de aceptación globales

- Todos los tests en verde.
- Reconciliación de wallets y de puntajes sin diferencias.
- Ninguna operación de dinero duplicada con la misma `idempotency_key`.
- Ningún endpoint privado accesible sin token válido.
- Cuentas congeladas bloqueadas en todas las operaciones.
- Identificadores únicos y numeración por Casa correcta.

---

## 4. Cobertura mínima objetivo

| Área | Cobertura objetivo |
|---|---|
| Autenticación / cuentas | 100% de casos críticos |
| Banco | 100% de casos críticos |
| Tienda | 100% de casos críticos |
| Puntos / Copa | 100% de casos críticos |
| Permisos | 100% de casos críticos |

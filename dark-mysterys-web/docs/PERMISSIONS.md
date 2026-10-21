# Dark Mystery's — Matriz de permisos (RBAC)

> La autorización se aplica **siempre en el backend**. Ocultar un botón en el
> frontend no es seguridad. Cada endpoint declara el permiso que exige mediante
> `require_permission(...)` y, cuando aplica, valida además la propiedad del
> recurso (por ejemplo, un jefe solo opera sobre su propia Casa).

---

## 1. Roles

| Código | Nombre | Descripción |
|---|---|---|
| `ADMINISTRADOR` | Administrador | Dirección / Casa Nocturna. Acceso global. |
| `JEFE_DE_CASA` | Jefe de Casa | Lidera una Casa competidora. |
| `SUBJEFE_DE_CASA` | Subjefe de Casa | Apoya al jefe; mismos permisos de gestión de Casa. |
| `BANQUERO` | Banquero | Opera el banco de Lunarias. Sin acceso a Puntos. |
| `ESTUDIANTE` | Estudiante | Miembro base. Solo lo propio. |

`JEFE_DE_CASA` y `SUBJEFE_DE_CASA` comparten el conjunto de permisos
`_HOUSE_LEADER`. La Casa Nocturna (gobierno) **no compite** en la Copa.

---

## 2. Matriz por área

Leyenda: **✓** permitido · **—** denegado · **(propia)** limitado a la propia
Casa / a lo propio.

### 2.1 Usuarios y cuentas
| Permiso | ADMIN | JEFE | SUBJEFE | BANQUERO | ESTUDIANTE |
|---|:--:|:--:|:--:|:--:|:--:|
| Crear usuarios | ✓ | — | — | — | — |
| Editar / dar de baja / reactivar | ✓ | — | — | — | — |
| Ver todos los usuarios | ✓ | — | — | — | — |
| Ver usuarios de su Casa | ✓ | ✓ | ✓ | — | — |
| Asignar rol | ✓ | — | — | — | — |
| Asignar Casa | ✓ | — | — | — | — |
| Congelar / descongelar cuentas | ✓ | — | — | — | — |

### 2.2 Banco (Lunarias)
| Permiso | ADMIN | JEFE | SUBJEFE | BANQUERO | ESTUDIANTE |
|---|:--:|:--:|:--:|:--:|:--:|
| Ver su propia billetera | ✓ | ✓ | ✓ | ✓ | ✓ |
| Transferir | ✓ | ✓ | ✓ | ✓ | ✓ |
| Ver todas las billeteras | ✓ | — | — | ✓ | — |
| Depositar | ✓ | — | — | ✓ | — |
| Ajustar | ✓ | — | — | ✓ | — |
| Aprobar ajustes grandes | ✓ | — | — | — | — |

> Nota: el Banquero **no** puede aprobar sus propios ajustes grandes; requiere un
> Administrador (segundo par de ojos).

### 2.3 Tienda
| Permiso | ADMIN | JEFE | SUBJEFE | BANQUERO | ESTUDIANTE |
|---|:--:|:--:|:--:|:--:|:--:|
| Gestionar catálogo | ✓ | — | — | — | — |
| Comprar | ✓ | ✓ | ✓ | ✓ | ✓ |
| Ver sus compras | ✓ | ✓ | ✓ | ✓ | ✓ |
| Gestionar activaciones | ✓ | — | — | — | — |
| Solicitar reembolso | ✓ | ✓ | ✓ | ✓ | ✓ |
| Aprobar reembolso | ✓ | — | — | — | — |

### 2.4 Puntos / Copa
| Permiso | ADMIN | JEFE | SUBJEFE | BANQUERO | ESTUDIANTE |
|---|:--:|:--:|:--:|:--:|:--:|
| Ver marcador (3 Casas) | ✓ | ✓ | ✓ | — | — |
| Cargar / confirmar / rectificar | ✓ | — | — | — | — |
| Sancionar puntos | ✓ | ✓ (propia) | ✓ (propia) | — | — |
| Sancionar lunarias | ✓ | ✓ (propia) | ✓ (propia) | — | — |

> Los jefes/subjefes **ven** las tres Casas (para la Copa) pero **no** cargan
> puntos: eso es potestad de Dirección. Las sanciones de jefes se restringen a su
> propia Casa (`SANCTIONS_OWN_HOUSE_ONLY`).

### 2.5 Eventos y calendario
| Permiso | ADMIN | JEFE | SUBJEFE | BANQUERO | ESTUDIANTE |
|---|:--:|:--:|:--:|:--:|:--:|
| Gestionar eventos | ✓ | — | — | — | — |
| Cargar eventos de su día | ✓ | ✓ | ✓ | — | — |
| Gestionar calendario | ✓ | — | — | — | — |
| Gestionar calendario de su día | ✓ | ✓ | ✓ | — | — |

### 2.6 Participaciones (Partis)
| Permiso | ADMIN | JEFE | SUBJEFE | BANQUERO | ESTUDIANTE |
|---|:--:|:--:|:--:|:--:|:--:|
| Ver todas | ✓ | — | — | — | — |
| Ver las de su Casa | ✓ | ✓ | ✓ | — | — |
| Gestionar | ✓ | — | — | — | — |

### 2.7 Estadísticas, informes y administración
| Permiso | ADMIN | JEFE | SUBJEFE | BANQUERO | ESTUDIANTE |
|---|:--:|:--:|:--:|:--:|:--:|
| Ver estadísticas globales | ✓ | — | — | — | — |
| Ver estadísticas de su Casa | ✓ | ✓ | ✓ | — | — |
| Exportar informes (todo) | ✓ | — | — | — | — |
| Exportar informes (su Casa) | ✓ | ✓ | ✓ | — | — |
| Exportar informes financieros | ✓ | — | — | ✓ | — |
| Crear reclamaciones | ✓ | ✓ | ✓ | ✓ | ✓ |
| Resolver reclamaciones | ✓ | — | — | — | — |
| Ver auditoría | ✓ | — | — | — | — |
| Gestionar configuración | ✓ | — | — | — | — |
| Editar su perfil | ✓ | ✓ | ✓ | ✓ | ✓ |

---

## 3. Reglas transversales

1. **Estado de cuenta:** solo las cuentas `ACTIVA` operan. `CONGELADA` y
   `DADA_DE_BAJA` no reciben nada (ni puntos, ni recompensas, ni
   transferencias, ni reembolsos) y sus sesiones quedan invalidadas.
2. **Propiedad del recurso:** los permisos con sufijo `(propia)` exigen
   comparar `recurso.house_id == usuario.house_id`.
3. **Segregación de funciones:** quien solicita un ajuste grande no puede
   aprobarlo; el Banquero deposita/ajusta pero no aprueba lo grande.
4. **Separación de sistemas:** el Banquero gestiona Lunarias pero **no** ve ni
   toca Puntos. Dirección gestiona ambos.
5. **Dirección (Administrador):** único rol que crea usuarios, asigna roles/Casas,
   gestiona el catálogo, carga puntos y ve la auditoría.

---

## 4. Implementación

- Constantes en `backend/app/permissions.py` (clase `Perm`).
- Conjuntos por rol: `_ADMIN`, `_HOUSE_LEADER`, `_BANKER`, `_STUDENT`.
- Aplicación: dependencia `require_permission(perm)` en `deps.py`.
- Restricciones de propiedad: verificadas dentro de cada `service`/`router`
  (p. ej. `SANCTIONS_OWN_HOUSE_ONLY`).
- El endpoint `GET /api/auth/me` devuelve la lista de permisos efectivos del
  usuario, de modo que el frontend muestre solo lo permitido — **sin que eso
  sustituya la validación del backend**.

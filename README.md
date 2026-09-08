# ir-remotes

Colección personal de mandos infrarrojos en formato Flipper Zero (`.ir`), pensada
para importarse desde el **GitHub Store** de la app
[IR Blaster Remote](https://github.com/iodn/android-ir-blaster) (`org.nslabs.ir_blaster`).

## Estructura

Un fichero `.ir` por mando, agrupado en carpetas de categoría poco profundas:

```
ir-remotes/
├── ACs/            Aire acondicionado
├── TVs/            Televisores
├── Audio/          Equipos de audio, barras de sonido
├── Proyectores/
└── tools/          Scripts para generar los códigos (no es una categoría de mandos)
```

El listado del GitHub Store **no es recursivo**: cada carpeta que abres es una
petición a la API de GitHub. Por eso el árbol se mantiene plano — dos niveles como
máximo — y no se anida por marca.

## Cómo añadirlo a la app

Settings → Remotes → GitHub Store → añadir repositorio.

- Repo completo:
  `https://github.com/<usuario>/ir-remotes/tree/main`
- Una sola categoría, con su propio alias (recomendado, ahorra un toque y una petición):
  `https://github.com/<usuario>/ir-remotes/tree/main/ACs`

Puedes añadir varios marcadores al mismo repo apuntando a carpetas distintas. Fija
siempre la rama con `/tree/main/` en vez de dejar la URL corta: si algún día
renombras la rama por defecto, los marcadores cortos dejan de funcionar.

## Convenciones

- **Nombre de fichero**: `Marca_Modelo.ir` (p. ej. `Midea_EF-24RD1.ir`). El listado
  ordena alfabéticamente ignorando mayúsculas, con las carpetas primero.
- **Nombre de los botones**: el campo `name:` de dentro del fichero es la etiqueta
  que ves en la app. Cortos y con el mismo criterio en todos los mandos.
- **Sufijo `_TEST`**: fichero de identificación de protocolo, todavía no es un mando
  usable. Se elimina el sufijo cuando se confirma qué códigos responden.

## Límites del GitHub Store

Merece la pena conocerlos porque condicionan cómo se organiza el repo:

| Límite | Valor |
|---|---|
| Tamaño máximo por fichero importable | **512 KB** |
| Peticiones a la API sin token | **60/hora**, globales por IP (no por repo) |
| Peticiones con token personal (PAT) | 5.000/hora |
| Caché de listados de carpeta | 15 min (48 entradas) |
| Caché de ficheros | 6 h (24 entradas, solo ≤128 KB) |

Notas:

- El repo debe ser **público**, o hará falta un PAT con permiso de lectura.
- Al configurar un PAT la app **desactiva la caché persistente en disco** — asume que
  con 5.000 peticiones/hora ya no la necesitas.
- Se ocultan los ficheros y carpetas que empiezan por `.`, pero **no hay filtro por
  extensión**: cualquier fichero suelto en la raíz aparece en el listado. Por eso la
  raíz solo contiene carpetas y este README.

## Estado actual

| Dispositivo | Fichero | Estado |
|---|---|---|
| Midea Solunar EF-24RD1 (24.000 BTU) | `ACs/Midea_EF-24RD1_TEST.ir` | Pendiente de identificar la familia de protocolo |
| LG conductos + control de pared MEZ61995616 | `ACs/LG_MEZ61995616.ir` | **Funcionando** — variante LG2 confirmada en el equipo |

**Midea**: el mando de este equipo es de la serie **RG10**, que en
[IRremoteESP8266](https://github.com/crankyoldgit/IRremoteESP8266) corresponde al
protocolo **Bosch144**. Los otros dos candidatos son **Coolix** (mandos RG52) y
**Midea** de 48 bits (mandos RG57/RG66). El fichero `_TEST` contiene señales de los
tres para averiguar cuál responde; ver `tools/gen_midea_ir.py`.

**LG**: unidad de conductos gobernada por un controlador de pared por cable
`MEZ61995616` (familia `PQRCVSL0` / `PREMTB001`) que lleva receptor de infrarrojos.
El protocolo LG es de 28 bits con firma `0x88` y tiene dos variantes de
temporización con contenido idéntico: **LG** (cabecera 8500/4250 µs) y **LG2**
(3200/9900 µs). **Este equipo responde a LG2**, coherente con que su mando
inalámbrico de fábrica sea de la familia comercial `AKB73315611` / `AKB74955603`.

El generador `tools/gen_lg_ir.py` está validado contra capturas reales de
Flipper-IRDB: construyendo la trama desde sus campos reproduce exactamente
`0x880094D` (frío, 24 °C, ventilador máximo), y los checksums de `0x88C0051`,
`0x8810001` y `0x88C00A6` salen correctos. Las 35 señales del fichero final se
decodifican de vuelta y coinciden con lo que promete el nombre de cada botón.

El fichero se ha ajustado a lo que el equipo acepta de verdad, que es menos que lo
que permite el protocolo:

- **Sin swing vertical ni luz de display.** Ambos códigos son válidos y el equipo
  los ignora, algo esperable en una unidad de conductos: no tiene lamas orientables
  ni display propio.
- **Rangos de temperatura recortados a lo que el equipo acepta**: frío **18–28 °C** y
  calor **20–26 °C**, frente a los 16–30 °C que permite el protocolo. Fuera de esos
  rangos el código emitido es válido pero la unidad lo ignora. Los cuatro límites
  reales viven en `COOL_TEMP_MIN` / `COOL_TEMP_MAX` / `HEAT_TEMP_MIN` /
  `HEAT_TEMP_MAX`, separados a propósito de `TEMP_MIN` / `TEMP_MAX`, que describen el
  formato y no el equipo.

```
python tools/gen_lg_ir.py ACs/LG_MEZ61995616.ir full
python tools/gen_lg_ir.py /tmp/prueba.ir test    # fichero de identificación
```

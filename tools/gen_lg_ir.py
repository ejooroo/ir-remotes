# -*- coding: utf-8 -*-
"""
Genera un fichero Flipper .ir con senales candidatas para un aire LG
gobernado por un controlador de pared MEZ61995616 (linea comercial, conductos).

Protocolo LG A/C segun IRremoteESP8266 (crankyoldgit, src/ir_LG.*):
trama de 28 bits, firma 0x88, con dos variantes de temporizacion:
  - LG   : cabecera 8500/4250 us, bit mark 550 us
  - LG2  : cabecera 3200/9900 us, bit mark 480 us
El contenido de los 28 bits es identico en ambas; solo cambia como se emiten.

Validado contra capturas reales de Flipper-IRDB:
  LG_AC_2 POWER      = 0x880094D  (frio, 24 C, ventilador max, encendido)
  LG_AC_2 Off        = 0x88C0051
  LG_LP1419IVSM SWING= 0x8810001
"""

# ------------------------------------------------------------ temporizaciones
LG_HDR_MARK, LG_HDR_SPACE = 8500, 4250
LG_BIT_MARK = 550

LG2_HDR_MARK, LG2_HDR_SPACE = 3200, 9900
LG2_BIT_MARK = 480

ONE_SPACE, ZERO_SPACE = 1600, 550

# ------------------------------------------------------------ campos de la trama
# union LGProtocol: Sum:4 | Fan:4 | Temp:4 | Mode:3 | :3 | Power:2 | Sign:8
SIGNATURE = 0x88
TEMP_ADJUST = 15
TEMP_MIN, TEMP_MAX = 16, 30

POWER_ON, POWER_OFF = 0b00, 0b11

MODE_COOL, MODE_DRY, MODE_FAN, MODE_AUTO, MODE_HEAT = 0, 1, 2, 3, 4

FAN_LOWEST, FAN_LOW, FAN_MEDIUM = 0, 1, 2
FAN_MAX, FAN_AUTO = 4, 5
FAN_LOW_ALT, FAN_HIGH = 9, 10

# Comandos fijos conocidos
CMD_OFF = 0x88C0051
CMD_SWING_V_TOGGLE = 0x8810001
CMD_LIGHT_TOGGLE = 0x88C00A6


def checksum(state):
    """Suma de los 4 nibbles que hay por encima del nibble de checksum."""
    v = state >> 4
    return sum((v >> (4 * i)) & 0xF for i in range(4)) & 0xF


def lg_state(power_on, mode, temp_c, fan):
    temp_c = max(TEMP_MIN, min(TEMP_MAX, temp_c))
    v = SIGNATURE << 20
    v |= (POWER_ON if power_on else POWER_OFF) << 18
    v |= (mode & 0b111) << 12
    v |= ((temp_c - TEMP_ADJUST) & 0xF) << 8
    v |= (fan & 0xF) << 4
    return v | checksum(v)


def raw(value28, variant):
    """variant: 'LG' o 'LG2'. Devuelve la lista de marcas/espacios en us."""
    if variant == 'LG':
        hdr_m, hdr_s, bit_mark = LG_HDR_MARK, LG_HDR_SPACE, LG_BIT_MARK
    else:
        hdr_m, hdr_s, bit_mark = LG2_HDR_MARK, LG2_HDR_SPACE, LG2_BIT_MARK

    seq = [hdr_m, hdr_s]
    for i in range(27, -1, -1):          # MSB primero
        seq.append(bit_mark)
        seq.append(ONE_SPACE if (value28 >> i) & 1 else ZERO_SPACE)
    seq.append(bit_mark)                 # footer, sin hueco final
    return seq


# ------------------------------------------------------------ capturas reales
# Copiadas literalmente de Lucaslhm/Flipper-IRDB (ACs/LG), como referencia de
# temporizacion real de un mando fisico.
CAPTURE_LG_POWER = (
    "8445 4206 542 1566 541 539 519 534 514 541 517 1564 543 537 521 533 "
    "515 539 519 534 514 540 518 536 512 542 516 537 521 532 516 538 520 "
    "534 514 1568 539 541 517 536 522 1560 547 533 515 1567 540 540 518 "
    "536 512 1570 547 1561 546 534 514 1568 539"
)
CAPTURE_LG2_OFF = (
    "3196 9607 615 1444 589 428 588 428 588 430 613 1444 589 428 588 428 "
    "587 430 588 1446 614 1445 589 429 588 429 588 429 584 434 611 406 "
    "582 483 561 455 561 456 560 456 558 460 557 459 558 1503 559 457 533 "
    "1527 559 457 559 457 586 457 560 1475 584"
)


def block(name, seq):
    data = seq if isinstance(seq, str) else " ".join(str(int(x)) for x in seq)
    return (
        "#\n"
        "name: {}\n"
        "type: raw\n"
        "frequency: 38000\n"
        "duty_cycle: 0.330000\n"
        "data: {}\n".format(name, data)
    )


def build():
    out = ["Filetype: IR signals file\nVersion: 1\n"]
    out.append(
        "# LG conductos + controlador de pared MEZ61995616\n"
        "# Fichero de IDENTIFICACION de variante de temporizacion.\n"
        "# Grupo A = LG2 (cabecera 3200/9900) - apuesta principal, familia\n"
        "#           comercial AKB73315611 / AKB74955603.\n"
        "# Grupo B = LG  (cabecera 8500/4250) - linea domestica.\n"
        "# El contenido de los 28 bits es el mismo en A y B; solo cambia el envio.\n"
    )

    # --- Grupo A: LG2
    out.append(block("A1_LG2_OFF", raw(CMD_OFF, 'LG2')))
    out.append(block("A2_LG2_FRIO_24_AUTO",
                     raw(lg_state(True, MODE_COOL, 24, FAN_AUTO), 'LG2')))
    out.append(block("A3_LG2_FRIO_24_MEDIO",
                     raw(lg_state(True, MODE_COOL, 24, FAN_MEDIUM), 'LG2')))
    out.append(block("A4_LG2_CALOR_22_AUTO",
                     raw(lg_state(True, MODE_HEAT, 22, FAN_AUTO), 'LG2')))
    # Sin swing: en esta instalacion (conductos) no hace nada, asi que como
    # senal de prueba solo daria falsos negativos.
    out.append(block("A6_LG2_OFF_CAPTURA_REAL", CAPTURE_LG2_OFF))

    # --- Grupo B: LG
    out.append(block("B1_LG_OFF", raw(CMD_OFF, 'LG')))
    out.append(block("B2_LG_FRIO_24_AUTO",
                     raw(lg_state(True, MODE_COOL, 24, FAN_AUTO), 'LG')))
    out.append(block("B3_LG_FRIO_24_MEDIO",
                     raw(lg_state(True, MODE_COOL, 24, FAN_MEDIUM), 'LG')))
    out.append(block("B4_LG_CALOR_22_AUTO",
                     raw(lg_state(True, MODE_HEAT, 22, FAN_AUTO), 'LG')))
    out.append(block("B5_LG_FRIO_24_MAX_CAPTURA_REAL", CAPTURE_LG_POWER))

    return "".join(out)


def build_full():
    """Mando completo, ya sabiendo que el equipo responde a LG2."""
    out = ["Filetype: IR signals file\nVersion: 1\n"]
    out.append(
        "# LG conductos + controlador de pared MEZ61995616\n"
        "# Variante LG2 (cabecera 3200/9900 us), confirmada en el equipo.\n"
        "# Cada boton envia el estado completo: modo + temperatura + ventilador.\n"
        "# No existen botones +/- porque el protocolo no funciona asi.\n"
    )

    def lg2(name, value):
        out.append(block(name, raw(value, 'LG2')))

    # --- basicos
    # No se emiten SWING_VERTICAL (0x8810001) ni LUZ_DISPLAY (0x88C00A6):
    # probados en el equipo y no hacen nada. Es coherente con una unidad de
    # conductos, que no tiene lamas orientables ni display propio.
    lg2("OFF", CMD_OFF)
    out.append(block("OFF_CAPTURA_REAL", CAPTURE_LG2_OFF))

    # --- frio: barrido de temperatura con ventilador automatico
    for t in range(TEMP_MIN, TEMP_MAX + 1):
        lg2("FRIO_%d_AUTO" % t, lg_state(True, MODE_COOL, t, FAN_AUTO))

    # --- frio: velocidades de ventilador a 24 C
    for etiqueta, fan in [("V1_MINIMA", FAN_LOWEST), ("V2_BAJA", FAN_LOW),
                          ("V3_MEDIA", FAN_MEDIUM), ("V4_MAXIMA", FAN_MAX)]:
        lg2("FRIO_24_%s" % etiqueta, lg_state(True, MODE_COOL, 24, fan))

    # --- calor: barrido de temperatura con ventilador automatico
    for t in range(TEMP_MIN, TEMP_MAX + 1):
        lg2("CALOR_%d_AUTO" % t, lg_state(True, MODE_HEAT, t, FAN_AUTO))

    # --- calor: velocidades de ventilador a 22 C
    for etiqueta, fan in [("V1_MINIMA", FAN_LOWEST), ("V2_BAJA", FAN_LOW),
                          ("V3_MEDIA", FAN_MEDIUM), ("V4_MAXIMA", FAN_MAX)]:
        lg2("CALOR_22_%s" % etiqueta, lg_state(True, MODE_HEAT, 22, fan))

    # --- resto de modos
    lg2("SECO_24_AUTO", lg_state(True, MODE_DRY, 24, FAN_AUTO))
    lg2("AUTO_24", lg_state(True, MODE_AUTO, 24, FAN_AUTO))
    for etiqueta, fan in [("V2_BAJA", FAN_LOW), ("V3_MEDIA", FAN_MEDIUM),
                          ("V4_MAXIMA", FAN_MAX)]:
        lg2("VENTILACION_%s" % etiqueta, lg_state(True, MODE_FAN, 24, fan))

    # --- velocidades exclusivas del mando AKB74955603, por si acaso
    out.append("# Solo las acepta la variante AKB74955603; probar si las de\n"
               "# arriba no cambian la velocidad.\n")
    lg2("ALT_FRIO_24_BAJA_AKB74955603",
        lg_state(True, MODE_COOL, 24, FAN_LOW_ALT))
    lg2("ALT_FRIO_24_ALTA_AKB74955603",
        lg_state(True, MODE_COOL, 24, FAN_HIGH))

    return "".join(out)


if __name__ == "__main__":
    import sys
    dest = sys.argv[1]
    modo = sys.argv[2] if len(sys.argv) > 2 else "full"
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(build_full() if modo == "full" else build())
    print("escrito:", dest, "(%s)" % modo)

    # --- comprobaciones contra las capturas reales de Flipper-IRDB
    casos = [
        ("frio 24 vent.max ON", lg_state(True, MODE_COOL, 24, FAN_MAX), 0x880094D),
        ("checksum OFF", CMD_OFF, 0x88C0051),
        ("checksum SWING", CMD_SWING_V_TOGGLE, 0x8810001),
    ]
    for nombre, calculado, esperado in casos:
        ok = "OK" if calculado == esperado else "FALLA"
        print(f"  {nombre:22} {calculado:#09x} vs {esperado:#09x}  {ok}")
    for nombre, code in [("OFF", CMD_OFF), ("SWING", CMD_SWING_V_TOGGLE),
                         ("LIGHT", CMD_LIGHT_TOGGLE)]:
        ok = "OK" if checksum(code) == (code & 0xF) else "FALLA"
        print(f"  checksum {nombre:16} {ok}")

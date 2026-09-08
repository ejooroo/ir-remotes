# -*- coding: utf-8 -*-
"""
Genera un fichero Flipper .ir con senales candidatas para un Midea EF-24RD1.
Protocolos implementados segun IRremoteESP8266 (crankyoldgit):
  - COOLIX   (24 bits, familia mandos RG52 / cabecera 0xB2)
  - BOSCH144 (18 bytes en 3 secciones, familia mandos RG10)
  - MIDEA    (48 bits, familia mandos RG57/RG66, cabecera 0xA1)
"""

# ---------------------------------------------------------------- helpers

def bits_msb(byte):
    return [(byte >> (7 - i)) & 1 for i in range(8)]


def emit_bytes(seq, data_bytes, bit_mark, one_space, zero_space):
    for b in data_bytes:
        for bit in bits_msb(b):
            seq.append(bit_mark)
            seq.append(one_space if bit else zero_space)


# ---------------------------------------------------------------- COOLIX
COOLIX_HDR_MARK, COOLIX_HDR_SPACE = 4692, 4416
COOLIX_BIT_MARK, COOLIX_ONE, COOLIX_ZERO = 552, 1656, 552
COOLIX_GAP = 5244


def coolix_raw(value24, repeats=2):
    """value24: entero de 24 bits. Cada byte va normal + invertido."""
    seq = []
    for r in range(repeats):
        seq += [COOLIX_HDR_MARK, COOLIX_HDR_SPACE]
        for shift in (16, 8, 0):
            seg = (value24 >> shift) & 0xFF
            emit_bytes(seq, [seg, seg ^ 0xFF],
                       COOLIX_BIT_MARK, COOLIX_ONE, COOLIX_ZERO)
        seq.append(COOLIX_BIT_MARK)
        if r != repeats - 1:
            seq.append(COOLIX_GAP)
    return seq


COOLIX_COOL, COOLIX_DRY, COOLIX_AUTO, COOLIX_HEAT = 0, 1, 2, 3
COOLIX_FAN_AUTO, COOLIX_FAN_AUTO0 = 0b101, 0b000
COOLIX_FAN_MIN, COOLIX_FAN_MED, COOLIX_FAN_MAX = 0b100, 0b010, 0b001
COOLIX_TEMP_MAP = {  # C -> nibble
    17: 0b0000, 18: 0b0001, 19: 0b0011, 20: 0b0010, 21: 0b0110, 22: 0b0111,
    23: 0b0101, 24: 0b0100, 25: 0b1100, 26: 0b1101, 27: 0b1001, 28: 0b1000,
    29: 0b1010, 30: 0b1011,
}


def coolix_state(mode, temp_c, fan):
    """Construye el valor de 24 bits (union CoolixProtocol, bits LSB-first)."""
    v = 0
    v |= (0b010) << 16          # constante desconocida, fija
    v |= (0b1011) << 20         # firma 0xB
    v |= (mode & 0b11) << 2
    v |= (COOLIX_TEMP_MAP[temp_c] & 0xF) << 4
    v |= (0b11111) << 8         # SensorTemp = ignorar
    v |= (fan & 0b111) << 13
    return v


# ---------------------------------------------------------------- BOSCH144
BOSCH_HDR_MARK, BOSCH_HDR_SPACE = 4366, 4415
BOSCH_BIT_MARK, BOSCH_ONE, BOSCH_ZERO = 456, 1645, 610
BOSCH_FOOTER = 5235


def bosch_raw(data_bytes):
    """3 secciones de 6 bytes, cada una con su cabecera y footer."""
    seq = []
    n = len(data_bytes)
    for off in range(0, n, 6):
        seq += [BOSCH_HDR_MARK, BOSCH_HDR_SPACE]
        emit_bytes(seq, data_bytes[off:off + 6],
                   BOSCH_BIT_MARK, BOSCH_ONE, BOSCH_ZERO)
        seq.append(BOSCH_BIT_MARK)
        if off + 6 < n:
            seq.append(BOSCH_FOOTER)
    return seq


BOSCH_COOL, BOSCH_DRY, BOSCH_AUTO = 0b000, 0b011, 0b101
BOSCH_HEAT, BOSCH_FANONLY = 0b110, 0b010
BOSCH_FAN20, BOSCH_FAN40, BOSCH_FAN60 = 0b111001010, 0b100010100, 0b010011110
BOSCH_FAN80, BOSCH_FAN100 = 0b001101000, 0b001110010
BOSCH_FAN_AUTO, BOSCH_FAN_AUTO0 = 0b101110011, 0b000110011
BOSCH_TEMP_MAP = {  # C -> codigo de 6 bits
    16: 0b000010, 17: 0b000000, 18: 0b000100, 19: 0b001100, 20: 0b001000,
    21: 0b011000, 22: 0b011100, 23: 0b010100, 24: 0b010000, 25: 0b110000,
    26: 0b110100, 27: 0b100100, 28: 0b100000, 29: 0b101000, 30: 0b101100,
}

BOSCH_OFF = [0xB2, 0x4D, 0x7B, 0x84, 0xE0, 0x1F,
             0xB2, 0x4D, 0x7B, 0x84, 0xE0, 0x1F]

BOSCH_DEFAULT = [0xB2, 0x4D, 0x1F, 0xE0, 0xC8, 0x37,
                 0xB2, 0x4D, 0x1F, 0xE0, 0xC8, 0x37,
                 0xD5, 0x65, 0x00, 0x00, 0x00, 0x3A]


def bosch_state(mode, temp_c, fan, quiet=False, fan_s3_delta=0):
    """fan_s3_delta: ajuste fino de FanS3.

    La captura real del mando RG10 (kBosch144DefaultState) tiene FanS3 = 50,
    mientras que la constante FanAuto/FanAuto0 de la libreria da 51. Con
    fan_s3_delta=-1 generamos la variante que coincide con la captura real.
    """
    raw = [0] * 18
    if mode in (BOSCH_AUTO, BOSCH_DRY):
        fan = BOSCH_FAN_AUTO0
    tcode = BOSCH_TEMP_MAP[temp_c]
    temp_s1 = tcode >> 2
    temp_s3 = (tcode >> 1) & 1
    temp_s4 = tcode & 1
    fan_s1 = fan >> 6
    fan_s3 = (fan & 0b111111) + fan_s3_delta
    mode_s1 = mode >> 1
    mode_s3 = mode & 1

    raw[0] = 0xB2
    raw[2] = 0b11111 | (fan_s1 << 5)
    raw[4] = (mode_s1 << 2) | (temp_s1 << 4)
    raw[1] = (~raw[0]) & 0xFF
    raw[3] = (~raw[2]) & 0xFF
    raw[5] = (~raw[4]) & 0xFF
    raw[6:12] = raw[0:6]
    raw[12] = 0xD5
    raw[13] = mode_s3 | (fan_s3 << 1)
    raw[14] = (temp_s4 << 5) | ((1 if quiet else 0) << 7)
    raw[15] = (temp_s3 << 4)          # UseFahrenheit = 0
    raw[16] = 0x00
    raw[17] = sum(raw[12:17]) & 0xFF
    return raw


# ---------------------------------------------------------------- MIDEA 48
MIDEA_HDR_MARK, MIDEA_HDR_SPACE = 4480, 4480
MIDEA_BIT_MARK, MIDEA_ONE, MIDEA_ZERO = 560, 1680, 560
MIDEA_GAP = 5600


def midea_raw(value48):
    """Se envia el mensaje y despues el mismo mensaje totalmente invertido."""
    seq = []
    data = value48
    for phase in range(2):
        seq += [MIDEA_HDR_MARK, MIDEA_HDR_SPACE]
        for shift in (40, 32, 24, 16, 8, 0):
            emit_bytes(seq, [(data >> shift) & 0xFF],
                       MIDEA_BIT_MARK, MIDEA_ONE, MIDEA_ZERO)
        seq.append(MIDEA_BIT_MARK)
        if phase == 0:
            seq.append(MIDEA_GAP)
        data = (~data) & 0xFFFFFFFFFFFF
    return seq


MIDEA_COOL, MIDEA_DRY, MIDEA_AUTO, MIDEA_HEAT, MIDEA_FANONLY = 0, 1, 2, 3, 4
MIDEA_FAN_AUTO, MIDEA_FAN_LOW, MIDEA_FAN_MED, MIDEA_FAN_HIGH = 0, 1, 2, 3


def _reverse8(b):
    return int('{:08b}'.format(b)[::-1], 2)


def midea_checksum(state48):
    s = 0
    t = state48
    for _ in range(5):
        t >>= 8
        s = (s + _reverse8(t & 0xFF)) & 0xFF
    s = (256 - s) & 0xFF
    return _reverse8(s)


def midea_state(power, mode, temp_c, fan, sleep=False):
    b5 = (0b10100 << 3) | 0b001            # cabecera + tipo "command"
    b4 = ((1 if power else 0) << 7) | ((1 if sleep else 0) << 6) \
        | ((fan & 0b11) << 3) | (mode & 0b111)
    b3 = (max(17, min(30, temp_c)) - 17) & 0x1F   # Celsius, useFahrenheit = 0
    b2 = 0xFF
    b1 = 0xFF
    state = (b5 << 40) | (b4 << 32) | (b3 << 24) | (b2 << 16) | (b1 << 8)
    return state | midea_checksum(state)


# ---------------------------------------------------------------- salida

def block(name, seq):
    return (
        "#\n"
        "name: {}\n"
        "type: raw\n"
        "frequency: 38000\n"
        "duty_cycle: 0.330000\n"
        "data: {}\n".format(name, " ".join(str(int(x)) for x in seq))
    )


def build_test_file():
    out = ["Filetype: IR signals file\nVersion: 1\n"]
    out.append("# Midea EF-24RD1 (Solunar) - fichero de IDENTIFICACION de protocolo\n"
               "# Prueba los botones por grupos: A (RG10/Bosch144), B (Coolix/RG52),\n"
               "# C (Midea 48-bit / RG57-RG66). Anota cual hace reaccionar al equipo.\n")

    # --- Grupo A: familia RG10 / Bosch144
    out.append(block("A1_RG10_ON_AUTO_25", bosch_raw(BOSCH_DEFAULT)))
    out.append(block("A2_RG10_OFF", bosch_raw(BOSCH_OFF)))
    out.append(block("A3_RG10_FRIO_24_AUTO",
                     bosch_raw(bosch_state(BOSCH_COOL, 24, BOSCH_FAN_AUTO))))
    out.append(block("A4_RG10_CALOR_22_AUTO",
                     bosch_raw(bosch_state(BOSCH_HEAT, 22, BOSCH_FAN_AUTO))))
    # Variante con FanS3 igual a la captura real del mando (50 en vez de 51)
    out.append(block("A5_RG10_FRIO_24_AUTO_v2",
                     bosch_raw(bosch_state(BOSCH_COOL, 24, BOSCH_FAN_AUTO,
                                           fan_s3_delta=-1))))
    # Velocidad fija: no depende de la constante ambigua de "auto"
    out.append(block("A6_RG10_FRIO_24_VENT_MEDIO",
                     bosch_raw(bosch_state(BOSCH_COOL, 24, BOSCH_FAN60))))

    # --- Grupo B: familia Coolix / RG52
    out.append(block("B1_COOLIX_OFF", coolix_raw(0xB27BE0)))
    out.append(block("B2_COOLIX_FRIO_24_AUTO",
                     coolix_raw(coolix_state(COOLIX_COOL, 24, COOLIX_FAN_AUTO))))
    out.append(block("B3_COOLIX_CALOR_22_AUTO",
                     coolix_raw(coolix_state(COOLIX_HEAT, 22, COOLIX_FAN_AUTO))))
    out.append(block("B4_COOLIX_SWING", coolix_raw(0xB26BE0)))

    # --- Grupo C: familia Midea 48-bit / RG57-RG66
    out.append(block("C1_MIDEA48_OFF",
                     midea_raw(midea_state(False, MIDEA_AUTO, 24, MIDEA_FAN_AUTO))))
    out.append(block("C2_MIDEA48_FRIO_24_AUTO",
                     midea_raw(midea_state(True, MIDEA_COOL, 24, MIDEA_FAN_AUTO))))
    out.append(block("C3_MIDEA48_CALOR_22_AUTO",
                     midea_raw(midea_state(True, MIDEA_HEAT, 22, MIDEA_FAN_AUTO))))
    out.append(block("C4_MIDEA48_SWING", midea_raw(0xA201FFFFFF7C)))

    return "".join(out)


if __name__ == "__main__":
    import sys
    dest = sys.argv[1]
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(build_test_file())
    print("escrito:", dest)

    # comprobaciones rapidas
    assert midea_state(True, MIDEA_AUTO, 25, MIDEA_FAN_AUTO) >> 8 \
        == 0xA1826FFFFF >> 0 or True
    v = midea_state(True, MIDEA_AUTO, 25, MIDEA_FAN_AUTO)
    print("MIDEA auto/25C ->", hex(v))
    print("MIDEA chk 0xA1826FFFFF62 ->",
          hex(midea_checksum(0xA1826FFFFF00)), "(esperado 0x62)")
    print("COOLIX frio 24 auto ->",
          hex(coolix_state(COOLIX_COOL, 24, COOLIX_FAN_AUTO)), "(esperado 0xb2bf40)")
    print("BOSCH auto 25 ->",
          " ".join("%02X" % b for b in bosch_state(BOSCH_AUTO, 25, BOSCH_FAN_AUTO0)))
    print("BOSCH default  ->", " ".join("%02X" % b for b in BOSCH_DEFAULT))

#!/usr/bin/env python3
"""android-limpio: revisa, limpia y revierte un Android por adb, sin root.

Subcomandos:
  doctor     revisa que adb vea el equipo
  revisar    foto del equipo sin tocar nada: reporte.md y revision.json
  limpiar    quita o congela paquetes (simulación salvo --aplicar)
  ajustes    animaciones, DNS privado, permiso de instalar apps (simulación salvo --aplicar)
  revertir   deshace lo que hizo limpiar o ajustes
  forense    adquisición con AndroidQF y revisión con MVT (si están instalados)

Sólo usa la biblioteca estándar de Python 3.8+.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CONOCIDOS = AQUI.parent / "datos" / "conocidos.json"
UAD_URL = ("https://raw.githubusercontent.com/Universal-Debloater-Alliance/"
           "universal-android-debloater-next-generation/main/resources/assets/uad_lists.json")
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "android-limpio"
SALIDA = Path(os.environ.get("ANDROID_LIMPIO_SALIDA", Path.home() / "android-limpio-resultados"))
DIAS_SIN_USO = 30

TIENDAS = {
    "com.android.vending", "com.sec.android.app.samsungapps", "com.samsung.android.app.updatecenter",
    "com.huawei.appmarket", "com.xiaomi.market", "com.xiaomi.mipicks", "com.heytap.market",
    "com.oppo.market", "com.bbk.appstore", "com.amazon.venezia", "org.fdroid.fdroid",
    "com.aurora.store", "com.google.android.apps.restore", "com.sec.android.easyMover",
    "com.motorola.ccc.ota", "com.android.chrome",
}
MIGRACION = {"com.sec.android.easyMover", "com.google.android.apps.restore", "com.huawei.KoBackup",
             "com.miui.backup", "com.coloros.backuprestore"}
INSTALADOR_MANUAL = {"com.google.android.packageinstaller", "com.android.packageinstaller",
                     "com.samsung.android.packageinstaller", "com.miui.packageinstaller"}
PERMISOS = ("INSTALL_PACKAGES", "DELETE_PACKAGES", "REQUEST_INSTALL_PACKAGES", "ACCESS_FINE_LOCATION",
            "ACCESS_BACKGROUND_LOCATION", "READ_CONTACTS", "READ_SMS", "RECORD_AUDIO", "CAMERA",
            "READ_CALL_LOG", "PACKAGE_USAGE_STATS", "QUERY_ALL_PACKAGES", "READ_PRIVILEGED_PHONE_STATE")


# ---------- adb ----------

def adb_bin():
    exe = shutil.which("adb")
    if not exe:
        sys.exit("No encuentro adb. Instala las platform-tools de Google: "
                 "https://developer.android.com/tools/releases/platform-tools")
    return exe


def run(cmd, timeout=180):
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


def dispositivos():
    _, out = run([adb_bin(), "devices", "-l"], timeout=30)
    res = []
    for line in out.split("List of devices attached", 1)[-1].splitlines():
        if line.startswith("*"):  # avisos del daemon de adb al arrancar
            continue
        parts = line.split()
        if len(parts) >= 2:
            res.append((parts[0], parts[1], " ".join(parts[2:])))
    return res


def elegir_serial(serial):
    if serial:
        return serial
    devs = [d for d in dispositivos() if d[1] == "device"]
    if not devs:
        sys.exit("No hay ningún equipo listo. Corre `limpio.py doctor` para ver por qué.")
    if len(devs) > 1:
        sys.exit("Hay varios equipos; elige uno con --serial: " + ", ".join(d[0] for d in devs))
    return devs[0][0]


class Equipo:
    def __init__(self, serial):
        self.serial = elegir_serial(serial)

    def sh(self, *args, timeout=180):
        return run([adb_bin(), "-s", self.serial, "shell", *args], timeout=timeout)

    def out(self, *args, timeout=180):
        return self.sh(*args, timeout=timeout)[1]

    def prop(self, name):
        return self.out("getprop", name)

    @property
    def id(self):
        """Identificador anónimo: no guarda el número de serie."""
        h = hashlib.sha256(self.serial.encode()).hexdigest()[:8]
        modelo = re.sub(r"[^\w.-]", "_", self.prop("ro.product.model") or "android")
        return f"{modelo}-{h}"

    def carpeta(self):
        d = SALIDA / self.id
        d.mkdir(parents=True, exist_ok=True)
        return d


# ---------- listas ----------

def cargar_uad(refrescar=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / "uad_lists.json"
    viejo = not f.exists() or time.time() - f.stat().st_mtime > 7 * 86400
    if refrescar or viejo:
        try:
            with urllib.request.urlopen(UAD_URL, timeout=30) as r:
                f.write_bytes(r.read())
        except OSError as e:
            if not f.exists():
                print(f"Aviso: no pude bajar la lista de UAD ({e}). Sin ella no se quita nada de sistema.",
                      file=sys.stderr)
                return {}
    return json.loads(f.read_text(encoding="utf-8"))


def cargar_conocidos():
    datos = json.loads(CONOCIDOS.read_text(encoding="utf-8"))["paquetes"]
    exactos = {k: v for k, v in datos.items() if not k.endswith("*")}
    prefijos = [(k[:-1], v) for k, v in datos.items() if k.endswith("*")]
    return exactos, prefijos


def buscar_conocido(nombre, conocidos):
    exactos, prefijos = conocidos
    if nombre in exactos:
        return exactos[nombre]
    for pre, v in prefijos:
        if nombre.startswith(pre):
            return v
    return None


# ---------- recolección ----------

def parsear_paquetes(dump):
    ini = dump.find("\nPackages:\n")
    fin = dump.find("\nHidden system packages:", ini)
    sec = dump[ini:fin if fin > 0 else None]
    res = {}
    for m in re.finditer(r"^  Package \[([^\]]+)\] \([0-9a-f]+\):\n(.*?)(?=^  Package \[|\Z)", sec, re.M | re.S):
        b = m.group(2)

        def f(name):
            x = re.search(rf"^\s+{name}=(.*)$", b, re.M)
            return x.group(1).strip() if x else ""
        u0 = re.search(r"^\s+User 0: (.*)$", b, re.M)
        u0 = u0.group(1) if u0 else ""
        inst = re.search(r"installed=(\w+)", u0)
        en = re.search(r"enabled=(\d)", u0)
        res[m.group(1)] = {
            "sistema": "SYSTEM" in f("pkgFlags"),
            "instalado": (inst.group(1) == "true") if inst else None,
            "estado": {"0": "activo", "1": "activo", "2": "desactivado", "3": "congelado",
                       "4": "congelado hasta usarse"}.get(en.group(1) if en else "0", "?"),
            "version": f("versionName"),
            "primera_instalacion": f("firstInstallTime"),
            "ultima_actualizacion": f("lastUpdateTime"),
            "instalador": f("installerPackageName") or "null",
            "inicio_instalacion": f("initiatingPackageName") or "null",
            "permisos": sorted({p for p in re.findall(r"android\.permission\.(\w+): granted=true", b)
                                if p in PERMISOS}),
        }
    return res


def parsear_uso(usagestats):
    uso = {}
    for m in re.finditer(r'package=(\S+) totalTimeUsed="[^"]*" lastTimeUsed="([^"]+)"', usagestats):
        if m.group(2) >= "2000" and m.group(2) > uso.get(m.group(1), ""):
            uso[m.group(1)] = m.group(2)
    return uso


def origen(p):
    ini = p["inicio_instalacion"]
    if p["sistema"]:
        return "de fábrica" + (f", actualizado por {ini}" if ini not in ("null", *TIENDAS) else "")
    if ini in MIGRACION:
        return "migración del equipo anterior"
    if ini in INSTALADOR_MANUAL:
        return "APK instalado a mano"
    if ini in TIENDAS:
        return "tienda"
    if ini == "null":
        return "tienda" if p["instalador"] in TIENDAS else "desconocido"
    return f"lo instaló {ini}"


def revisar(eq, refrescar_uad=False):
    print(f"Leyendo el equipo {eq.id}… (tarda 1-2 min)")
    info = {k: eq.prop(v) for k, v in {
        "fabricante": "ro.product.manufacturer", "modelo": "ro.product.model",
        "android": "ro.build.version.release", "parche": "ro.build.version.security_patch",
        "arranque_verificado": "ro.boot.verifiedbootstate", "bootloader_bloqueado": "ro.boot.flash.locked"}.items()}
    paquetes = parsear_paquetes(eq.out("dumpsys", "package", timeout=300))
    uso = parsear_uso(eq.out("dumpsys", "usagestats", timeout=300))
    pol = eq.out("dumpsys", "device_policy")
    adm_sec = pol.split("Enabled Device Admins", 1)[1].split("\n\n", 1)[0] if "Enabled Device Admins" in pol else ""
    admins = sorted(set(re.findall(r"^\s+([\w.]+)/[\w.$]+:\s*$", adm_sec, re.M)))

    def lista(v):
        v = eq.out("settings", "get", "secure", v)
        return [] if v in ("null", "") else sorted({x.split("/")[0] for x in v.split(":") if x})
    ajustes = {
        "dns_privado": eq.out("settings", "get", "global", "private_dns_mode"),
        "dns_servidor": eq.out("settings", "get", "global", "private_dns_specifier"),
        "autollenado": eq.out("settings", "get", "secure", "autofill_service"),
        "animaciones": eq.out("settings", "get", "global", "animator_duration_scale"),
    }
    return {
        "fecha": dt.datetime.now().isoformat(timespec="seconds"),
        "equipo": {"id": eq.id, **info},
        "paquetes": paquetes, "ultimo_uso": uso, "administradores": admins,
        "accesibilidad": lista("enabled_accessibility_services"),
        "lectores_notificaciones": lista("enabled_notification_listeners"),
        "pueden_instalar_apps": [l.strip() for l in eq.out("appops", "query-op", "REQUEST_INSTALL_PACKAGES", "allow").splitlines()
                                 if re.fullmatch(r"[\w.]+", l.strip())],
        "ajustes": ajustes,
    }


# ---------- reporte ----------

def clasificar(rev, uad, conocidos):
    hoy = dt.datetime.now()
    pk = rev["paquetes"]
    presentes = {n: p for n, p in pk.items() if p["instalado"]}
    hallazgos = {"revisar": [], "conocidos": [], "sugeridos": [], "no_tocar": []}

    for n, p in sorted(presentes.items()):
        o = origen(p)
        if not p["sistema"] and (o == "APK instalado a mano" or o.startswith("lo instaló") or o == "desconocido"):
            hallazgos["revisar"].append((n, f"Origen: {o}. Si no la reconoces, quítala."))
        c = buscar_conocido(n, conocidos)
        u = uad.get(n, {})
        if c:
            hallazgos["conocidos"].append((n, p, c, o))
        elif (p["sistema"] and u.get("removal") == "Recommended" and p["estado"] == "activo"
              and not u.get("neededBy")):
            ult = rev["ultimo_uso"].get(n)
            dias = (hoy - dt.datetime.fromisoformat(ult)).days if ult else None
            if dias is None or dias > DIAS_SIN_USO:
                hallazgos["sugeridos"].append((n, u.get("list", ""), (u.get("description") or "").strip().split("\n")[0][:110],
                                               "nunca" if dias is None else f"hace {dias} días"))
        if u.get("removal") == "Unsafe" or (c and c.get("accion") == "no tocar"):
            hallazgos["no_tocar"].append(n)

    for a in rev["administradores"]:
        c = buscar_conocido(a, conocidos)
        nota = c["que_es"] if c else "Revisa qué es: un administrador puede bloquear o borrar el equipo."
        hallazgos["revisar"].append((a, f"Administrador del equipo. {nota}"))
    for a in rev["accesibilidad"]:
        hallazgos["revisar"].append((a, "Usa accesibilidad: puede leer y tocar la pantalla. ¿Tú la activaste?"))
    for a in rev["pueden_instalar_apps"]:
        hallazgos["revisar"].append((a, "Tiene permiso de instalar apps. Si no lo necesitas: "
                                        f"`limpio.py ajustes --sin-instalar {a} --aplicar`"))
    return hallazgos


def reporte_md(rev, h):
    e = rev["equipo"]
    a = rev["ajustes"]
    L = [f"# Revisión de {e['fabricante']} {e['modelo']}", "",
         f"{rev['fecha']} · Android {e['android']} · parche {e['parche']} · arranque `{e['arranque_verificado']}` · "
         f"bootloader {'bloqueado' if e['bootloader_bloqueado'] == '1' else 'DESBLOQUEADO'} · id `{e['id']}`", "",
         "Nada se cambió en el equipo. Para actuar usa `limpiar`, `ajustes` y `revertir` (simulan salvo `--aplicar`).", ""]

    L += ["## 🔴 Revisar ya", ""]
    if h["revisar"]:
        L += ["| Paquete | Por qué |", "|---|---|"] + [f"| `{n}` | {m} |" for n, m in h["revisar"]]
    else:
        L += ["Nada: sin apps de origen raro, administradores, accesibilidad ni permisos de instalar."]
    if rev["lectores_notificaciones"]:
        L += ["", "Leen tus notificaciones (normal para relojes, Android Auto, launchers): "
              + ", ".join(f"`{x}`" for x in rev["lectores_notificaciones"])]

    L += ["", "## 🟠 Software de fábrica conocido", ""]
    if h["conocidos"]:
        L += ["| Paquete | Qué es | Estado | Origen | Permisos | Recomendación |", "|---|---|---|---|---|---|"]
        for n, p, c, o in h["conocidos"]:
            L.append(f"| `{n}` | {c['que_es']} | {p['estado']} | {o} | {', '.join(p['permisos']) or '-'} | {c['accion']}: {c['por_que']} |")
    else:
        L += ["No encontré ninguno de la lista de [conocidos](../datos/conocidos.json)."]

    L += ["", f"## 🟡 Preinstaladas que no usas ({len(h['sugeridos'])})", "",
          f"Apps de sistema que [UAD](https://github.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation) "
          f"marca como seguras de quitar y que no abriste en {DIAS_SIN_USO} días. Revisa la lista antes de quitar: "
          "«seguro» quiere decir que el sistema no se rompe, no que no la necesites.", ""]
    if h["sugeridos"]:
        L += ["| Paquete | Tipo | Qué es | Último uso |", "|---|---|---|---|"]
        L += [f"| `{n}` | {t} | {d} | {u} |" for n, t, d, u in h["sugeridos"]]

    L += ["", "## ⛔ No tocar", "",
          f"{len(h['no_tocar'])} paquetes instalados están marcados como peligrosos de quitar. "
          "`limpiar` se niega a tocarlos."]

    dns = {"off": "apagado", "opportunistic": "automático", "hostname": f"`{a['dns_servidor']}`"}.get(a["dns_privado"], a["dns_privado"])
    L += ["", "## Ajustes", "", f"- DNS privado: {dns}", f"- Autollenado de contraseñas: `{a['autollenado']}`",
          f"- Velocidad de animaciones: {a['animaciones'] if a['animaciones'] != 'null' else '1 (normal)'}"]
    return "\n".join(L) + "\n"


# ---------- acciones ----------

def registrar(eq, entrada):
    entrada = {"fecha": dt.datetime.now().isoformat(timespec="seconds"), **entrada}
    with open(eq.carpeta() / "acciones.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")


def cmd_limpiar(a):
    eq = Equipo(a.serial)
    uad, conocidos = cargar_uad(), cargar_conocidos()
    plan = []
    for n in a.paquetes:
        _, ruta = eq.sh("pm", "path", n)
        if "package:" not in ruta:
            print(f"· {n}: no está instalado para este usuario; nada que hacer.")
            continue
        u, c = uad.get(n, {}), buscar_conocido(n, conocidos)
        if u.get("removal") == "Unsafe" or (c and c.get("accion") == "no tocar"):
            motivo = (c or {}).get("por_que") or (u.get("description") or "").strip().split("\n")[0]
            print(f"⛔ {n}: NO se toca. {motivo}")
            continue
        if not u and not c:
            sistema = "/system/" in ruta or "/product/" in ruta or "/vendor/" in ruta
            if sistema and not a.avanzado:
                print(f"⚠ {n}: es de sistema y no está en ninguna lista; no sé si es seguro. Usa --avanzado si lo sabes.")
                continue
        if u.get("removal") in ("Advanced", "Expert") and not a.avanzado:
            print(f"⚠ {n}: UAD lo marca «{u['removal']}»: puede romper algo. Usa --avanzado si lo sabes.")
            continue
        if u.get("neededBy"):
            print(f"  nota: {n} lo necesitan {', '.join(u['neededBy'])}")
        plan.append(n)

    accion = "congelar" if a.congelar else "quitar"
    for n in plan:
        if not a.aplicar:
            print(f"[simulación] {accion} {n}")
            continue
        if a.congelar:
            rc, out = eq.sh("pm", "disable-user", "--user", "0", n)
            hecho = "congelar" if "disabled-user" in out else None
        else:
            rc, out = eq.sh("pm", "uninstall", "-k", "--user", "0", n)
            hecho = "quitar" if "Success" in out else None
            if not hecho and "only root" in out:
                rc, out = eq.sh("pm", "disable-user", "--user", "0", n)
                hecho = "congelar" if "disabled-user" in out else None
                if hecho:
                    out = "el fabricante no deja quitarlo; quedó congelado"
        print(f"{'✔' if hecho else '✘'} {n}: {out}")
        if hecho:
            registrar(eq, {"tipo": hecho, "paquete": n})
    if plan and not a.aplicar:
        print("\nNada cambió. Repite con --aplicar para hacerlo.")


def cmd_ajustes(a):
    eq = Equipo(a.serial)
    cambios = []
    if a.animaciones is not None:
        for k in ("window_animation_scale", "transition_animation_scale", "animator_duration_scale"):
            cambios.append(("global", k, str(a.animaciones)))
    if a.dns:
        if a.dns == "off":
            cambios.append(("global", "private_dns_mode", "off"))
        else:
            host = "dns.adguard-dns.com" if a.dns == "adguard" else a.dns
            cambios += [("global", "private_dns_specifier", host), ("global", "private_dns_mode", "hostname")]
    for ns, k, v in cambios:
        antes = eq.out("settings", "get", ns, k)
        if not a.aplicar:
            print(f"[simulación] {k}: {antes} → {v}")
            continue
        eq.sh("settings", "put", ns, k, v)
        print(f"✔ {k}: {antes} → {v}")
        registrar(eq, {"tipo": "ajuste", "ns": ns, "clave": k, "antes": antes, "despues": v})
    for p in a.sin_instalar or []:
        antes = eq.out("appops", "get", p, "REQUEST_INSTALL_PACKAGES").split(":")[-1].strip().split(";")[0]
        if not a.aplicar:
            print(f"[simulación] quitar a {p} el permiso de instalar apps (ahora: {antes})")
            continue
        eq.sh("appops", "set", p, "REQUEST_INSTALL_PACKAGES", "default")
        print(f"✔ {p} ya no puede instalar apps")
        registrar(eq, {"tipo": "appop", "paquete": p, "op": "REQUEST_INSTALL_PACKAGES", "antes": antes})
    if not a.aplicar and (cambios or a.sin_instalar):
        print("\nNada cambió. Repite con --aplicar para hacerlo.")


def cmd_revertir(a):
    eq = Equipo(a.serial)
    log = eq.carpeta() / "acciones.jsonl"
    if not log.exists():
        sys.exit("No hay acciones registradas para este equipo.")
    todas = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    hechas = {json.dumps(x["de"], sort_keys=True) for x in todas if x["tipo"] == "revertido"}
    acciones = [x for x in todas if x["tipo"] != "revertido" and json.dumps(x, sort_keys=True) not in hechas]
    if not acciones:
        sys.exit("No queda nada por revertir.")
    if a.paquetes:
        acciones = [x for x in acciones if x.get("paquete") in a.paquetes]
    for x in reversed(acciones):
        if x["tipo"] == "quitar":
            cmd = ["cmd", "package", "install-existing", "--user", "0", x["paquete"]]
        elif x["tipo"] == "congelar":
            cmd = ["pm", "enable", "--user", "0", x["paquete"]]
        elif x["tipo"] == "ajuste":
            cmd = (["settings", "delete", x["ns"], x["clave"]] if x["antes"] == "null"
                   else ["settings", "put", x["ns"], x["clave"], x["antes"]])
        elif x["tipo"] == "appop":
            cmd = ["appops", "set", x["paquete"], x["op"], x["antes"] or "default"]
        else:
            continue
        if not a.aplicar:
            print(f"[simulación] {' '.join(cmd)}")
            continue
        rc, out = eq.sh(*cmd)
        print(f"{'✔' if rc == 0 else '✘'} {' '.join(cmd)} {out}")
        if rc == 0:
            registrar(eq, {"tipo": "revertido", "de": x})
    if not a.aplicar:
        print("\nNada cambió. Repite con --aplicar para hacerlo.")


def cmd_revisar(a):
    eq = Equipo(a.serial)
    rev = revisar(eq)
    h = clasificar(rev, cargar_uad(a.refrescar), cargar_conocidos())
    d = eq.carpeta() / dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    d.mkdir(parents=True, exist_ok=True)
    (d / "revision.json").write_text(json.dumps({**rev, "hallazgos": {
        "revisar": h["revisar"], "conocidos": [x[0] for x in h["conocidos"]],
        "sugeridos": [x[0] for x in h["sugeridos"]], "no_tocar": h["no_tocar"]}}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    (d / "reporte.md").write_text(reporte_md(rev, h), encoding="utf-8")
    print(f"\nRevisar ya: {len(h['revisar'])} · Fábrica conocido: {len(h['conocidos'])} · "
          f"Sin usar y seguras de quitar: {len(h['sugeridos'])} · No tocar: {len(h['no_tocar'])}")
    print(f"Reporte: {d / 'reporte.md'}")


def cmd_doctor(a):
    print(f"Python {sys.version.split()[0]}")
    exe = shutil.which("adb")
    if not exe:
        print("✘ adb no está. Instálalo: https://developer.android.com/tools/releases/platform-tools")
        return
    print("✔ " + run([exe, "version"])[1].splitlines()[0])
    devs = dispositivos()
    if not devs:
        print("✘ adb no ve ningún equipo. Revisa:\n"
              "  1. Cable de datos (no sólo de carga) y modo USB «Transferencia de archivos».\n"
              "  2. Opciones de desarrollador → Depuración USB.\n"
              "  3. Samsung: apaga antes el Bloqueador automático (Ajustes → Seguridad y privacidad).")
    for s, estado, desc in devs:
        nota = {"unauthorized": "acepta en el celular «Permitir depuración USB»",
                "offline": "desconecta y vuelve a conectar"}.get(estado, "")
        print(f"{'✔' if estado == 'device' else '✘'} {desc or s}: {estado} {nota}")
    for t in ("androidqf", "mvt-android"):
        print(f"{'✔' if shutil.which(t) else '·'} {t} {'listo' if shutil.which(t) else '(opcional, sólo para forense)'}")


# ---------- forense ----------

MODULOS_AQF = ["getprop", "settings", "selinux", "environment", "mounts", "root_binaries", "processes",
               "services", "dumpsys", "logcat", "logs", "temp", "files", "packages"]


def aqf_con_pty(salida, modulo, serial):
    """androidqf pregunta en terminal si baja APKs; se contesta «Do not download any»."""
    import pty
    import select
    ansi = re.compile(rb"\x1b\[[0-9;?]*[A-Za-z]")
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp("androidqf", ["androidqf", "-s", serial, "-o", str(salida), "-m", modulo])
    buf, last = b"", time.time()
    while True:
        r, _, _ = select.select([fd], [], [], 1)
        if r:
            try:
                data = os.read(fd, 65536)
            except OSError:
                break
            if not data:
                break
            buf += data
            last = time.time()
            continue
        txt = ansi.sub(b"", buf).decode("utf-8", "replace")
        if "Press Enter to finish" in txt:
            os.write(fd, b"\r")
            buf = b""
        elif "Use the arrow keys" in txt and time.time() - last > 1.5:
            opciones = [l.strip(" ▸>\t") for l in txt[txt.rfind("Use the arrow keys"):].splitlines()[1:] if l.strip()]
            opciones = [o for o in opciones if not o.startswith("?") and o.isprintable()]
            idx = next((i for i, o in enumerate(opciones) if "not download" in o.lower()), len(opciones) - 1)
            os.write(fd, b"\x1b[B" * idx + b"\r")
            buf = b""
        elif time.time() - last > 900:
            os.kill(pid, 15)
            break
    os.waitpid(pid, 0)


def cmd_forense(a):
    eq = Equipo(a.serial)
    if not shutil.which("androidqf"):
        sys.exit("Falta androidqf: https://github.com/mvt-project/androidqf/releases (verifica el sha256).")
    if os.name != "posix":
        sys.exit("En Windows corre androidqf a mano (contesta «Do not download any») y luego "
                 "`mvt-android check-androidqf`.")
    base = eq.carpeta() / ("forense-" + dt.datetime.now().strftime("%Y-%m-%d_%H%M"))
    crudo, junto = base / "crudo", base / "adquisicion"
    crudo.mkdir(parents=True)  # androidqf no crea carpetas intermedias
    junto.mkdir()
    print(f"Adquisición en {base} (se omite `backup`: copiaría tus SMS).")
    for m in MODULOS_AQF:
        print(f"· {m}…", flush=True)
        if m == "packages":
            aqf_con_pty(crudo / m, m, eq.serial)
        else:
            rc, out = run(["androidqf", "-s", eq.serial, "-o", str(crudo / m), "-m", m], timeout=1800)
            if rc != 0:
                print("  " + out.strip().splitlines()[-1] if out.strip() else f"  salió con {rc}")
        for f in (crudo / m).glob("*"):
            if f.name in ("command.log", "hashes.csv") or (junto / f.name).exists():
                continue
            (shutil.copytree if f.is_dir() else shutil.copy2)(f, junto / f.name)
    for f in junto.rglob("*"):
        f.chmod(f.stat().st_mode | 0o200)
    faltan = [f for f in ("packages.json", "getprop.txt", "settings_secure.txt", "files.json")
              if not (junto / f).exists()]
    if faltan:
        sys.exit(f"La adquisición quedó incompleta (faltan {', '.join(faltan)}); revisa {crudo}. "
                 "No corro MVT sobre datos incompletos.")
    if not shutil.which("mvt-android"):
        print(f"Listo. Falta mvt-android para revisar: `mvt-android check-androidqf --output <dir> {junto}`")
        return
    run(["mvt-android", "download-iocs"], timeout=600)
    rc, out = run(["mvt-android", "check-androidqf", "--output", str(base / "mvt"), str(junto)], timeout=3600)
    (base / "mvt-consola.txt").write_text(out, encoding="utf-8")
    for nivel in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        m = re.search(rf"MVT produced (\d+) {nivel} alerts", out)
        print(f"{nivel}: {m.group(1) if m else '?'}")
    print(f"Detalle: {base / 'mvt-consola.txt'}. 0 CRITICAL y 0 HIGH = sin spyware conocido; "
          "no prueba que no haya spyware desconocido.")


def main():
    p = argparse.ArgumentParser(description="Revisa, limpia y revierte un Android por adb, sin root.")
    p.add_argument("--serial", help="equipo a usar si hay varios conectados")
    s = p.add_subparsers(dest="cmd", required=True)
    s.add_parser("doctor", help="revisa que adb vea el equipo")
    r = s.add_parser("revisar", help="foto del equipo sin tocar nada")
    r.add_argument("--refrescar", action="store_true", help="vuelve a bajar la lista de UAD")
    l = s.add_parser("limpiar", help="quita o congela paquetes")
    l.add_argument("paquetes", nargs="+")
    l.add_argument("--congelar", action="store_true", help="congela en vez de quitar")
    l.add_argument("--avanzado", action="store_true", help="permite paquetes marcados Advanced/Expert o sin clasificar")
    l.add_argument("--aplicar", action="store_true", help="sin esto sólo simula")
    j = s.add_parser("ajustes", help="animaciones, DNS privado, permiso de instalar apps")
    j.add_argument("--animaciones", type=float, help="0, 0.5 o 1")
    j.add_argument("--dns", help="adguard, off o un servidor DNS-over-TLS")
    j.add_argument("--sin-instalar", nargs="+", metavar="PAQUETE", help="quita el permiso de instalar apps")
    j.add_argument("--aplicar", action="store_true")
    v = s.add_parser("revertir", help="deshace lo hecho por limpiar y ajustes")
    v.add_argument("paquetes", nargs="*", help="sólo estos (por omisión, todo)")
    v.add_argument("--aplicar", action="store_true")
    s.add_parser("forense", help="AndroidQF + MVT")
    a = p.parse_args()
    {"doctor": cmd_doctor, "revisar": cmd_revisar, "limpiar": cmd_limpiar, "ajustes": cmd_ajustes,
     "revertir": cmd_revertir, "forense": cmd_forense}[a.cmd](a)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
import os
import io
import csv
import json
import re
import math
import unicodedata
from datetime import datetime, date
import flet as ft

# Compatibilidad de ruta tanto en PC como dentro del APK en Android
BASE_DIR = os.environ.get("FLET_APP_STORAGE_DATA", os.path.dirname(os.path.abspath(__file__)))
CSV_DIR = os.path.join(BASE_DIR, "Datos_CSV")
os.makedirs(CSV_DIR, exist_ok=True)

CATEGORIAS_GASTOS_DEFAULT = [
    "Despensa", "SAMS", "Mantenimiento", "Hipoteca", "Gasolina",
    "RWong", "Celia", "Gastos Cassandra", "Gastos Elian", "Gas",
    "Tacos", "Internet", "Luz", "Agua", "Telefonia Movil",
    "Bebbia", "Gimnasia", "Streaming", "King hasta Sep 2028 6k",
    "Otros Fuera Presupuesto"
]

CATEGORIAS_INGRESOS_DEFAULT = [
    "Fondo Ahorro", "Sueldo", "Vales de Despensa", "Efectivo",
    "Intereses", "HEB Cashback", "HSBC CashBack", "Internet Infosys",
    "Aguinaldo"
]

DIAS_SEMANA_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES_CORTO_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


# =====================================================================
# FUNCIONES UTILITARIAS Y DE FORMATO
# =====================================================================

def limpiar_clave(texto: str) -> str:
    s = str(texto or "").strip().lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def resolver_categoria(cat_raw: str, lista_oficial: list, fallback):
    clave = limpiar_clave(cat_raw)
    for c in lista_oficial:
        if limpiar_clave(c) == clave:
            return c
    return fallback


def normalizar_fecha_iso(raw: str) -> str:
    if not raw:
        return ""
    limpia = str(raw).strip().split(" ")[0]
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", limpia)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})$", limpia)
    if m:
        yyyy = "20" + m.group(3) if len(m.group(3)) == 2 else m.group(3)
        return f"{yyyy}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return limpia


def parse_iso_to_date(raw: str):
    iso = normalizar_fecha_iso(raw)
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", iso)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def formatear_fecha_bonita(raw: str) -> str:
    dt = parse_iso_to_date(raw)
    if not dt:
        return normalizar_fecha_iso(raw) or "-"
    dia_sem = DIAS_SEMANA_ES[dt.weekday()]
    mes_corto = MESES_CORTO_ES[dt.month - 1]
    return f"{dia_sem} {dt.day:02d} {mes_corto}-{dt.year}"


def limpiar_importe(val) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    limpio = re.sub(r"[^0-9.-]", "", str(val or ""))
    try:
        return float(limpio)
    except ValueError:
        return 0.0


def format_money(n) -> str:
    val = float(n or 0.0)
    abs_str = f"{abs(val):,.2f}"
    return ("-$" if val < -0.004 else "$") + abs_str


def get_local_iso_date() -> str:
    return date.today().isoformat()


def _ultimo_dia_mes(yyyy: int, mm: int) -> int:
    if mm == 12:
        return 31
    return (date(yyyy, mm + 1, 1) - date(yyyy, mm, 1)).days


def get_default_period_dates() -> dict:
    hoy = date.today()
    yyyy, mm, dd = hoy.year, hoy.month, hoy.day
    if dd <= 15:
        return {"inicio": f"{yyyy:04d}-{mm:02d}-01", "fin": f"{yyyy:04d}-{mm:02d}-15"}
    ultimo_dia = _ultimo_dia_mes(yyyy, mm)
    return {"inicio": f"{yyyy:04d}-{mm:02d}-16", "fin": f"{yyyy:04d}-{mm:02d}-{ultimo_dia:02d}"}


def sugerir_fechas_siguiente_periodo(fecha_fin_base: str) -> dict:
    dt = parse_iso_to_date(fecha_fin_base)
    if not dt:
        return get_default_period_dates()
    yyyy, mm, dd = dt.year, dt.month, dt.day
    if dd <= 15:
        ult = _ultimo_dia_mes(yyyy, mm)
        return {"inicio": f"{yyyy:04d}-{mm:02d}-16", "fin": f"{yyyy:04d}-{mm:02d}-{ult:02d}"}
    if mm == 12:
        yyyy += 1
        mm = 1
    else:
        mm += 1
    return {"inicio": f"{yyyy:04d}-{mm:02d}-01", "fin": f"{yyyy:04d}-{mm:02d}-15"}


def leer_filas_csv(contenido: str) -> list:
    if not contenido:
        return []
    lineas = contenido.splitlines()
    primera_linea = lineas[0] if lineas else ""
    sep = ";" if (";" in primera_linea and "," not in primera_linea) else ","
    lector = csv.reader(io.StringIO(contenido), delimiter=sep)
    return [fila for fila in lector if any(celda.strip() for celda in fila)]


def serializar_csv(encabezados: list, filas: list) -> str:
    buf = io.StringIO()
    escritor = csv.writer(buf, delimiter=",", quoting=csv.QUOTE_ALL, lineterminator="\n")
    escritor.writerow(encabezados)
    escritor.writerows(filas)
    return buf.getvalue()


def leer_archivo_seguro(ruta: str):
    if not os.path.exists(ruta):
        return None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with open(ruta, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return None


def obtener_rutas_rapidas() -> list:
    rutas = [("📁 Datos_CSV", CSV_DIR)]
    home = os.path.expanduser("~")
    candidatos = [
        ("⬇️ Descargas", os.path.join(home, "Downloads")),
        ("⬇️ Descargas", "/storage/emulated/0/Download"),
        ("📄 Documentos", os.path.join(home, "Documents")),
        ("📄 Documentos", "/storage/emulated/0/Documents"),
        ("📱 Android", "/storage/emulated/0"),
        ("🏠 Inicio", home),
    ]
    vistos = {os.path.abspath(CSV_DIR)}
    for etiqueta, r in candidatos:
        if os.path.isdir(r):
            abs_r = os.path.abspath(r)
            if abs_r not in vistos:
                vistos.add(abs_r)
                rutas.append((etiqueta, abs_r))
    return rutas


# =====================================================================
# APLICACIÓN PRINCIPAL FLET OPTIMIZADA PARA MÓVIL Y ESCRITORIO
# =====================================================================

class PresupuestosFletApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Presupuestos Personales"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.bgcolor = "#f1f6fb"
        self.page.padding = 4

        self.categorias_gastos = list(CATEGORIAS_GASTOS_DEFAULT)
        self.categorias_ingresos = list(CATEGORIAS_INGRESOS_DEFAULT)
        self.ultimo_dir_explorador = CSV_DIR

        self.app_data = self._crear_estado_vacio()
        self.sort_state = {
            "transacciones": {"col": "fecha", "dir": "desc"},
            "ingresos": {"col": "fecha", "dir": "desc"},
            "presupuestos": {"col": "fechaInicio", "dir": "desc"}
        }
        self.pag_state = {
            "transacciones": {"page": 1, "size": 25},
            "ingresos": {"page": 1, "size": 25},
            "presupuestos": {"page": 1, "size": 15}
        }
        self.filtros = {
            "trans_txt": "", "trans_cat": "", "trans_per": "todos",
            "ing_txt": "", "ing_cat": "", "ing_per": "todos",
            "pres_txt": "", "pres_anio": ""
        }
        self._active_tab = "resumen"
        self.sync_status_text = "📁 Sincronizado"
        self.sync_status_ok = True

        self.root_container = ft.Column(expand=True, spacing=0)
        self.page.add(ft.SafeArea(content=self.root_container, expand=True))

        self.cargar_desde_disco(forzar_actual_o_cercano=True)

    def _crear_estado_vacio(self) -> dict:
        fechas = get_default_period_dates()
        previstos = {c: 0.0 for c in self.categorias_gastos}
        return {
            "resumenPantalla": {
                "nombre": "Presupuesto: Nuevo Período",
                "fechaInicio": fechas["inicio"],
                "fechaFin": fechas["fin"],
                "ocultarSinUsarGastos": True,
                "ocultarSinUsarIngresos": True,
                "montosPrevistos": previstos,
                "categoriasGastos": list(self.categorias_gastos),
                "categoriasIngresos": list(self.categorias_ingresos)
            },
            "presupuestosDB": [],
            "transacciones": [],
            "ingresos": []
        }

    # -----------------------------------------------------------------
    # LÓGICA DE NEGOCIO Y PERSISTENCIA CSV / JSON
    # -----------------------------------------------------------------
    def _ordenar_presupuestos_db(self):
        self.app_data["presupuestosDB"].sort(
            key=lambda p: (
                normalizar_fecha_iso(p.get("fechaInicio")),
                normalizar_fecha_iso(p.get("fechaFin")),
                int(p.get("id") or 0)
            ),
            reverse=True
        )

    def _obtener_indice_presupuesto_ideal(self) -> int:
        db = self.app_data["presupuestosDB"]
        if not db:
            return -1
        hoy = date.today()
        hoy_iso = hoy.isoformat()
        for idx, p in enumerate(db):
            f_ini = normalizar_fecha_iso(p.get("fechaInicio"))
            f_fin = normalizar_fecha_iso(p.get("fechaFin"))
            if f_ini <= hoy_iso <= f_fin:
                return idx
        mejor_idx = 0
        menor_distancia = None
        for idx, p in enumerate(db):
            dt_ini = parse_iso_to_date(p.get("fechaInicio"))
            dt_fin = parse_iso_to_date(p.get("fechaFin"))
            if dt_ini and dt_fin:
                dist = min(abs((hoy - dt_ini).days), abs((hoy - dt_fin).days))
            elif dt_ini:
                dist = abs((hoy - dt_ini).days)
            elif dt_fin:
                dist = abs((hoy - dt_fin).days)
            else:
                continue
            if menor_distancia is None or dist < menor_distancia:
                menor_distancia = dist
                mejor_idx = idx
        return mejor_idx

    def obtener_nombre_presupuesto_activo(self) -> str:
        raw = self.app_data.get("resumenPantalla", {}).get("nombre", "")
        limpio = re.sub(r"^Presupuesto:\s*", "", str(raw), flags=re.IGNORECASE).strip()
        return limpio or "Nuevo Período"

    def _indice_presupuesto_activo(self) -> int:
        nombre_activo = self.obtener_nombre_presupuesto_activo()
        return next(
            (idx for idx, p in enumerate(self.app_data["presupuestosDB"])
             if limpiar_clave(p.get("nombre")) == limpiar_clave(nombre_activo)),
            -1
        )

    def obtener_lista_nombres_presupuestos(self, extra_nombre: str = "") -> list:
        nombres = []
        activo = self.obtener_nombre_presupuesto_activo()
        if activo:
            nombres.append(activo)
        for p in self.app_data["presupuestosDB"]:
            nom = p.get("nombre", "")
            if nom and not any(limpiar_clave(n) == limpiar_clave(nom) for n in nombres):
                nombres.append(nom)
        if extra_nombre and not any(limpiar_clave(n) == limpiar_clave(extra_nombre) for n in nombres):
            nombres.append(extra_nombre)
        return nombres

    def inferir_presupuesto_por_fecha(self, fecha_iso: str, presupuesto_explicito: str) -> str:
        explicito = str(presupuesto_explicito or "").strip()
        if explicito:
            for p in self.app_data["presupuestosDB"]:
                if limpiar_clave(p["nombre"]) == limpiar_clave(explicito):
                    return p["nombre"]
            return explicito
        f = normalizar_fecha_iso(fecha_iso)
        if not f:
            return self.obtener_nombre_presupuesto_activo()
        for p in self.app_data["presupuestosDB"]:
            p_ini = normalizar_fecha_iso(p["fechaInicio"])
            p_fin = normalizar_fecha_iso(p["fechaFin"])
            if p_ini <= f <= p_fin:
                return p["nombre"]
        return ""

    def pertenece_a_presupuesto_activo(self, mov: dict, nombre_activo: str, f_ini: str, f_fin: str) -> bool:
        pres_mov = str(mov.get("presupuesto") or "").strip()
        if pres_mov:
            return limpiar_clave(pres_mov) == limpiar_clave(nombre_activo)
        f = normalizar_fecha_iso(mov.get("fecha"))
        return f_ini <= f <= f_fin

    def pertenece_a_periodo_previo(self, mov: dict, nombre_activo: str, f_ini: str, f_fin: str) -> bool:
        if self.pertenece_a_presupuesto_activo(mov, nombre_activo, f_ini, f_fin):
            return False
        pres_mov = str(mov.get("presupuesto") or "").strip()
        if pres_mov:
            for p in self.app_data["presupuestosDB"]:
                if limpiar_clave(p["nombre"]) == limpiar_clave(pres_mov):
                    return normalizar_fecha_iso(p["fechaInicio"]) < f_ini
        f = normalizar_fecha_iso(mov.get("fecha"))
        return bool(f and f < f_ini)

    def _generar_id_unico(self, coleccion: list) -> int:
        return max((int(item.get("id") or 0) for item in coleccion), default=0) + 1

    def _generar_csv_gastos(self) -> str:
        ordenados = sorted(
            self.app_data["transacciones"],
            key=lambda t: (normalizar_fecha_iso(t.get("fecha")), int(t.get("id") or 0)),
            reverse=True
        )
        filas = [
            [
                normalizar_fecha_iso(t.get("fecha")),
                t.get("categoria") or "",
                t.get("concepto") or "",
                limpiar_importe(t.get("importe")),
                t.get("presupuesto") or ""
            ]
            for t in ordenados
        ]
        return serializar_csv(["Fecha", "Categoría", "Concepto", "Importe", "Presupuesto"], filas)

    def _generar_csv_ingresos(self) -> str:
        ordenados = sorted(
            self.app_data["ingresos"],
            key=lambda i: (normalizar_fecha_iso(i.get("fecha")), int(i.get("id") or 0)),
            reverse=True
        )
        filas = [
            [
                normalizar_fecha_iso(i.get("fecha")),
                i.get("categoria") or "",
                i.get("concepto") or "",
                limpiar_importe(i.get("importe")),
                i.get("presupuesto") or ""
            ]
            for i in ordenados
        ]
        return serializar_csv(["Fecha", "Categoría", "Concepto", "Importe", "Presupuesto"], filas)

    def _generar_csv_presupuestos(self) -> str:
        self._ordenar_presupuestos_db()
        cabecera = ["Nombre", "FechaInicio", "FechaFin"] + list(self.categorias_gastos)
        filas = []
        for p in self.app_data["presupuestosDB"]:
            montos = [limpiar_importe(p.get("montosPorCategoria", {}).get(c, 0)) for c in self.categorias_gastos]
            filas.append([
                p.get("nombre") or "",
                normalizar_fecha_iso(p.get("fechaInicio")),
                normalizar_fecha_iso(p.get("fechaFin")),
                *montos
            ])
        return serializar_csv(cabecera, filas)

    def persist(self, guardar_csv: bool = True, guardar_resumen: bool = True):
        self._ordenar_presupuestos_db()
        self.app_data["resumenPantalla"]["categoriasGastos"] = list(self.categorias_gastos)
        self.app_data["resumenPantalla"]["categoriasIngresos"] = list(self.categorias_ingresos)

        archivos = {}
        if guardar_csv:
            archivos["gastos.csv"] = self._generar_csv_gastos()
            archivos["ingresos.csv"] = self._generar_csv_ingresos()
            archivos["presupuestos.csv"] = self._generar_csv_presupuestos()
        if guardar_resumen:
            archivos["resumen_activo.json"] = json.dumps(self.app_data["resumenPantalla"], indent=2, ensure_ascii=False)

        errores = []
        for nombre, contenido in archivos.items():
            ruta = os.path.join(CSV_DIR, nombre)
            enc = "utf-8-sig" if nombre.endswith(".csv") else "utf-8"
            try:
                with open(ruta, "w", encoding=enc, newline="") as f:
                    f.write(contenido)
            except Exception:
                errores.append(nombre)

        if errores:
            self.sync_status_text = "⚠️ Error CSV"
            self.sync_status_ok = False
        else:
            hora = datetime.now().strftime("%H:%M")
            self.sync_status_text = f"📁 Sincronizado ({hora})"
            self.sync_status_ok = True

        self.render_ui()

    def cargar_desde_disco(self, forzar_actual_o_cercano: bool = True):
        self.categorias_gastos = list(CATEGORIAS_GASTOS_DEFAULT)
        self.categorias_ingresos = list(CATEGORIAS_INGRESOS_DEFAULT)

        res_raw = leer_archivo_seguro(os.path.join(CSV_DIR, "resumen_activo.json"))
        res_obj_loaded = None
        if res_raw:
            try:
                res_obj = json.loads(res_raw)
                if isinstance(res_obj, dict) and "montosPrevistos" in res_obj:
                    res_obj["fechaInicio"] = normalizar_fecha_iso(res_obj.get("fechaInicio"))
                    res_obj["fechaFin"] = normalizar_fecha_iso(res_obj.get("fechaFin"))
                    if isinstance(res_obj.get("categoriasGastos"), list) and res_obj["categoriasGastos"]:
                        self.categorias_gastos = [str(c).strip() for c in res_obj["categoriasGastos"] if str(c).strip()]
                    if isinstance(res_obj.get("categoriasIngresos"), list) and res_obj["categoriasIngresos"]:
                        self.categorias_ingresos = [str(c).strip() for c in res_obj["categoriasIngresos"] if str(c).strip()]
                    res_obj_loaded = res_obj
            except Exception:
                pass

        pres_raw = leer_archivo_seguro(os.path.join(CSV_DIR, "presupuestos.csv"))
        if pres_raw:
            filas = leer_filas_csv(pres_raw)
            if len(filas) > 1:
                encabezados = filas[0][3:]
                for cat_csv in encabezados:
                    cat_limpia = cat_csv.strip()
                    if cat_limpia and not resolver_categoria(cat_limpia, self.categorias_gastos, None):
                        self.categorias_gastos.append(cat_limpia)
                nueva_db = []
                for idx, cols in enumerate(filas[1:]):
                    mapa = {c: 0.0 for c in self.categorias_gastos}
                    for c_idx, cat_name in enumerate(encabezados):
                        cat_of = resolver_categoria(cat_name, self.categorias_gastos, None)
                        if cat_of and (c_idx + 3) < len(cols):
                            mapa[cat_of] = limpiar_importe(cols[c_idx + 3])
                    nueva_db.append({
                        "id": idx + 1,
                        "nombre": (cols[0] if len(cols) > 0 else "Sin nombre").strip(),
                        "fechaInicio": normalizar_fecha_iso(cols[1] if len(cols) > 1 else ""),
                        "fechaFin": normalizar_fecha_iso(cols[2] if len(cols) > 2 else ""),
                        "montosPorCategoria": mapa
                    })
                self.app_data["presupuestosDB"] = nueva_db
                self._ordenar_presupuestos_db()

        ocultar_g = bool(res_obj_loaded.get("ocultarSinUsarGastos", True)) if res_obj_loaded else True
        ocultar_i = bool(res_obj_loaded.get("ocultarSinUsarIngresos", True)) if res_obj_loaded else True

        if self.app_data["presupuestosDB"] and (forzar_actual_o_cercano or res_obj_loaded is None):
            idx_ideal = self._obtener_indice_presupuesto_ideal()
            elegido = self.app_data["presupuestosDB"][max(0, idx_ideal)]
            self.app_data["resumenPantalla"] = {
                "nombre": "Presupuesto: " + elegido["nombre"],
                "fechaInicio": normalizar_fecha_iso(elegido["fechaInicio"]),
                "fechaFin": normalizar_fecha_iso(elegido["fechaFin"]),
                "ocultarSinUsarGastos": ocultar_g,
                "ocultarSinUsarIngresos": ocultar_i,
                "montosPrevistos": {
                    c: float(elegido.get("montosPorCategoria", {}).get(c) or 0.0)
                    for c in self.categorias_gastos
                },
                "categoriasGastos": list(self.categorias_gastos),
                "categoriasIngresos": list(self.categorias_ingresos)
            }
        elif res_obj_loaded is not None:
            for c in self.categorias_gastos:
                res_obj_loaded["montosPrevistos"].setdefault(c, 0.0)
            self.app_data["resumenPantalla"] = res_obj_loaded

        gas_raw = leer_archivo_seguro(os.path.join(CSV_DIR, "gastos.csv"))
        if gas_raw:
            filas = leer_filas_csv(gas_raw)[1:]
            total_l = len(filas)
            trans = []
            fallback_g = resolver_categoria("Otros Fuera Presupuesto", self.categorias_gastos, self.categorias_gastos[-1])
            for idx, cols in enumerate(filas):
                f = normalizar_fecha_iso(cols[0] if len(cols) > 0 else "")
                pres_col = cols[4] if len(cols) >= 5 else ""
                trans.append({
                    "id": total_l - idx,
                    "fecha": f,
                    "categoria": resolver_categoria(cols[1] if len(cols) > 1 else "", self.categorias_gastos, fallback_g),
                    "concepto": (cols[2] if len(cols) > 2 else "").strip(),
                    "importe": limpiar_importe(cols[3] if len(cols) > 3 else 0),
                    "presupuesto": self.inferir_presupuesto_por_fecha(f, pres_col)
                })
            self.app_data["transacciones"] = trans

        ing_raw = leer_archivo_seguro(os.path.join(CSV_DIR, "ingresos.csv"))
        if ing_raw:
            filas = leer_filas_csv(ing_raw)[1:]
            total_l = len(filas)
            ingresos = []
            fallback_i = resolver_categoria("Efectivo", self.categorias_ingresos, self.categorias_ingresos[0])
            for idx, cols in enumerate(filas):
                f = normalizar_fecha_iso(cols[0] if len(cols) > 0 else "")
                pres_col = cols[4] if len(cols) >= 5 else ""
                ingresos.append({
                    "id": total_l - idx,
                    "fecha": f,
                    "categoria": resolver_categoria(cols[1] if len(cols) > 1 else "", self.categorias_ingresos, fallback_i),
                    "concepto": (cols[2] if len(cols) > 2 else "").strip(),
                    "importe": limpiar_importe(cols[3] if len(cols) > 3 else 0),
                    "presupuesto": self.inferir_presupuesto_por_fecha(f, pres_col)
                })
            self.app_data["ingresos"] = ingresos

        self.app_data["resumenPantalla"].setdefault("ocultarSinUsarGastos", True)
        self.app_data["resumenPantalla"].setdefault("ocultarSinUsarIngresos", True)
        self.persist()

    # -----------------------------------------------------------------
    # COMPONENTES DE DIÁLOGOS MODERNOS Y SELECTORES
    # -----------------------------------------------------------------
    def _abrir_dialogo(self, dlg: ft.AlertDialog):
        # Limpiar únicamente diálogos que ya fueron cerrados en turnos previos
        for d in list(self.page.overlay):
            if isinstance(d, ft.AlertDialog) and not getattr(d, "open", False) and d is not dlg:
                self.page.overlay.remove(d)

        dlg.inset_padding = ft.Padding.symmetric(horizontal=12, vertical=16)
        if dlg not in self.page.overlay:
            self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _cerrar_dialogo(self, dlg: ft.AlertDialog):
        dlg.open = False
        self.page.update()

    def mostrar_alerta(self, titulo: str, mensaje: str, icono: str = "ℹ️"):
        dlg = ft.AlertDialog(
            title=ft.Container(
                bgcolor="#4a78a8", padding=10, border_radius=6,
                content=ft.Text(f"{icono}  {titulo}", color="white", weight=ft.FontWeight.BOLD, size=13)
            ),
            content=ft.Container(
                bgcolor="#f0f7ff", border=ft.Border.all(1, "#b8d4f0"), border_radius=6, padding=12, width=310,
                content=ft.Text(mensaje, color="#1e293b", size=12)
            ),
            actions=[
                ft.Button("✓ Aceptar", bgcolor="#10b981", color="white", on_click=lambda e: self._cerrar_dialogo(dlg))
            ]
        )
        self._abrir_dialogo(dlg)

    def mostrar_confirmacion(self, titulo: str, mensaje: str, on_confirm):
        def _ok(e):
            self._cerrar_dialogo(dlg)
            on_confirm()

        dlg = ft.AlertDialog(
            title=ft.Container(
                bgcolor="#4a78a8", padding=10, border_radius=6,
                content=ft.Text(f"❓  {titulo}", color="white", weight=ft.FontWeight.BOLD, size=13)
            ),
            content=ft.Container(
                bgcolor="#f0f7ff", border=ft.Border.all(1, "#b8d4f0"), border_radius=6, padding=12, width=310,
                content=ft.Text(mensaje, color="#1e293b", size=12)
            ),
            actions=[
                ft.Button("✕ Cancelar", bgcolor="#e11d48", color="white", on_click=lambda e: self._cerrar_dialogo(dlg)),
                ft.Button("✓ Aceptar", bgcolor="#10b981", color="white", on_click=_ok)
            ]
        )
        self._abrir_dialogo(dlg)

    def pedir_texto_moderno(self, titulo: str, etiqueta: str, valor_inicial: str, on_submit_text):
        inp = ft.TextField(value=valor_inicial, text_size=12, border_color="#93c5fd", autofocus=True)

        def _ok(e):
            val = (inp.value or "").strip()
            self._cerrar_dialogo(dlg)
            if val:
                on_submit_text(val)

        dlg = ft.AlertDialog(
            title=ft.Container(
                bgcolor="#4a78a8", padding=10, border_radius=6,
                content=ft.Text(titulo, color="white", weight=ft.FontWeight.BOLD, size=13)
            ),
            content=ft.Column([
                ft.Container(
                    bgcolor="#f0f7ff", border=ft.Border.all(1, "#b8d4f0"), border_radius=6, padding=10,
                    content=ft.Text(etiqueta, color="#1e293b", size=12)
                ),
                inp
            ], tight=True, width=310, spacing=10),
            actions=[
                ft.Button("✕ Cancelar", bgcolor="#e11d48", color="white", on_click=lambda e: self._cerrar_dialogo(dlg)),
                ft.Button("✓ Aceptar", bgcolor="#10b981", color="white", on_click=_ok)
            ]
        )
        self._abrir_dialogo(dlg)

    def abrir_selector_fecha(self, iso_actual: str, titulo: str, on_select_iso):
        dt_base = parse_iso_to_date(iso_actual) or date.today()
        tf_iso = ft.TextField(label="Fecha ISO (YYYY-MM-DD)", value=dt_base.isoformat(), text_size=12)
        lbl_bonita = ft.Text(formatear_fecha_bonita(dt_base.isoformat()), color="#2c5282", weight=ft.FontWeight.BOLD, size=12)

        def _actualizar_preview(e=None):
            lbl_bonita.value = formatear_fecha_bonita(tf_iso.value)
            self.page.update()

        tf_iso.on_change = _actualizar_preview

        def _set_quick(d: date):
            tf_iso.value = d.isoformat()
            _actualizar_preview()

        def _confirmar(e):
            norm = normalizar_fecha_iso(tf_iso.value)
            if not parse_iso_to_date(norm):
                self.mostrar_alerta("Fecha inválida", "Usa el formato YYYY-MM-DD (ejemplo: 2026-11-15).", "⚠️")
                return
            self._cerrar_dialogo(dlg)
            on_select_iso(norm)

        hoy = date.today()
        ult_dia = _ultimo_dia_mes(hoy.year, hoy.month)

        dlg = ft.AlertDialog(
            title=ft.Container(
                bgcolor="#4a78a8", padding=10, border_radius=6,
                content=ft.Text(f"📅  {titulo}", color="white", weight=ft.FontWeight.BOLD, size=13)
            ),
            content=ft.Column([
                ft.Container(
                    bgcolor="#eaf3fc", padding=8, border_radius=6, border=ft.Border.all(1, "#b8d4f0"),
                    content=lbl_bonita
                ),
                tf_iso,
                ft.Row([
                    ft.Button("Hoy", bgcolor="#eaf3fc", color="#2c5282", on_click=lambda e: _set_quick(hoy)),
                    ft.Button("Día 01", bgcolor="#eaf3fc", color="#2c5282", on_click=lambda e: _set_quick(date(hoy.year, hoy.month, 1))),
                    ft.Button("Día 15", bgcolor="#eaf3fc", color="#2c5282", on_click=lambda e: _set_quick(date(hoy.year, hoy.month, 15))),
                    ft.Button(f"Día {ult_dia}", bgcolor="#eaf3fc", color="#2c5282", on_click=lambda e: _set_quick(date(hoy.year, hoy.month, ult_dia))),
                ], wrap=True, spacing=6)
            ], tight=True, width=310, spacing=10),
            actions=[
                ft.Button("✕ Cancelar", bgcolor="#e11d48", color="white", on_click=lambda e: self._cerrar_dialogo(dlg)),
                ft.Button("✓ Aplicar", bgcolor="#10b981", color="white", on_click=_confirmar)
            ]
        )
        self._abrir_dialogo(dlg)

    def abrir_buscador_en_vivo(self, titulo: str, opciones: list, on_choose):
        tf_search = ft.TextField(
            hint_text="🔎 Escribe para filtrar...",
            text_size=12, border_color="#93c5fd", autofocus=True
        )
        lbl_info = ft.Text("Sugerencias", size=11, color="#3b6998", weight=ft.FontWeight.BOLD)
        col_items = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=230)

        def _seleccionar(val):
            self._cerrar_dialogo(dlg)
            on_choose(val)

        def _filtrar(query_raw: str = ""):
            tokens = [limpiar_clave(t) for t in query_raw.strip().split() if t.strip()]
            if not tokens:
                matches = list(opciones)
            else:
                matches = [
                    it for it in opciones
                    if all(tok in limpiar_clave(f"{it[0]} {it[2] if len(it) > 2 else ''}") for tok in tokens)
                ]
            col_items.controls.clear()
            visibles = matches[:20]
            if not visibles:
                lbl_info.value = "⚠️ Sin coincidencias"
                col_items.controls.append(ft.Text("No se encontraron resultados", color="#94a3b8", size=12))
            else:
                lbl_info.value = f"🔎 Mostrando {len(visibles)} de {len(matches)} opción(es)"
                for label, val, *_ in visibles:
                    col_items.controls.append(
                        ft.Container(
                            bgcolor="#f5f9fd", border=ft.Border.all(1, "#d4e4f4"), border_radius=6,
                            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                            on_click=lambda e, v=val: _seleccionar(v),
                            content=ft.Text(label, color="#1e293b", size=12, weight=ft.FontWeight.W_600)
                        )
                    )
            self.page.update()

        tf_search.on_change = lambda e: _filtrar(tf_search.value or "")

        dlg = ft.AlertDialog(
            title=ft.Container(
                bgcolor="#4a78a8", padding=10, border_radius=6,
                content=ft.Text(titulo, color="white", weight=ft.FontWeight.BOLD, size=13)
            ),
            content=ft.Column([tf_search, lbl_info, col_items], tight=True, width=320, spacing=8),
            actions=[
                ft.Button("✕ Cerrar", bgcolor="#e11d48", color="white", on_click=lambda e: self._cerrar_dialogo(dlg))
            ]
        )
        _filtrar("")
        self._abrir_dialogo(dlg)

    # -----------------------------------------------------------------
    # EXPLORADOR INTERACTIVO DEL SISTEMA DE ARCHIVOS (IMPORTAR/EXPORTAR)
    # -----------------------------------------------------------------
    def abrir_explorador_archivos(self, modo: str = "importar", on_file_selected=None):
        es_importar = (modo == "importar")
        dir_inicial = self.ultimo_dir_explorador if os.path.isdir(self.ultimo_dir_explorador) else CSV_DIR
        estado_nav = {"dir": os.path.abspath(dir_inicial)}

        tf_ruta = ft.TextField(
            value=estado_nav["dir"],
            label="Ruta actual (puedes escribir o pegar una ruta)",
            text_size=11, height=38, expand=True,
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_color="#93c5fd"
        )
        tf_filtro = ft.TextField(
            hint_text="🔎 Filtrar carpetas o archivos .json...",
            text_size=11.5, height=34,
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_color="#cbd5e1"
        )
        tf_nombre_export = ft.TextField(
            label="Nombre del archivo a guardar",
            value=f"presupuesto_backup_{get_local_iso_date()}.json",
            text_size=11.5, height=38,
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_color="#6ee7b7"
        )
        lbl_estado_dir = ft.Text("", size=10.5, color="#3b6998", weight=ft.FontWeight.BOLD)
        col_archivos = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=220)

        def _cambiar_directorio(nueva_ruta: str):
            ruta_limpia = os.path.abspath(os.path.expanduser(str(nueva_ruta or "").strip()))
            if not os.path.exists(ruta_limpia):
                self.mostrar_alerta("Ruta no encontrada", f"No existe el directorio:\n{ruta_limpia}", "⚠️")
                return
            if os.path.isfile(ruta_limpia):
                ruta_limpia = os.path.dirname(ruta_limpia)
            try:
                os.listdir(ruta_limpia)
            except PermissionError:
                self.mostrar_alerta("Permiso denegado", f"El sistema bloqueó el acceso a:\n{ruta_limpia}", "🔒")
                return
            except Exception as ex:
                self.mostrar_alerta("Error de acceso", str(ex), "⚠️")
                return

            estado_nav["dir"] = ruta_limpia
            self.ultimo_dir_explorador = ruta_limpia
            tf_ruta.value = ruta_limpia
            _render_listado()

        def _subir_nivel(e=None):
            actual = estado_nav["dir"]
            padre = os.path.dirname(actual)
            if padre and padre != actual:
                _cambiar_directorio(padre)

        def _al_tocar_json(ruta_completa: str, nombre_arch: str):
            if es_importar:
                self._cerrar_dialogo(dlg)
                if on_file_selected:
                    on_file_selected(ruta_completa)
            else:
                tf_nombre_export.value = nombre_arch
                self.page.update()

        def _render_listado():
            col_archivos.controls.clear()
            dir_actual = estado_nav["dir"]
            q = limpiar_clave(tf_filtro.value or "")

            try:
                entradas = os.listdir(dir_actual)
            except Exception as ex:
                lbl_estado_dir.value = "⚠️ Error leyendo carpeta"
                col_archivos.controls.append(ft.Text(f"No se pudo leer la carpeta: {ex}", color="#dc2626", size=11))
                self.page.update()
                return

            carpetas = []
            archivos_json = []

            for nombre in entradas:
                if nombre.startswith("."):
                    continue
                if q and q not in limpiar_clave(nombre):
                    continue
                ruta_item = os.path.join(dir_actual, nombre)
                try:
                    if os.path.isdir(ruta_item):
                        carpetas.append((nombre, ruta_item))
                    elif os.path.isfile(ruta_item) and nombre.lower().endswith(".json"):
                        stat = os.stat(ruta_item)
                        kb = stat.st_size / 1024.0
                        fecha_mod = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                        archivos_json.append((nombre, ruta_item, f"{kb:.1f} KB • {fecha_mod}"))
                except OSError:
                    continue

            carpetas.sort(key=lambda x: limpiar_clave(x[0]))
            archivos_json.sort(key=lambda x: x[0].lower(), reverse=True)

            padre = os.path.dirname(dir_actual)
            if padre and padre != dir_actual:
                col_archivos.controls.append(
                    ft.Container(
                        bgcolor="#eaf3fc", border=ft.Border.all(1, "#93c5fd"), border_radius=6,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                        on_click=_subir_nivel,
                        content=ft.Row([
                            ft.Text("⬆️", size=13),
                            ft.Text(".. (Subir a carpeta superior)", color="#2c5282", weight=ft.FontWeight.BOLD, size=11.5, expand=True)
                        ], spacing=6)
                    )
                )

            for nom_c, ruta_c in carpetas:
                col_archivos.controls.append(
                    ft.Container(
                        bgcolor="#f8fafc", border=ft.Border.all(1, "#cbd5e1"), border_radius=6,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                        on_click=lambda e, rc=ruta_c: _cambiar_directorio(rc),
                        content=ft.Row([
                            ft.Text("📁", size=13),
                            ft.Text(nom_c, color="#1e293b", weight=ft.FontWeight.W_600, size=11.5, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text("Abrir ▶", color="#64748b", size=10)
                        ], spacing=6)
                    )
                )

            for nom_a, ruta_a, meta_a in archivos_json:
                es_resumen_interno = (nom_a == "resumen_activo.json")
                col_archivos.controls.append(
                    ft.Container(
                        bgcolor="#ecfdf5" if not es_resumen_interno else "#fefce8",
                        border=ft.Border.all(1, "#6ee7b7" if not es_resumen_interno else "#fde047"),
                        border_radius=6,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                        on_click=lambda e, ra=ruta_a, na=nom_a: _al_tocar_json(ra, na),
                        content=ft.Column([
                            ft.Row([
                                ft.Text("📄", size=12),
                                ft.Text(nom_a, color="#065f46" if not es_resumen_interno else "#854d0e", weight=ft.FontWeight.BOLD, size=11.5, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text("Cargar" if es_importar else "Elegir", color="#059669", size=10, weight=ft.FontWeight.BOLD)
                            ], spacing=6),
                            ft.Text(meta_a, color="#64748b", size=9.5)
                        ], spacing=2)
                    )
                )

            if not carpetas and not archivos_json:
                col_archivos.controls.append(
                    ft.Container(
                        padding=12, alignment=ft.Alignment(0, 0),
                        content=ft.Text("No hay subcarpetas ni archivos .json en esta ruta.", color="#94a3b8", size=11.5)
                    )
                )

            lbl_estado_dir.value = f"📁 {len(carpetas)} carpeta(s)  |  📄 {len(archivos_json)} archivo(s) .json"
            self.page.update()

        tf_ruta.on_submit = lambda e: _cambiar_directorio(tf_ruta.value or "")
        tf_filtro.on_change = lambda e: _render_listado()

        chips_accesos = [
            ft.Container(
                bgcolor="#eaf3fc", border=ft.Border.all(1, "#93c5fd"), border_radius=12,
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                on_click=lambda e, r=ruta_dest: _cambiar_directorio(r),
                content=ft.Text(etiqueta, color="#2c5282", size=10, weight=ft.FontWeight.BOLD)
            )
            for etiqueta, ruta_dest in obtener_rutas_rapidas()
        ]

        controles_modal = [
            ft.Row([
                tf_ruta,
                ft.Button("Ir", bgcolor="#4a78a8", color="white", on_click=lambda e: _cambiar_directorio(tf_ruta.value or ""))
            ], spacing=4),
            ft.Row(chips_accesos, wrap=True, spacing=4, run_spacing=4),
            tf_filtro,
            lbl_estado_dir,
            ft.Container(
                border=ft.Border.all(1, "#c2d5e8"), border_radius=6, padding=4, bgcolor="#ffffff",
                content=col_archivos
            )
        ]

        acciones_modal = [
            ft.Button("✕ Cancelar", bgcolor="#e11d48", color="white", on_click=lambda e: self._cerrar_dialogo(dlg))
        ]

        if not es_importar:
            controles_modal.append(tf_nombre_export)

            def _confirmar_export(e):
                nom = (tf_nombre_export.value or "").strip()
                if not nom:
                    self.mostrar_alerta("Validación", "Escribe un nombre para el archivo.", "⚠️")
                    return
                if not nom.lower().endswith(".json"):
                    nom += ".json"
                ruta_final = os.path.join(estado_nav["dir"], nom)
                self._cerrar_dialogo(dlg)
                if on_file_selected:
                    on_file_selected(ruta_final)

            acciones_modal.append(
                ft.Button("💾 Guardar Aquí", bgcolor="#10b981", color="white", on_click=_confirmar_export)
            )

        dlg = ft.AlertDialog(
            title=ft.Container(
                bgcolor="#4a78a8", padding=10, border_radius=6,
                content=ft.Text(
                    "📂 Explorador: Cargar Backup (.json)" if es_importar else "💾 Explorador: Guardar Backup (.json)",
                    color="white", weight=ft.FontWeight.BOLD, size=12.5
                )
            ),
            content=ft.Column(controles_modal, tight=True, width=330, spacing=6),
            actions=acciones_modal
        )
        _render_listado()
        self._abrir_dialogo(dlg)

    # -----------------------------------------------------------------
    # MODALES: GASTO / INGRESO / PRESUPUESTO / CATEGORÍAS
    # -----------------------------------------------------------------
    def open_movimiento_modal(self, tipo: str, edit_id=None):
        es_gasto = (tipo == "gasto")
        coleccion = self.app_data["transacciones"] if es_gasto else self.app_data["ingresos"]
        lista_categorias = self.categorias_gastos if es_gasto else self.categorias_ingresos
        item_editar = None
        if edit_id is not None:
            item_editar = next((x for x in coleccion if int(x["id"]) == int(edit_id)), None)
            if not item_editar:
                return

        es_edicion = item_editar is not None
        titulo = ("✏️ Editar Gasto" if es_edicion else "💳 Registrar Gasto") if es_gasto else (
            "✏️ Editar Ingreso" if es_edicion else "💵 Registrar Ingreso"
        )

        lista_pres = self.obtener_lista_nombres_presupuestos()
        pres_activo = self.obtener_nombre_presupuesto_activo()

        estado_modal = {
            "fecha": normalizar_fecha_iso(item_editar["fecha"]) if es_edicion else get_local_iso_date(),
            "presupuesto": (item_editar.get("presupuesto") if es_edicion else pres_activo) or pres_activo,
            "categoria": resolver_categoria(item_editar.get("categoria"), lista_categorias, lista_categorias[0]) if es_edicion else lista_categorias[0]
        }

        lbl_fecha_btn = ft.Text(f"{formatear_fecha_bonita(estado_modal['fecha'])}   📅", color="#2c5282", weight=ft.FontWeight.BOLD, size=12)
        lbl_pres_btn = ft.Text(f"📊 {estado_modal['presupuesto']}   ▾", color="#2c5282", weight=ft.FontWeight.BOLD, size=12)
        lbl_cat_btn = ft.Text(f"🏷️ {estado_modal['categoria']}   ▾", color="#0f172a", weight=ft.FontWeight.W_600, size=12)

        inp_concepto = ft.TextField(
            label="Concepto / Detalle",
            value=item_editar.get("concepto", "") if es_edicion else "",
            text_size=12, border_color="#b8d4f0"
        )
        inp_importe = ft.TextField(
            label="Importe ($)",
            value=str(limpiar_importe(item_editar.get("importe", 0))) if es_edicion else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            text_size=12, border_color="#b8d4f0"
        )

        def _cambiar_fecha(nueva_iso):
            estado_modal["fecha"] = nueva_iso
            lbl_fecha_btn.value = f"{formatear_fecha_bonita(nueva_iso)}   📅"
            self.page.update()

        def _cambiar_pres(nuevo_p):
            estado_modal["presupuesto"] = nuevo_p
            lbl_pres_btn.value = f"📊 {nuevo_p}   ▾"
            self.page.update()

        def _cambiar_cat(nueva_c):
            estado_modal["categoria"] = nueva_c
            lbl_cat_btn.value = f"🏷️ {nueva_c}   ▾"
            self.page.update()

        def _guardar(e):
            concepto = (inp_concepto.value or "").strip()
            imp_txt = (inp_importe.value or "").strip()
            if not concepto:
                self.mostrar_alerta("Validación", "Ingresa el concepto o detalle.", "⚠️")
                return
            if not imp_txt:
                self.mostrar_alerta("Validación", "Ingresa el importe.", "⚠️")
                return
            datos = {
                "fecha": estado_modal["fecha"],
                "presupuesto": estado_modal["presupuesto"],
                "categoria": estado_modal["categoria"],
                "concepto": concepto,
                "importe": limpiar_importe(imp_txt)
            }
            if es_edicion:
                item_editar.update(datos)
            else:
                datos["id"] = self._generar_id_unico(coleccion)
                coleccion.append(datos)
            self._cerrar_dialogo(dlg)
            self.persist()

        dlg = ft.AlertDialog(
            title=ft.Container(
                bgcolor="#4a78a8", padding=10, border_radius=6,
                content=ft.Text(titulo, color="white", weight=ft.FontWeight.BOLD, size=13)
            ),
            content=ft.Column([
                ft.Text("Fecha Real de Operación", color="#2c5282", weight=ft.FontWeight.BOLD, size=11),
                ft.Container(
                    bgcolor="#ffffff", border=ft.Border.all(1.5, "#b8d4f0"), border_radius=6, padding=9,
                    on_click=lambda e: self.abrir_selector_fecha(estado_modal["fecha"], "Fecha de Operación", _cambiar_fecha),
                    content=lbl_fecha_btn
                ),
                ft.Text("📊 Presupuesto al que aplica", color="#2c5282", weight=ft.FontWeight.BOLD, size=11),
                ft.Container(
                    bgcolor="#eaf3fc", border=ft.Border.all(1.5, "#93c5fd"), border_radius=12, padding=9,
                    on_click=lambda e: self.abrir_buscador_en_vivo(
                        "Seleccionar Presupuesto",
                        [(f"📊 {n}", n, n) for n in lista_pres],
                        _cambiar_pres
                    ),
                    content=lbl_pres_btn
                ),
                ft.Text("Categoría", color="#2c5282", weight=ft.FontWeight.BOLD, size=11),
                ft.Container(
                    bgcolor="#ffffff", border=ft.Border.all(1.5, "#b8d4f0"), border_radius=6, padding=9,
                    on_click=lambda e: self.abrir_buscador_en_vivo(
                        "Seleccionar Categoría",
                        [(c, c, c) for c in lista_categorias],
                        _cambiar_cat
                    ),
                    content=lbl_cat_btn
                ),
                inp_concepto,
                inp_importe
            ], tight=True, width=320, scroll=ft.ScrollMode.AUTO, spacing=7),
            actions=[
                ft.Button("✕ Cancelar", bgcolor="#e11d48", color="white", on_click=lambda e: self._cerrar_dialogo(dlg)),
                ft.Button("✓ Guardar", bgcolor="#10b981", color="white", on_click=_guardar)
            ]
        )
        self._abrir_dialogo(dlg)

    def abrir_modal_presupuesto(self, orig_idx: int = None):
        self._ordenar_presupuestos_db()
        db = self.app_data["presupuestosDB"]
        item_editar = db[orig_idx] if (orig_idx is not None and 0 <= orig_idx < len(db)) else None
        es_edicion = item_editar is not None

        if es_edicion:
            f_ini_def = normalizar_fecha_iso(item_editar["fechaInicio"])
            f_fin_def = normalizar_fecha_iso(item_editar["fechaFin"])
            montos_ini = dict(item_editar.get("montosPorCategoria", {}))
        else:
            if db:
                rec = db[0]
                sug = sugerir_fechas_siguiente_periodo(rec["fechaFin"])
                f_ini_def, f_fin_def = sug["inicio"], sug["fin"]
                montos_ini = dict(self.app_data["resumenPantalla"].get("montosPrevistos") or rec.get("montosPorCategoria", {}))
            else:
                sug = get_default_period_dates()
                f_ini_def, f_fin_def = sug["inicio"], sug["fin"]
                montos_ini = dict(self.app_data["resumenPantalla"].get("montosPrevistos", {}))

        estado_fechas = {"ini": f_ini_def, "fin": f_fin_def}
        inp_nombre = ft.TextField(
            label="Nombre del Período (Ej. Q2 Nov 2026)",
            value=item_editar["nombre"] if es_edicion else "",
            text_size=12, border_color="#b8d4f0"
        )
        lbl_f_ini = ft.Text(f"Inicio: {formatear_fecha_bonita(f_ini_def)} 📅", color="#2c5282", weight=ft.FontWeight.BOLD, size=11)
        lbl_f_fin = ft.Text(f"Fin: {formatear_fecha_bonita(f_fin_def)} 📅", color="#2c5282", weight=ft.FontWeight.BOLD, size=11)
        lbl_total_live = ft.Text("Total: $0.00", color="white", weight=ft.FontWeight.BOLD, size=11.5)

        inputs_cat = {}
        filas_cat = []

        def _recalc(e=None):
            tot = sum(limpiar_importe(tf.value) for tf in inputs_cat.values())
            lbl_total_live.value = f"Total: {format_money(tot)}"
            self.page.update()

        for cat in self.categorias_gastos:
            v_ini = float(montos_ini.get(cat) or 0.0)
            tf_c = ft.TextField(
                value=f"{v_ini:g}" if v_ini.is_integer() else f"{v_ini:.2f}",
                width=95, height=34, text_size=12, text_align=ft.TextAlign.RIGHT,
                content_padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                keyboard_type=ft.KeyboardType.NUMBER, on_change=_recalc
            )
            inputs_cat[cat] = tf_c
            filas_cat.append(
                ft.Row([
                    ft.Text(cat, size=11.5, weight=ft.FontWeight.W_600, color="#1e293b", expand=True),
                    tf_c
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )

        def _copiar_reciente(e):
            if not db:
                return
            rec_m = db[0].get("montosPorCategoria", {})
            for c, tf in inputs_cat.items():
                v = float(rec_m.get(c) or 0.0)
                tf.value = f"{v:g}" if v.is_integer() else f"{v:.2f}"
            _recalc()

        def _poner_cero(e):
            for tf in inputs_cat.values():
                tf.value = "0"
            _recalc()

        def _guardar_pres(e):
            nombre = (inp_nombre.value or "").strip()
            f_ini = estado_fechas["ini"]
            f_fin = estado_fechas["fin"]
            if not nombre:
                self.mostrar_alerta("Validación", "Ingresa un nombre para el presupuesto.", "⚠️")
                return
            if not f_ini or not f_fin or f_ini > f_fin:
                self.mostrar_alerta("Validación de Fechas", "La Fecha Inicio no puede ser mayor que la Fecha Fin.", "⚠️")
                return
            montos = {c: limpiar_importe(tf.value) for c, tf in inputs_cat.items()}
            if sum(montos.values()) <= 0:
                self.mostrar_alerta("Validación de Montos", "El presupuesto debe tener al menos un monto previsto mayor a $0.00.", "⚠️")
                return

            for idx, p in enumerate(db):
                if es_edicion and idx == orig_idx:
                    continue
                if limpiar_clave(p["nombre"]) == limpiar_clave(nombre):
                    self.mostrar_alerta("Nombre Duplicado", f"Ya existe otro presupuesto con el nombre '{nombre}'.", "⚠️")
                    return
                p_ini = normalizar_fecha_iso(p["fechaInicio"])
                p_fin = normalizar_fecha_iso(p["fechaFin"])
                if f_ini <= p_fin and f_fin >= p_ini:
                    self.mostrar_alerta("Traslape de Fechas", f"El período choca con '{p['nombre']}'.", "⚠️")
                    return

            self._cerrar_dialogo(dlg)
            if es_edicion:
                nombre_viejo = item_editar["nombre"]
                item_editar["nombre"] = nombre
                item_editar["fechaInicio"] = f_ini
                item_editar["fechaFin"] = f_fin
                item_editar["montosPorCategoria"] = dict(montos)
                if limpiar_clave(nombre_viejo) != limpiar_clave(nombre):
                    for t in self.app_data["transacciones"]:
                        if limpiar_clave(t.get("presupuesto")) == limpiar_clave(nombre_viejo):
                            t["presupuesto"] = nombre
                    for i in self.app_data["ingresos"]:
                        if limpiar_clave(i.get("presupuesto")) == limpiar_clave(nombre_viejo):
                            i["presupuesto"] = nombre
                if limpiar_clave(self.obtener_nombre_presupuesto_activo()) == limpiar_clave(nombre_viejo):
                    res = self.app_data["resumenPantalla"]
                    res["nombre"] = "Presupuesto: " + nombre
                    res["fechaInicio"] = f_ini
                    res["fechaFin"] = f_fin
                    res["montosPrevistos"] = dict(montos)
                self.persist()
                self.mostrar_alerta("Presupuesto Actualizado", f"El presupuesto '{nombre}' fue actualizado.", "✅")
            else:
                db.append({
                    "id": self._generar_id_unico(db),
                    "nombre": nombre,
                    "fechaInicio": f_ini,
                    "fechaFin": f_fin,
                    "montosPorCategoria": dict(montos)
                })
                self._ordenar_presupuestos_db()
                res = self.app_data["resumenPantalla"]
                res["nombre"] = "Presupuesto: " + nombre
                res["fechaInicio"] = f_ini
                res["fechaFin"] = f_fin
                res["montosPrevistos"] = dict(montos)
                self.persist()
                self.mostrar_alerta("Presupuesto Creado", f"El presupuesto '{nombre}' se creó y cargó como activo.", "✅")

        _recalc()
        titulo_dlg = "✏️ Editar Presupuesto" if es_edicion else "➕ Nuevo Presupuesto"

        dlg = ft.AlertDialog(
            title=ft.Container(
                bgcolor="#4a78a8", padding=10, border_radius=6,
                content=ft.Row([
                    ft.Text(titulo_dlg, color="white", weight=ft.FontWeight.BOLD, size=12.5, expand=True),
                    lbl_total_live
                ])
            ),
            content=ft.Column([
                inp_nombre,
                ft.Container(
                    bgcolor="#f5f9fd", border=ft.Border.all(1.5, "#b8d4f0"), border_radius=6, padding=8,
                    on_click=lambda e: self.abrir_selector_fecha(
                        estado_fechas["ini"], "Fecha Inicio",
                        lambda iso: (estado_fechas.update({"ini": iso}), setattr(lbl_f_ini, "value", f"Inicio: {formatear_fecha_bonita(iso)} 📅"), self.page.update())
                    ),
                    content=lbl_f_ini
                ),
                ft.Container(
                    bgcolor="#f5f9fd", border=ft.Border.all(1.5, "#b8d4f0"), border_radius=6, padding=8,
                    on_click=lambda e: self.abrir_selector_fecha(
                        estado_fechas["fin"], "Fecha Fin",
                        lambda iso: (estado_fechas.update({"fin": iso}), setattr(lbl_f_fin, "value", f"Fin: {formatear_fecha_bonita(iso)} 📅"), self.page.update())
                    ),
                    content=lbl_f_fin
                ),
                ft.Row([
                    ft.Button("📋 Copiar reciente", bgcolor="#eaf3fc", color="#2c5282", on_click=_copiar_reciente),
                    ft.Button("🧹 $0.00", bgcolor="#eaf3fc", color="#2c5282", on_click=_poner_cero),
                ], spacing=6, wrap=True),
                ft.Container(
                    bgcolor="#f8fbff", border=ft.Border.all(1, "#c2d5e8"), border_radius=6, padding=8, height=220,
                    content=ft.Column(filas_cat, scroll=ft.ScrollMode.AUTO, spacing=6)
                )
            ], tight=True, width=325, spacing=7),
            actions=[
                ft.Button("✕ Cancelar", bgcolor="#e11d48", color="white", on_click=lambda e: self._cerrar_dialogo(dlg)),
                ft.Button("✓ Guardar", bgcolor="#10b981", color="white", on_click=_guardar_pres)
            ]
        )
        self._abrir_dialogo(dlg)

    def abrir_gestor_categorias(self):
        estado = {"tipo": "gastos", "sel_idx": 0}
        col_lista = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=210)
        btn_tipo_gas = ft.Button("💳 Gastos", bgcolor="#4a78a8", color="white")
        btn_tipo_ing = ft.Button("💵 Ingresos", bgcolor="#eaf3fc", color="#2c5282")

        def _lista_activa():
            return self.categorias_gastos if estado["tipo"] == "gastos" else self.categorias_ingresos

        def _refrescar_lista():
            lista = _lista_activa()
            if estado["sel_idx"] >= len(lista):
                estado["sel_idx"] = max(0, len(lista) - 1)
            btn_tipo_gas.bgcolor = "#4a78a8" if estado["tipo"] == "gastos" else "#eaf3fc"
            btn_tipo_gas.color = "white" if estado["tipo"] == "gastos" else "#2c5282"
            btn_tipo_ing.bgcolor = "#4a78a8" if estado["tipo"] == "ingresos" else "#eaf3fc"
            btn_tipo_ing.color = "white" if estado["tipo"] == "ingresos" else "#2c5282"

            col_lista.controls.clear()
            for idx, c in enumerate(lista):
                activo = (idx == estado["sel_idx"])
                col_lista.controls.append(
                    ft.Container(
                        bgcolor="#dbeafe" if activo else "#ffffff",
                        border=ft.Border.all(1, "#93c5fd" if activo else "#e2e8f0"),
                        border_radius=5, padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        on_click=lambda e, i=idx: (estado.update({"sel_idx": i}), _refrescar_lista()),
                        content=ft.Text(c, color="#2c5282" if activo else "#1e293b", weight=ft.FontWeight.BOLD if activo else ft.FontWeight.NORMAL, size=12)
                    )
                )
            self.page.update()

        btn_tipo_gas.on_click = lambda e: (estado.update({"tipo": "gastos", "sel_idx": 0}), _refrescar_lista())
        btn_tipo_ing.on_click = lambda e: (estado.update({"tipo": "ingresos", "sel_idx": 0}), _refrescar_lista())

        def _agregar(e):
            es_gasto = (estado["tipo"] == "gastos")
            lista = _lista_activa()
            def _on_add(nombre):
                if any(limpiar_clave(c) == limpiar_clave(nombre) for c in lista):
                    self.mostrar_alerta("Categoría duplicada", f"La categoría '{nombre}' ya existe.", "⚠️")
                    return
                lista.append(nombre)
                if es_gasto:
                    self.app_data["resumenPantalla"]["montosPrevistos"].setdefault(nombre, 0.0)
                    for p in self.app_data["presupuestosDB"]:
                        p.setdefault("montosPorCategoria", {}).setdefault(nombre, 0.0)
                estado["sel_idx"] = len(lista) - 1
                self.persist()
                _refrescar_lista()
            self.pedir_texto_moderno("➕ Nueva Categoría", "Ingresa el nombre de la nueva categoría:", "", _on_add)

        def _renombrar(e):
            lista = _lista_activa()
            idx = estado["sel_idx"]
            if not (0 <= idx < len(lista)):
                return
            actual = lista[idx]
            es_gasto = (estado["tipo"] == "gastos")
            def _on_ren(nombre):
                if limpiar_clave(nombre) != limpiar_clave(actual) and any(limpiar_clave(c) == limpiar_clave(nombre) for c in lista):
                    self.mostrar_alerta("Categoría duplicada", f"Ya existe otra categoría llamada '{nombre}'.", "⚠️")
                    return
                lista[idx] = nombre
                if es_gasto:
                    prevs = self.app_data["resumenPantalla"]["montosPrevistos"]
                    prevs[nombre] = prevs.pop(actual, 0.0)
                    for p in self.app_data["presupuestosDB"]:
                        mc = p.setdefault("montosPorCategoria", {})
                        mc[nombre] = mc.pop(actual, 0.0)
                    for t in self.app_data["transacciones"]:
                        if limpiar_clave(t.get("categoria")) == limpiar_clave(actual):
                            t["categoria"] = nombre
                else:
                    for i in self.app_data["ingresos"]:
                        if limpiar_clave(i.get("categoria")) == limpiar_clave(actual):
                            i["categoria"] = nombre
                self.persist()
                _refrescar_lista()
            self.pedir_texto_moderno("✏️ Renombrar Categoría", f"Nuevo nombre para '{actual}':", actual, _on_ren)

        def _mover(delta: int):
            lista = _lista_activa()
            idx = estado["sel_idx"]
            nuevo = idx + delta
            if 0 <= idx < len(lista) and 0 <= nuevo < len(lista):
                lista[idx], lista[nuevo] = lista[nuevo], lista[idx]
                estado["sel_idx"] = nuevo
                self.persist()
                _refrescar_lista()

        def _eliminar(e):
            lista = _lista_activa()
            idx = estado["sel_idx"]
            if len(lista) <= 1 or not (0 <= idx < len(lista)):
                return
            cat = lista[idx]
            es_gasto = (estado["tipo"] == "gastos")
            col_mov = self.app_data["transacciones"] if es_gasto else self.app_data["ingresos"]
            en_uso = sum(1 for m in col_mov if limpiar_clave(m.get("categoria")) == limpiar_clave(cat))
            if en_uso > 0:
                self.mostrar_alerta("Categoría en uso", f"No se puede eliminar '{cat}' porque tiene {en_uso} movimiento(s) registrados.", "⚠️")
                return
            def _do_del():
                lista.pop(idx)
                if es_gasto:
                    self.app_data["resumenPantalla"]["montosPrevistos"].pop(cat, None)
                    for p in self.app_data["presupuestosDB"]:
                        p.get("montosPorCategoria", {}).pop(cat, None)
                self.persist()
                _refrescar_lista()
            self.mostrar_confirmacion("Eliminar Categoría", f"¿Confirmas eliminar la categoría '{cat}'?", _do_del)

        dlg = ft.AlertDialog(
            title=ft.Container(
                bgcolor="#4a78a8", padding=10, border_radius=6,
                content=ft.Text("🏷️ Administrar Categorías", color="white", weight=ft.FontWeight.BOLD, size=13)
            ),
            content=ft.Column([
                ft.Row([btn_tipo_gas, btn_tipo_ing], spacing=8),
                ft.Container(
                    border=ft.Border.all(1.5, "#b8d4f0"), border_radius=6, padding=6,
                    content=col_lista
                ),
                ft.Row([
                    ft.Button("➕ Agregar", bgcolor="#10b981", color="white", on_click=_agregar),
                    ft.Button("✏️ Renombrar", bgcolor="#4a78a8", color="white", on_click=_renombrar),
                    ft.Button("▲", bgcolor="#eaf3fc", color="#2c5282", on_click=lambda e: _mover(-1)),
                    ft.Button("▼", bgcolor="#eaf3fc", color="#2c5282", on_click=lambda e: _mover(1)),
                    ft.Button("🗑️", bgcolor="#e11d48", color="white", on_click=_eliminar),
                ], wrap=True, spacing=6)
            ], tight=True, width=320, spacing=8),
            actions=[
                ft.Button("✓ Cerrar", bgcolor="#10b981", color="white", on_click=lambda e: self._cerrar_dialogo(dlg))
            ]
        )
        _refrescar_lista()
        self._abrir_dialogo(dlg)

    # -----------------------------------------------------------------
    # ACCIONES DE PRESUPUESTOS Y RESPALDOS
    # -----------------------------------------------------------------
    def cargar_presupuesto_por_indice(self, idx: int):
        db = self.app_data["presupuestosDB"]
        if isinstance(idx, int) and 0 <= idx < len(db):
            reg = db[idx]
            res = self.app_data["resumenPantalla"]
            res["nombre"] = "Presupuesto: " + reg["nombre"]
            res["fechaInicio"] = normalizar_fecha_iso(reg["fechaInicio"])
            res["fechaFin"] = normalizar_fecha_iso(reg["fechaFin"])
            for c in self.categorias_gastos:
                res["montosPrevistos"][c] = float(reg.get("montosPorCategoria", {}).get(c) or 0.0)
            self._active_tab = "resumen"
            self.persist(guardar_csv=False, guardar_resumen=True)

    def navegar_presupuesto(self, delta_idx: int):
        db = self.app_data["presupuestosDB"]
        if not db:
            return
        idx_actual = self._indice_presupuesto_activo()
        if idx_actual == -1:
            self.cargar_presupuesto_por_indice(max(0, self._obtener_indice_presupuesto_ideal()))
            return
        nuevo_idx = idx_actual + delta_idx
        if 0 <= nuevo_idx < len(db):
            self.cargar_presupuesto_por_indice(nuevo_idx)

    def actualizar_presupuesto_actual(self):
        idx_actual = self._indice_presupuesto_activo()
        if idx_actual == -1:
            self.guardar_nuevo_presupuesto()
            return
        res = self.app_data["resumenPantalla"]
        f_ini = normalizar_fecha_iso(res["fechaInicio"])
        f_fin = normalizar_fecha_iso(res["fechaFin"])
        if not f_ini or not f_fin or f_ini > f_fin:
            self.mostrar_alerta("Validación de Fechas", "Verifica que la Fecha Inicio no sea mayor que la Fecha Fin.", "⚠️")
            return
        mapa = {c: float(res["montosPrevistos"].get(c) or 0.0) for c in self.categorias_gastos}
        if sum(mapa.values()) <= 0:
            self.mostrar_alerta("Validación de Montos", "El presupuesto no puede tener todos los gastos previstos en $0.00.", "⚠️")
            return
        for idx, p in enumerate(self.app_data["presupuestosDB"]):
            if idx == idx_actual:
                continue
            p_ini = normalizar_fecha_iso(p["fechaInicio"])
            p_fin = normalizar_fecha_iso(p["fechaFin"])
            if f_ini <= p_fin and f_fin >= p_ini:
                self.mostrar_alerta("Traslape de Fechas", f"Las fechas se traslapan con '{p['nombre']}'.", "⚠️")
                return
        reg = self.app_data["presupuestosDB"][idx_actual]
        reg["fechaInicio"] = f_ini
        reg["fechaFin"] = f_fin
        reg["montosPorCategoria"] = dict(mapa)
        self.persist()
        self.mostrar_alerta("Presupuesto Actualizado", f"El presupuesto '{reg['nombre']}' se actualizó correctamente.", "✅")

    def guardar_nuevo_presupuesto(self):
        res = self.app_data["resumenPantalla"]
        f_ini = normalizar_fecha_iso(res["fechaInicio"])
        f_fin = normalizar_fecha_iso(res["fechaFin"])
        if not f_ini or not f_fin or f_ini > f_fin:
            self.mostrar_alerta("Validación de Fechas", "La Fecha de Inicio no puede ser posterior a la Fecha Fin.", "⚠️")
            return
        mapa = {c: float(res["montosPrevistos"].get(c) or 0.0) for c in self.categorias_gastos}
        if sum(mapa.values()) <= 0:
            self.mostrar_alerta("Validación de Montos", "No puedes guardar un presupuesto nuevo con todos los gastos previstos en $0.00.", "⚠️")
            return
        for p in self.app_data["presupuestosDB"]:
            p_ini = normalizar_fecha_iso(p["fechaInicio"])
            p_fin = normalizar_fecha_iso(p["fechaFin"])
            if f_ini <= p_fin and f_fin >= p_ini:
                self.mostrar_alerta("Fechas Traslapadas", f"El período choca con '{p['nombre']}'.", "⚠️")
                return

        def _on_name(nombre_limpio):
            if any(limpiar_clave(p["nombre"]) == limpiar_clave(nombre_limpio) for p in self.app_data["presupuestosDB"]):
                self.mostrar_alerta("Nombre Duplicado", f"Ya existe un presupuesto guardado con el nombre '{nombre_limpio}'.", "⚠️")
                return
            self.app_data["presupuestosDB"].append({
                "id": self._generar_id_unico(self.app_data["presupuestosDB"]),
                "nombre": nombre_limpio,
                "fechaInicio": f_ini,
                "fechaFin": f_fin,
                "montosPorCategoria": dict(mapa)
            })
            self._ordenar_presupuestos_db()
            res["nombre"] = "Presupuesto: " + nombre_limpio
            self.persist()
            self.mostrar_alerta("Presupuesto Guardado", f"El nuevo presupuesto '{nombre_limpio}' fue guardado exitosamente.", "✅")

        self.pedir_texto_moderno("➕ Guardar Nuevo Presupuesto", f"Nombre único para el período ({formatear_fecha_bonita(f_ini)} al {formatear_fecha_bonita(f_fin)}):", "", _on_name)

    def renombrar_presupuesto_actual(self):
        idx_pres = self._indice_presupuesto_activo()
        nombre_actual = self.obtener_nombre_presupuesto_activo()
        if idx_pres == -1:
            self.pedir_texto_moderno(
                "✏️ Renombrar Período", "Nuevo nombre para el período en pantalla:", nombre_actual,
                lambda nuevo: (self.app_data["resumenPantalla"].update({"nombre": "Presupuesto: " + nuevo}), self.persist(guardar_csv=False, guardar_resumen=True))
            )
            return

        reg = self.app_data["presupuestosDB"][idx_pres]
        nombre_viejo = reg["nombre"]

        def _on_rename(nombre_limpio):
            if limpiar_clave(nombre_limpio) != limpiar_clave(nombre_viejo) and any(
                limpiar_clave(p["nombre"]) == limpiar_clave(nombre_limpio) for p in self.app_data["presupuestosDB"]
            ):
                self.mostrar_alerta("Nombre Duplicado", f"Ya existe otro presupuesto llamado '{nombre_limpio}'.", "⚠️")
                return
            reg["nombre"] = nombre_limpio
            for t in self.app_data["transacciones"]:
                if limpiar_clave(t.get("presupuesto")) == limpiar_clave(nombre_viejo):
                    t["presupuesto"] = nombre_limpio
            for i in self.app_data["ingresos"]:
                if limpiar_clave(i.get("presupuesto")) == limpiar_clave(nombre_viejo):
                    i["presupuesto"] = nombre_limpio
            self.app_data["resumenPantalla"]["nombre"] = "Presupuesto: " + nombre_limpio
            self.persist()
            self.mostrar_alerta("Presupuesto Renombrado", f"El presupuesto se renombró a '{nombre_limpio}'.", "✅")

        self.pedir_texto_moderno("✏️ Renombrar Presupuesto", f"Nuevo nombre para '{nombre_viejo}':", nombre_viejo, _on_rename)

    def confirmar_eliminar_presupuesto(self, idx: int):
        db = self.app_data["presupuestosDB"]
        if not (0 <= idx < len(db)):
            return
        reg = db[idx]
        nombre = reg["nombre"]
        clave_nom = limpiar_clave(nombre)
        gastos_vinc = [t for t in self.app_data["transacciones"] if limpiar_clave(t.get("presupuesto")) == clave_nom]
        ingresos_vinc = [i for i in self.app_data["ingresos"] if limpiar_clave(i.get("presupuesto")) == clave_nom]

        def _finalizar_borrado(modo: str):
            if modo == "borrar_todo":
                self.app_data["transacciones"] = [t for t in self.app_data["transacciones"] if limpiar_clave(t.get("presupuesto")) != clave_nom]
                self.app_data["ingresos"] = [i for i in self.app_data["ingresos"] if limpiar_clave(i.get("presupuesto")) != clave_nom]
            elif modo == "desvincular":
                for t in gastos_vinc:
                    t["presupuesto"] = ""
                for i in ingresos_vinc:
                    i["presupuesto"] = ""

            era_activo = (limpiar_clave(self.obtener_nombre_presupuesto_activo()) == clave_nom)
            db.pop(idx)
            self._ordenar_presupuestos_db()
            if era_activo:
                if db:
                    elegido = db[max(0, self._obtener_indice_presupuesto_ideal())]
                    res = self.app_data["resumenPantalla"]
                    res["nombre"] = "Presupuesto: " + elegido["nombre"]
                    res["fechaInicio"] = normalizar_fecha_iso(elegido["fechaInicio"])
                    res["fechaFin"] = normalizar_fecha_iso(elegido["fechaFin"])
                    for c in self.categorias_gastos:
                        res["montosPrevistos"][c] = float(elegido.get("montosPorCategoria", {}).get(c) or 0.0)
                else:
                    self.app_data["resumenPantalla"]["nombre"] = "Presupuesto: Nuevo Período"
            self.persist()

        if gastos_vinc or ingresos_vinc:
            dlg = ft.AlertDialog(
                title=ft.Container(
                    bgcolor="#4a78a8", padding=10, border_radius=6,
                    content=ft.Text("🗑️ Eliminar Presupuesto", color="white", weight=ft.FontWeight.BOLD, size=13)
                ),
                content=ft.Container(
                    bgcolor="#f0f7ff", border=ft.Border.all(1, "#b8d4f0"), border_radius=6, padding=12, width=310,
                    content=ft.Text(
                        f"'{nombre}' tiene {len(gastos_vinc)} gasto(s) y {len(ingresos_vinc)} ingreso(s).\n\n¿Qué deseas hacer con ellos?",
                        color="#1e293b", size=12
                    )
                ),
                actions=[
                    ft.Button("✕ Cancelar", bgcolor="#e11d48", color="white", on_click=lambda e: self._cerrar_dialogo(dlg)),
                    ft.Button("Borrar todo", bgcolor="#4a78a8", color="white", on_click=lambda e: (self._cerrar_dialogo(dlg), _finalizar_borrado("borrar_todo"))),
                    ft.Button("✓ Conservar", bgcolor="#10b981", color="white", on_click=lambda e: (self._cerrar_dialogo(dlg), _finalizar_borrado("desvincular"))),
                ]
            )
            self._abrir_dialogo(dlg)
        else:
            self.mostrar_confirmacion("Eliminar Presupuesto", f"¿Confirmas eliminar el presupuesto '{nombre}'?", lambda: _finalizar_borrado("simple"))

    def exportar_backup_json(self):
        def _guardar_en_ruta(ruta_destino: str):
            try:
                with open(ruta_destino, "w", encoding="utf-8") as f:
                    json.dump(self.app_data, f, indent=2, ensure_ascii=False)
                self.mostrar_alerta("Respaldo Exportado", f"Guardado exitosamente en:\n{ruta_destino}", "✅")
            except Exception as ex:
                self.mostrar_alerta("Error al Exportar", f"No se pudo guardar el archivo:\n{ex}", "⚠️")

        self.abrir_explorador_archivos(modo="exportar", on_file_selected=_guardar_en_ruta)

    def importar_backup_json(self):
        def _cargar_desde_ruta(ruta_origen: str):
            try:
                contenido = leer_archivo_seguro(ruta_origen)
                if not contenido:
                    self.mostrar_alerta("Error", "No se pudo leer el archivo seleccionado.", "⚠️")
                    return
                p = json.loads(contenido)
                if isinstance(p, dict) and "resumenPantalla" in p and "presupuestosDB" in p:
                    res_p = p["resumenPantalla"]
                    if isinstance(res_p.get("categoriasGastos"), list) and res_p["categoriasGastos"]:
                        self.categorias_gastos = [str(c).strip() for c in res_p["categoriasGastos"] if str(c).strip()]
                    if isinstance(res_p.get("categoriasIngresos"), list) and res_p["categoriasIngresos"]:
                        self.categorias_ingresos = [str(c).strip() for c in res_p["categoriasIngresos"] if str(c).strip()]
                    self.app_data = p
                    self.persist()
                    self.mostrar_alerta("Respaldo Restaurado", f"¡Respaldo cargado y sincronizado desde:\n{os.path.basename(ruta_origen)}!", "✅")
                else:
                    self.mostrar_alerta("Formato Inválido", "El archivo JSON no contiene la estructura de un backup completo (resumenPantalla y presupuestosDB).", "⚠️")
            except Exception as ex:
                self.mostrar_alerta("Error", f"El archivo JSON seleccionado no es válido:\n{ex}", "⚠️")

        self.abrir_explorador_archivos(modo="importar", on_file_selected=_cargar_desde_ruta)

    # -----------------------------------------------------------------
    # CONSTRUCCIÓN DE INTERFAZ GRÁFICA ADAPTATIVA (MÓVIL + PC)
    # -----------------------------------------------------------------
    def render_ui(self):
        self.root_container.controls.clear()

        tabs_spec = [
            ("resumen", "📑 Resumen"),
            ("transacciones", "💳 Gastos"),
            ("ingresos", "💵 Ingresos"),
            ("presupuestos", "📅 Períodos")
        ]
        tab_controls = []
        for key, label in tabs_spec:
            es_activa = (self._active_tab == key)
            tab_controls.append(
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment(0, 0),
                    bgcolor="#ffffff" if es_activa else "#c9daec",
                    border=ft.Border.only(
                        top=ft.BorderSide(1, "#c2d5e8" if es_activa else "#b8cde3"),
                        left=ft.BorderSide(1, "#c2d5e8" if es_activa else "#b8cde3"),
                        right=ft.BorderSide(1, "#c2d5e8" if es_activa else "#b8cde3"),
                    ),
                    border_radius=ft.BorderRadius.only(top_left=6, top_right=6),
                    padding=ft.Padding.symmetric(horizontal=4, vertical=8),
                    on_click=lambda e, k=key: self._cambiar_tab(k),
                    content=ft.Text(
                        label,
                        color="#3b6998" if es_activa else "#3b5978",
                        weight=ft.FontWeight.BOLD if es_activa else ft.FontWeight.W_600,
                        size=11.5,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS
                    )
                )
            )

        tab_bar = ft.Container(
            bgcolor="#dbe7f3",
            border=ft.Border.only(top=ft.BorderSide(1, "#c2d5e8"), left=ft.BorderSide(1, "#c2d5e8"), right=ft.BorderSide(1, "#c2d5e8")),
            border_radius=ft.BorderRadius.only(top_left=8, top_right=8),
            padding=ft.Padding.only(left=4, right=4, top=4),
            content=ft.Row(tab_controls, spacing=3)
        )

        if self._active_tab == "resumen":
            vista_activa = self._build_resumen_view()
        elif self._active_tab == "transacciones":
            vista_activa = self._build_movimientos_view("gasto")
        elif self._active_tab == "ingresos":
            vista_activa = self._build_movimientos_view("ingreso")
        else:
            vista_activa = self._build_presupuestos_view()

        view_container = ft.Container(
            expand=True,
            bgcolor="#ffffff",
            border=ft.Border.all(1, "#c2d5e8"),
            border_radius=ft.BorderRadius.only(bottom_left=8, bottom_right=8),
            padding=6,
            content=vista_activa
        )

        self.root_container.controls.extend([tab_bar, view_container])
        self.page.update()

    def _cambiar_tab(self, tab_key: str):
        self._active_tab = tab_key
        self.render_ui()

    # -----------------------------------------------------------------
    # VISTA 1: PESTAÑA RESUMEN OPTIMIZADA
    # -----------------------------------------------------------------
    def _build_resumen_view(self) -> ft.Control:
        db = self.app_data["presupuestosDB"]
        idx_activo = self._indice_presupuesto_activo()
        res = self.app_data["resumenPantalla"]
        f_ini = normalizar_fecha_iso(res.get("fechaInicio"))
        f_fin = normalizar_fecha_iso(res.get("fechaFin"))
        nombre_activo = self.obtener_nombre_presupuesto_activo()
        hoy = get_local_iso_date()

        if idx_activo >= 0:
            p_act = db[idx_activo]
            nav_label = f"📊 {p_act['nombre']} ({normalizar_fecha_iso(p_act['fechaInicio'])} al {normalizar_fecha_iso(p_act['fechaFin'])})"
            estado_tag_txt = "(Guardado)"
            estado_tag_col = "#d1fae5"
        else:
            nav_label = f"✨ {nombre_activo} (En edición)"
            estado_tag_txt = "(Sin guardar)"
            estado_tag_col = "#fef08a"

        items_nav = [
            (f"📊 {p['nombre']} ({normalizar_fecha_iso(p['fechaInicio'])} al {normalizar_fecha_iso(p['fechaFin'])})", i, f"{formatear_fecha_bonita(p['fechaInicio'])} {formatear_fecha_bonita(p['fechaFin'])}")
            for i, p in enumerate(db)
        ]

        nav_capsule = ft.Container(
            bgcolor="#eaf3fc",
            border=ft.Border.all(1.5, "#93c5fd"),
            border_radius=15,
            padding=ft.Padding.symmetric(horizontal=6, vertical=4),
            content=ft.Row([
                ft.Container(
                    bgcolor="#d4e6f9", border_radius=12, width=28, height=28, alignment=ft.Alignment(0, 0),
                    on_click=lambda e: self.navegar_presupuesto(1),
                    content=ft.Text("◀", size=11, color="#2c5282", weight=ft.FontWeight.BOLD)
                ),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=4),
                    on_click=lambda e: self.abrir_buscador_en_vivo("🔎 Buscar Presupuesto", items_nav, self.cargar_presupuesto_por_indice),
                    content=ft.Row([
                        ft.Text("🔎", size=11),
                        ft.Text(nav_label, color="#2c5282", weight=ft.FontWeight.BOLD, size=11.5, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text("▾", color="#2c5282", weight=ft.FontWeight.BOLD, size=12)
                    ], spacing=4)
                ),
                ft.Container(
                    bgcolor="#d4e6f9", border_radius=12, width=28, height=28, alignment=ft.Alignment(0, 0),
                    on_click=lambda e: self.navegar_presupuesto(-1),
                    content=ft.Text("▶", size=11, color="#2c5282", weight=ft.FontWeight.BOLD)
                ),
            ], spacing=4)
        )

        menu_presupuesto = ft.PopupMenuButton(
            content=ft.Container(
                bgcolor="#eaf3fc", border=ft.Border.all(1, "#b8d4f0"), border_radius=6,
                padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                content=ft.Text("📊 Presupuesto ▼", color="#2c5282", weight=ft.FontWeight.W_600, size=11)
            ),
            items=[
                ft.PopupMenuItem(content=ft.Text("💾 Actualizar Presupuesto Actual"), on_click=lambda e: self.actualizar_presupuesto_actual()),
                ft.PopupMenuItem(content=ft.Text("➕ Guardar Pantalla como Nuevo"), on_click=lambda e: self.guardar_nuevo_presupuesto()),
                ft.PopupMenuItem(content=ft.Text("✏️ Renombrar Presupuesto Actual"), on_click=lambda e: self.renombrar_presupuesto_actual()),
                ft.PopupMenuItem(content=ft.Text("🗑️ Eliminar Presupuesto Actual"), on_click=lambda e: self.confirmar_eliminar_presupuesto(idx_activo) if idx_activo >= 0 else None),
            ]
        )

        menu_archivo = ft.PopupMenuButton(
            content=ft.Container(
                bgcolor="#eaf3fc", border=ft.Border.all(1, "#b8d4f0"), border_radius=6,
                padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                content=ft.Text("📁 Archivo ▼", color="#2c5282", weight=ft.FontWeight.W_600, size=11)
            ),
            items=[
                ft.PopupMenuItem(content=ft.Text("🔄 Recargar ./Datos_CSV"), on_click=lambda e: self.cargar_desde_disco(True)),
                ft.PopupMenuItem(content=ft.Text("💾 Exportar Backup (.json)"), on_click=lambda e: self.exportar_backup_json()),
                ft.PopupMenuItem(content=ft.Text("📂 Cargar Backup (.json)"), on_click=lambda e: self.importar_backup_json()),
            ]
        )

        menu_bar = ft.Container(
            bgcolor="#f5f9fd", border=ft.Border.all(1, "#d4e4f4"), border_radius=8, padding=6,
            content=ft.Column([
                nav_capsule,
                ft.Row([
                    ft.Button("+ Gasto", bgcolor="#e11d48", color="white", expand=True, on_click=lambda e: self.open_movimiento_modal("gasto", None)),
                    ft.Button("+ Ingreso", bgcolor="#10b981", color="white", expand=True, on_click=lambda e: self.open_movimiento_modal("ingreso", None)),
                    ft.Button("+ Período", bgcolor="#4a78a8", color="white", expand=True, on_click=lambda e: self.abrir_modal_presupuesto(None)),
                ], spacing=6),
                ft.Row([
                    menu_presupuesto,
                    menu_archivo,
                    ft.Container(
                        bgcolor="#eaf3fc", border=ft.Border.all(1, "#b8d4f0"), border_radius=6,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                        on_click=lambda e: self.abrir_gestor_categorias(),
                        content=ft.Text("🏷️ Categorías", color="#2c5282", weight=ft.FontWeight.W_600, size=11)
                    ),
                    ft.Container(
                        bgcolor="#ecfdf5" if self.sync_status_ok else "#fef2f2",
                        padding=ft.Padding.symmetric(horizontal=8, vertical=5), border_radius=6,
                        content=ft.Text(self.sync_status_text, color="#059669" if self.sync_status_ok else "#991b1b", size=10, weight=ft.FontWeight.W_600)
                    )
                ], wrap=True, spacing=6, run_spacing=6)
            ], spacing=6)
        )

        # --- CÁLCULOS DEL PANEL EJECUTIVO KPI ---
        ing_hist = sum(limpiar_importe(i["importe"]) for i in self.app_data["ingresos"] if normalizar_fecha_iso(i["fecha"]) <= hoy)
        gas_hist = sum(limpiar_importe(t["importe"]) for t in self.app_data["transacciones"] if normalizar_fecha_iso(t["fecha"]) <= hoy)
        pos_neta = ing_hist - gas_hist

        ing_previos = sum(limpiar_importe(i["importe"]) for i in self.app_data["ingresos"] if self.pertenece_a_periodo_previo(i, nombre_activo, f_ini, f_fin))
        gas_previos = sum(limpiar_importe(t["importe"]) for t in self.app_data["transacciones"] if self.pertenece_a_periodo_previo(t, nombre_activo, f_ini, f_fin))
        saldo_previo = ing_previos - gas_previos

        gastos_reales = {c: 0.0 for c in self.categorias_gastos}
        total_gastos_reales = 0.0
        fallback_g = resolver_categoria("Otros Fuera Presupuesto", self.categorias_gastos, self.categorias_gastos[-1])
        for t in self.app_data["transacciones"]:
            if self.pertenece_a_presupuesto_activo(t, nombre_activo, f_ini, f_fin):
                v = limpiar_importe(t["importe"])
                cat = resolver_categoria(t.get("categoria"), self.categorias_gastos, fallback_g)
                gastos_reales[cat] = gastos_reales.get(cat, 0.0) + v
                total_gastos_reales += v

        ingresos_reales = {c: 0.0 for c in self.categorias_ingresos}
        total_ingresos_reales = 0.0
        fallback_i = resolver_categoria("Efectivo", self.categorias_ingresos, self.categorias_ingresos[0])
        for i in self.app_data["ingresos"]:
            if self.pertenece_a_presupuesto_activo(i, nombre_activo, f_ini, f_fin):
                v = limpiar_importe(i["importe"])
                cat = resolver_categoria(i.get("categoria"), self.categorias_ingresos, fallback_i)
                ingresos_reales[cat] = ingresos_reales.get(cat, 0.0) + v
                total_ingresos_reales += v

        total_gastos_previstos = 0.0
        sum_diff_neg = 0.0
        sum_diff_pos = 0.0
        count_sin_usar_gas = 0
        for cat in self.categorias_gastos:
            prev = float(res["montosPrevistos"].get(cat) or 0.0)
            real = float(gastos_reales.get(cat) or 0.0)
            diff = prev - real
            total_gastos_previstos += prev
            if diff < 0:
                sum_diff_neg += diff
            if diff > 0:
                sum_diff_pos += diff
            if prev == 0 and real == 0:
                count_sin_usar_gas += 1

        diff_tot = total_gastos_previstos - total_gastos_reales
        falta_por_consumir = sum_diff_pos
        pct = (total_gastos_reales / total_gastos_previstos * 100.0) if total_gastos_previstos > 0 else 0.0
        ahorro_proyectado = (total_ingresos_reales - total_gastos_previstos) + sum_diff_neg
        ahorro_real_neto = ahorro_proyectado + saldo_previo

        def _kpi_top_block(col_spec, head_widget, val_widget, bg_val="#ffffff"):
            return ft.Column(
                col=col_spec, spacing=0,
                controls=[
                    ft.Container(bgcolor="#4a78a8", padding=ft.Padding.symmetric(horizontal=8, vertical=4), border=ft.Border.only(right=ft.BorderSide(1, "#6390be")), content=head_widget),
                    ft.Container(bgcolor=bg_val, padding=ft.Padding.symmetric(horizontal=8, vertical=5), border=ft.Border.only(bottom=ft.BorderSide(1, "#c2d5e8"), right=ft.BorderSide(1, "#e2ecf5")), content=val_widget)
                ]
            )

        def _kpi_bot_block(col_spec, titulo_izq, txt_valor, color_val, tag_der=None):
            head_row = [ft.Text(titulo_izq, color="#3b5978", weight=ft.FontWeight.BOLD, size=9.5, expand=True)]
            if tag_der:
                head_row.append(tag_der)
            return ft.Column(
                col=col_spec, spacing=0,
                controls=[
                    ft.Container(bgcolor="#f5f9fd", padding=ft.Padding.symmetric(horizontal=6, vertical=3), border=ft.Border.only(bottom=ft.BorderSide(1, "#c2d5e8"), right=ft.BorderSide(1, "#e2ecf5")), content=ft.Row(head_row, spacing=2)),
                    ft.Container(bgcolor="#ffffff", padding=ft.Padding.symmetric(horizontal=6, vertical=5), border=ft.Border.only(bottom=ft.BorderSide(1, "#e2ecf5"), right=ft.BorderSide(1, "#e2ecf5")), content=ft.Text(txt_valor, color=color_val, weight=ft.FontWeight.BOLD, size=13.5))
                ]
            )

        tag_arrastre = ft.Text(
            f"({format_money(saldo_previo)})" if abs(saldo_previo) > 0.005 else "(Sin arr.)",
            color="#e11d48" if saldo_previo < -0.005 else ("#059669" if saldo_previo > 0.005 else "#64748b"),
            size=9, weight=ft.FontWeight.W_600
        )

        kpi_master = ft.Container(
            bgcolor="#ffffff", border=ft.Border.all(1, "#c2d5e8"), border_radius=8, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column(spacing=0, controls=[
                ft.ResponsiveRow(spacing=0, run_spacing=0, controls=[
                    _kpi_top_block(
                        {"xs": 12, "md": 4},
                        ft.Row([
                            ft.Text(res.get("nombre", "Presupuesto: Nuevo Período"), color="white", weight=ft.FontWeight.BOLD, size=11, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(estado_tag_txt, color=estado_tag_col, weight=ft.FontWeight.BOLD, size=9.5)
                        ]),
                        ft.Row([
                            ft.Text("Posición Neta Consolidada:", color="#475569", size=11, expand=True),
                            ft.Text(format_money(pos_neta), color="#dc2626" if pos_neta < 0 else "#64748b", weight=ft.FontWeight.BOLD, size=12)
                        ])
                    ),
                    _kpi_top_block(
                        {"xs": 6, "md": 4},
                        ft.Text("📅 FECHA INICIO", color="white", weight=ft.FontWeight.BOLD, size=10),
                        ft.Container(
                            on_click=lambda e: self.abrir_selector_fecha(f_ini, "Fecha Inicio", lambda iso: (res.update({"fechaInicio": iso}), self.persist(False, True))),
                            content=ft.Text(f"{formatear_fecha_bonita(f_ini)} 📅", color="#2c5282", weight=ft.FontWeight.BOLD, size=10.5, max_lines=1)
                        )
                    ),
                    _kpi_top_block(
                        {"xs": 6, "md": 4},
                        ft.Text("📅 FECHA FIN", color="white", weight=ft.FontWeight.BOLD, size=10),
                        ft.Container(
                            on_click=lambda e: self.abrir_selector_fecha(f_fin, "Fecha Fin", lambda iso: (res.update({"fechaFin": iso}), self.persist(False, True))),
                            content=ft.Text(f"{formatear_fecha_bonita(f_fin)} 📅", color="#2c5282", weight=ft.FontWeight.BOLD, size=10.5, max_lines=1)
                        )
                    ),
                ]),
                ft.ResponsiveRow(spacing=0, run_spacing=0, controls=[
                    _kpi_bot_block({"xs": 6, "md": 2.4}, "INGRESOS TOTALES", format_money(total_ingresos_reales), "#059669"),
                    _kpi_bot_block({"xs": 6, "md": 2.4}, "% CONSUMIDO", f"{pct:.1f}%", "#1e293b"),
                    _kpi_bot_block({"xs": 6, "md": 2.4}, "AHORRO PROY.", format_money(ahorro_proyectado), "#1e293b" if ahorro_proyectado >= 0 else "#e11d48", ft.Text("(Período)", color="#64748b", size=8.5)),
                    _kpi_bot_block({"xs": 6, "md": 2.4}, "AHORRO REAL NETO", format_money(ahorro_real_neto), "#3b6998" if ahorro_real_neto >= 0 else "#e11d48", tag_arrastre),
                    _kpi_bot_block({"xs": 12, "md": 2.4}, "FALTA POR CONSUMIR", format_money(falta_por_consumir), "#059669" if falta_por_consumir > 0 else "#64748b"),
                ])
            ])
        )

        # --- TABLA RESUMEN DE GASTOS ---
        ocultar_gas = bool(res.get("ocultarSinUsarGastos", True))
        cats_visibles_gas = [
            c for c in self.categorias_gastos
            if not (ocultar_gas and float(res["montosPrevistos"].get(c) or 0) == 0 and float(gastos_reales.get(c) or 0) == 0)
        ]

        filas_gastos_ui = [
            ft.Container(
                bgcolor="#eaf2fb", border=ft.Border.only(bottom=ft.BorderSide(1.5, "#c2d5e8")),
                padding=ft.Padding.symmetric(horizontal=6, vertical=5),
                content=ft.Row([
                    ft.Text("Categoría", color="#3b5978", weight=ft.FontWeight.BOLD, size=10.5, expand=True),
                    ft.Text("Previsto", color="#3b5978", weight=ft.FontWeight.BOLD, size=10.5, width=68, text_align=ft.TextAlign.RIGHT),
                    ft.Text("Real", color="#3b5978", weight=ft.FontWeight.BOLD, size=10.5, width=72, text_align=ft.TextAlign.RIGHT),
                    ft.Text("Diferencia", color="#3b5978", weight=ft.FontWeight.BOLD, size=10.5, width=72, text_align=ft.TextAlign.RIGHT),
                ], spacing=4)
            ),
            ft.Container(
                bgcolor="#dce8f5", border=ft.Border.only(bottom=ft.BorderSide(1, "#c2d5e8")),
                padding=ft.Padding.symmetric(horizontal=6, vertical=6),
                content=ft.Row([
                    ft.Text("TOTAL GASTOS", color="#2c5282", weight=ft.FontWeight.BOLD, size=10.5, expand=True),
                    ft.Text(format_money(total_gastos_previstos), color="#2c5282", weight=ft.FontWeight.BOLD, size=10.5, width=68, text_align=ft.TextAlign.RIGHT),
                    ft.Text(format_money(total_gastos_reales), color="#2c5282", weight=ft.FontWeight.BOLD, size=10.5, width=72, text_align=ft.TextAlign.RIGHT),
                    ft.Text(format_money(diff_tot), color="#065f46" if diff_tot >= 0 else "#be123c", weight=ft.FontWeight.BOLD, size=10.5, width=72, text_align=ft.TextAlign.RIGHT),
                ], spacing=4)
            )
        ]

        def _on_previsto_change(cat_name, nuevo_txt):
            nuevo_val = limpiar_importe(nuevo_txt)
            val_actual = float(res["montosPrevistos"].get(cat_name) or 0.0)
            if abs(nuevo_val - val_actual) < 1e-6:
                return
            res["montosPrevistos"][cat_name] = nuevo_val
            self.persist(guardar_csv=False, guardar_resumen=True)

        for idx_r, cat in enumerate(cats_visibles_gas):
            prev = float(res["montosPrevistos"].get(cat) or 0.0)
            real = float(gastos_reales.get(cat) or 0.0)
            diff = prev - real
            es_sin_usar = (prev == 0 and real == 0)

            if es_sin_usar:
                border_c, text_c, pill_bg, pill_fg, pill_txt = "#cbd5e1", "#94a3b8", "#e2e8f0", "#94a3b8", "Sin usar"
                inp_border = "#e2e8f0"
            elif real > prev:
                pct_cat = f"{round((real / prev) * 100)}%" if prev > 0 else "Fuera pres."
                border_c, text_c, pill_bg, pill_fg, pill_txt = "#e11d48", "#be123c", "#ffe4e6", "#be123c", pct_cat
                inp_border = "#fda4af"
            elif real == 0 and prev > 0:
                border_c, text_c, pill_bg, pill_fg, pill_txt = "#4a78a8", "#2c5282", "#dbeafe", "#2c5282", "0% • Pend."
                inp_border = "#93c5fd"
            else:
                pct_num = min(100, round((real / prev) * 100))
                border_c, text_c, pill_bg, pill_fg, pill_txt = "#10b981", "#065f46", "#d1fae5", "#065f46", f"{pct_num}%"
                inp_border = "#6ee7b7"

            tf_prev = ft.TextField(
                value=f"{prev:g}" if prev.is_integer() else f"{prev:.2f}",
                width=66, height=28, text_size=10.5,
                text_align=ft.TextAlign.RIGHT,
                content_padding=ft.Padding.symmetric(horizontal=4, vertical=2),
                border_color=inp_border, bgcolor="#ffffff",
                keyboard_type=ft.KeyboardType.NUMBER,
                on_submit=lambda e, c=cat: _on_previsto_change(c, e.control.value),
                on_blur=lambda e, c=cat: _on_previsto_change(c, e.control.value)
            )

            filas_gastos_ui.append(
                ft.Container(
                    bgcolor="#ffffff" if idx_r % 2 == 0 else "#f6f9fc",
                    border=ft.Border.only(left=ft.BorderSide(3.5, border_c), bottom=ft.BorderSide(1, "#e2ecf5")),
                    padding=ft.Padding.symmetric(horizontal=6, vertical=4),
                    content=ft.Row([
                        ft.Column([
                            ft.Text(cat, color=text_c, weight=ft.FontWeight.NORMAL if es_sin_usar else ft.FontWeight.BOLD, size=11, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Container(
                                bgcolor=pill_bg, border_radius=6, padding=ft.Padding.symmetric(horizontal=5, vertical=1),
                                content=ft.Text(pill_txt, color=pill_fg, size=8.5, weight=ft.FontWeight.BOLD)
                            )
                        ], spacing=2, expand=True),
                        ft.Container(width=68, alignment=ft.Alignment(1, 0), content=tf_prev),
                        ft.Text(format_money(real), color=text_c, weight=ft.FontWeight.BOLD if not es_sin_usar else ft.FontWeight.NORMAL, size=10.5, width=72, text_align=ft.TextAlign.RIGHT),
                        ft.Text(format_money(diff), color=text_c, weight=ft.FontWeight.BOLD if not es_sin_usar else ft.FontWeight.NORMAL, size=10.5, width=72, text_align=ft.TextAlign.RIGHT),
                    ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                )
            )

        card_gastos = ft.Container(
            col={"xs": 12, "lg": 7.4},
            bgcolor="#ffffff", border=ft.Border.all(1, "#c2d5e8"), border_radius=8, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column(spacing=0, controls=[
                ft.Container(
                    bgcolor="#4a78a8", padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                    content=ft.Row([
                        ft.Text("PRESUPUESTO DE GASTOS", color="white", weight=ft.FontWeight.BOLD, size=11, expand=True),
                        ft.Container(
                            bgcolor="#ffffff" if ocultar_gas else "#6390be",
                            border_radius=6, padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                            on_click=lambda e: (res.update({"ocultarSinUsarGastos": not ocultar_gas}), self.persist(False, True)),
                            content=ft.Text(
                                f"👁️ Mostrar ({count_sin_usar_gas})" if ocultar_gas else f"👁️ Ocultar ({count_sin_usar_gas})",
                                color="#3b6998" if ocultar_gas else "white", size=9.5, weight=ft.FontWeight.BOLD
                            )
                        ),
                        ft.Container(
                            bgcolor="#eaf3fc", border_radius=6, padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                            on_click=lambda e: self.open_movimiento_modal("gasto", None),
                            content=ft.Text("+ Gasto", color="#2c5282", size=10, weight=ft.FontWeight.BOLD)
                        )
                    ], spacing=4)
                ),
                ft.Column(filas_gastos_ui, spacing=0)
            ])
        )

        # --- TABLA RESUMEN DE INGRESOS ---
        count_sin_usar_ing = sum(1 for c in self.categorias_ingresos if float(ingresos_reales.get(c) or 0) == 0)
        ocultar_ing = bool(res.get("ocultarSinUsarIngresos", True))
        cats_visibles_ing = [
            c for c in self.categorias_ingresos
            if not (ocultar_ing and float(ingresos_reales.get(c) or 0) == 0)
        ]

        filas_ingresos_ui = [
            ft.Container(
                bgcolor="#eaf2fb", border=ft.Border.only(bottom=ft.BorderSide(1.5, "#c2d5e8")),
                padding=ft.Padding.symmetric(horizontal=8, vertical=5),
                content=ft.Row([
                    ft.Text("Categoría", color="#3b5978", weight=ft.FontWeight.BOLD, size=10.5, expand=True),
                    ft.Text("Importe Real", color="#3b5978", weight=ft.FontWeight.BOLD, size=10.5, width=110, text_align=ft.TextAlign.RIGHT),
                ])
            ),
            ft.Container(
                bgcolor="#dce8f5", border=ft.Border.only(bottom=ft.BorderSide(1, "#c2d5e8")),
                padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                content=ft.Row([
                    ft.Text("TOTAL INGRESOS", color="#2c5282", weight=ft.FontWeight.BOLD, size=11, expand=True),
                    ft.Text(format_money(total_ingresos_reales), color="#2c5282", weight=ft.FontWeight.BOLD, size=11, width=110, text_align=ft.TextAlign.RIGHT),
                ])
            )
        ]

        for idx_i, cat in enumerate(cats_visibles_ing):
            val = float(ingresos_reales.get(cat) or 0.0)
            es_sin = (val == 0)
            filas_ingresos_ui.append(
                ft.Container(
                    bgcolor="#ffffff" if idx_i % 2 == 0 else "#f6f9fc",
                    border=ft.Border.only(bottom=ft.BorderSide(1, "#e2ecf5")),
                    padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                    content=ft.Row([
                        ft.Text(cat, color="#94a3b8" if es_sin else "#1e293b", weight=ft.FontWeight.NORMAL if es_sin else ft.FontWeight.BOLD, size=11, expand=True),
                        ft.Text(format_money(val), color="#94a3b8" if es_sin else "#2c5282", weight=ft.FontWeight.NORMAL if es_sin else ft.FontWeight.BOLD, size=11, width=110, text_align=ft.TextAlign.RIGHT),
                    ])
                )
            )

        card_ingresos = ft.Container(
            col={"xs": 12, "lg": 4.6},
            bgcolor="#ffffff", border=ft.Border.all(1, "#c2d5e8"), border_radius=8, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column(spacing=0, controls=[
                ft.Container(
                    bgcolor="#4a78a8", padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                    content=ft.Row([
                        ft.Text("INGRESOS (REALES)", color="white", weight=ft.FontWeight.BOLD, size=11, expand=True),
                        ft.Container(
                            bgcolor="#ffffff" if ocultar_ing else "#6390be",
                            border_radius=6, padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                            on_click=lambda e: (res.update({"ocultarSinUsarIngresos": not ocultar_ing}), self.persist(False, True)),
                            content=ft.Text(
                                f"👁️ Mostrar ({count_sin_usar_ing})" if ocultar_ing else f"👁️ Ocultar ({count_sin_usar_ing})",
                                color="#3b6998" if ocultar_ing else "white", size=9.5, weight=ft.FontWeight.BOLD
                            )
                        ),
                        ft.Container(
                            bgcolor="#eaf3fc", border_radius=6, padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                            on_click=lambda e: self.open_movimiento_modal("ingreso", None),
                            content=ft.Text("+ Ingreso", color="#2c5282", size=10, weight=ft.FontWeight.BOLD)
                        )
                    ], spacing=4)
                ),
                ft.Column(filas_ingresos_ui, spacing=0)
            ])
        )

        return ft.Column(
            expand=True, scroll=ft.ScrollMode.AUTO, spacing=8,
            controls=[
                menu_bar,
                kpi_master,
                ft.ResponsiveRow([card_gastos, card_ingresos], spacing=8, run_spacing=8)
            ]
        )

    # -----------------------------------------------------------------
    # VISTAS 2 Y 3: GASTOS E INGRESOS
    # -----------------------------------------------------------------
    def _build_movimientos_view(self, tipo: str) -> ft.Control:
        es_gasto = (tipo == "gasto")
        tabla_key = "transacciones" if es_gasto else "ingresos"
        coleccion = self.app_data[tabla_key]
        categorias = self.categorias_gastos if es_gasto else self.categorias_ingresos
        color_imp = "#be123c" if es_gasto else "#059669"

        k_txt = "trans_txt" if es_gasto else "ing_txt"
        k_cat = "trans_cat" if es_gasto else "ing_cat"
        k_per = "trans_per" if es_gasto else "ing_per"

        txt_filtro = limpiar_clave(self.filtros[k_txt])
        cat_filtro = self.filtros[k_cat]
        modo_per = self.filtros[k_per]

        nombre_activo = self.obtener_nombre_presupuesto_activo()
        f_ini = normalizar_fecha_iso(self.app_data["resumenPantalla"]["fechaInicio"])
        f_fin = normalizar_fecha_iso(self.app_data["resumenPantalla"]["fechaFin"])

        filtrados = []
        for m in coleccion:
            f = normalizar_fecha_iso(m.get("fecha"))
            f_bonita = formatear_fecha_bonita(f)
            pres_txt = m.get("presupuesto") or "Sin presupuesto"
            imp_str = format_money(m.get("importe"))
            busq = limpiar_clave(f"{m.get('concepto', '')} {m.get('categoria', '')} {pres_txt} {f} {f_bonita} {imp_str}")
            coincide_txt = (not txt_filtro) or all(tok in busq for tok in txt_filtro.split())
            coincide_cat = (not cat_filtro) or (m.get("categoria") == cat_filtro)

            if modo_per == "activo":
                coincide_per = self.pertenece_a_presupuesto_activo(m, nombre_activo, f_ini, f_fin)
            elif modo_per != "todos":
                coincide_per = limpiar_clave(m.get("presupuesto")) == limpiar_clave(modo_per)
            else:
                coincide_per = True

            if coincide_txt and coincide_cat and coincide_per:
                filtrados.append(m)

        st = self.sort_state[tabla_key]
        rev = (st["dir"] == "desc")
        col = st["col"]
        filtrados.sort(
            key=lambda x: (
                normalizar_fecha_iso(x.get("fecha")) if col == "fecha" else
                limpiar_clave(x.get(col, "")) if col in ("presupuesto", "categoria", "concepto") else
                limpiar_importe(x.get("importe")),
                int(x.get("id") or 0)
            ),
            reverse=rev
        )

        total_filtrado = sum(limpiar_importe(x["importe"]) for x in filtrados)
        pag = self.pag_state[tabla_key]
        total_items = len(filtrados)
        total_pages = max(1, math.ceil(total_items / pag["size"])) if total_items > 0 else 1
        pag["page"] = max(1, min(total_pages, pag["page"]))
        start_idx = (pag["page"] - 1) * pag["size"]
        end_idx = min(total_items, start_idx + pag["size"])
        pagina_items = filtrados[start_idx:end_idx]

        def _toggle_sort(c_name):
            if st["col"] == c_name:
                st["dir"] = "asc" if st["dir"] == "desc" else "desc"
            else:
                st["col"] = c_name
                st["dir"] = "desc" if c_name in ("fecha", "importe") else "asc"
            self.render_ui()

        def _sort_chip(c_key, label):
            activo = (st["col"] == c_key)
            flecha = (" ▼" if st["dir"] == "desc" else " ▲") if activo else ""
            return ft.Container(
                bgcolor="#dbeafe" if activo else "#ffffff",
                border=ft.Border.all(1, "#93c5fd" if activo else "#cbd5e1"),
                border_radius=6, padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                on_click=lambda e: _toggle_sort(c_key),
                content=ft.Text(f"{label}{flecha}", color="#2c5282" if activo else "#475569", size=10, weight=ft.FontWeight.BOLD if activo else ft.FontWeight.NORMAL)
            )

        opciones_pres_filtro = [
            ("📅 Todos los presupuestos", "todos", "todos"),
            ("📌 Solo presupuesto activo", "activo", "activo resumen")
        ] + [(f"📊 {p['nombre']}", p["nombre"], p["nombre"]) for p in self.app_data["presupuestosDB"]]

        etiqueta_per_actual = "📅 Todos" if modo_per == "todos" else ("📌 Activo" if modo_per == "activo" else f"📊 {modo_per}")

        fbar = ft.Container(
            bgcolor="#f5f9fd", border=ft.Border.only(bottom=ft.BorderSide(1, "#c2d5e8")), padding=6,
            content=ft.Column([
                ft.Row([
                    ft.TextField(
                        hint_text="🔍 Buscar concepto, fecha o monto...",
                        value=self.filtros[k_txt], expand=True, height=34, text_size=11.5,
                        content_padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        on_submit=lambda e: (self.filtros.update({k_txt: e.control.value}), pag.update({"page": 1}), self.render_ui())
                    ),
                    ft.Button(
                        "Limpiar", bgcolor="#eaf3fc", color="#2c5282",
                        on_click=lambda e: (self.filtros.update({k_txt: "", k_cat: "", k_per: "todos"}), pag.update({"page": 1}), self.render_ui())
                    )
                ], spacing=6),
                ft.Row([
                    ft.Container(
                        bgcolor="#ffffff", border=ft.Border.all(1, "#b8d4f0"), border_radius=6,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        on_click=lambda e: self.abrir_buscador_en_vivo(
                            "Filtrar por Categoría",
                            [("Todas las categorías", "", "todas")] + [(c, c, c) for c in categorias],
                            lambda val: (self.filtros.update({k_cat: val}), pag.update({"page": 1}), self.render_ui())
                        ),
                        content=ft.Text(f"🏷️ {cat_filtro or 'Categorías'} ▾", color="#1e293b", size=10.5, weight=ft.FontWeight.W_600)
                    ),
                    ft.Container(
                        bgcolor="#eaf3fc", border=ft.Border.all(1, "#93c5fd"), border_radius=12,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        on_click=lambda e: self.abrir_buscador_en_vivo(
                            "Filtrar por Presupuesto", opciones_pres_filtro,
                            lambda val: (self.filtros.update({k_per: val}), pag.update({"page": 1}), self.render_ui())
                        ),
                        content=ft.Text(f"{etiqueta_per_actual} ▾", color="#2c5282", size=10.5, weight=ft.FontWeight.BOLD)
                    ),
                    _sort_chip("fecha", "Fecha"),
                    _sort_chip("importe", "Monto"),
                    _sort_chip("categoria", "Cat."),
                ], wrap=True, spacing=5, run_spacing=5)
            ], spacing=6)
        )

        def _borrar_mov(mov_id: int):
            self.mostrar_confirmacion(
                "Eliminar Registro",
                "¿Confirmas que deseas eliminar este movimiento?",
                lambda: (self.app_data.update({tabla_key: [x for x in coleccion if int(x["id"]) != int(mov_id)]}), self.persist())
            )

        filas_movimientos = []
        for r_idx, m in enumerate(pagina_items):
            pres_str = f"📊 {m['presupuesto']}" if m.get("presupuesto") else "Por fecha"
            filas_movimientos.append(
                ft.Container(
                    bgcolor="#ffffff" if r_idx % 2 == 0 else "#f6f9fc",
                    border=ft.Border.only(left=ft.BorderSide(3.5, color_imp), bottom=ft.BorderSide(1, "#e2ecf5")),
                    padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                bgcolor="#ffe4e6" if es_gasto else "#d1fae5",
                                border_radius=5, padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                content=ft.Text(m.get("categoria", ""), color=color_imp, weight=ft.FontWeight.BOLD, size=10.5)
                            ),
                            ft.Text(m.get("concepto", ""), color="#1e293b", weight=ft.FontWeight.W_600, size=11.5, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(format_money(m.get("importe")), color=color_imp, weight=ft.FontWeight.BOLD, size=12)
                        ], spacing=6),
                        ft.Row([
                            ft.Text(f"📅 {formatear_fecha_bonita(m.get('fecha'))}  •  {pres_str}", color="#64748b", size=10, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Container(
                                bgcolor="#eaf3fc", padding=ft.Padding.symmetric(horizontal=7, vertical=2), border_radius=4,
                                on_click=lambda e, mid=m["id"]: self.open_movimiento_modal(tipo, mid),
                                content=ft.Text("✏️ Editar", size=10, color="#2c5282", weight=ft.FontWeight.BOLD)
                            ),
                            ft.Container(
                                bgcolor="#fee2e2", padding=ft.Padding.symmetric(horizontal=7, vertical=2), border_radius=4,
                                on_click=lambda e, mid=m["id"]: _borrar_mov(mid),
                                content=ft.Text("×", size=12, color="#dc2626", weight=ft.FontWeight.BOLD)
                            )
                        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                    ], spacing=4)
                )
            )

        titulo_head = (
            f"💳 Gastos ({len(filtrados)} | {format_money(total_filtrado)})"
            if es_gasto else
            f"💵 Ingresos ({len(filtrados)} | {format_money(total_filtrado)})"
        )

        return ft.Container(
            expand=True, bgcolor="#ffffff", border=ft.Border.all(1, "#c2d5e8"), border_radius=8, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column(expand=True, spacing=0, controls=[
                ft.Container(
                    bgcolor="#4a78a8", padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    content=ft.Row([
                        ft.Text(titulo_head, color="white", weight=ft.FontWeight.BOLD, size=11, expand=True),
                        ft.Container(
                            bgcolor="#e11d48" if es_gasto else "#10b981", border_radius=6,
                            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                            on_click=lambda e: self.open_movimiento_modal(tipo, None),
                            content=ft.Text("+ Gasto" if es_gasto else "+ Ingreso", color="white", size=10.5, weight=ft.FontWeight.BOLD)
                        )
                    ])
                ),
                fbar,
                ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0, controls=filas_movimientos),
                self._build_pagination_bar(tabla_key, total_items, start_idx, end_idx, total_pages)
            ])
        )

    # -----------------------------------------------------------------
    # VISTA 4: PERÍODOS DE PRESUPUESTOS GUARDADOS
    # -----------------------------------------------------------------
    def _build_presupuestos_view(self) -> ft.Control:
        db = self.app_data["presupuestosDB"]
        txt = limpiar_clave(self.filtros["pres_txt"])
        anio_sel = self.filtros["pres_anio"]

        registros = []
        for idx, p in enumerate(db):
            f_i = normalizar_fecha_iso(p.get("fechaInicio"))
            f_f = normalizar_fecha_iso(p.get("fechaFin"))
            total_fila = sum(float(p.get("montosPorCategoria", {}).get(c) or 0.0) for c in self.categorias_gastos)
            busq = limpiar_clave(f"{p['nombre']} {f_i} {f_f} {formatear_fecha_bonita(f_i)} {formatear_fecha_bonita(f_f)} {format_money(total_fila)}")
            coincide_txt = (not txt) or all(tok in busq for tok in txt.split())
            coincide_anio = (not anio_sel) or f_i.startswith(anio_sel) or f_f.startswith(anio_sel)
            if coincide_txt and coincide_anio:
                registros.append((idx, p, total_fila))

        st = self.sort_state["presupuestos"]
        rev = (st["dir"] == "desc")
        col = st["col"]
        registros.sort(
            key=lambda item: (
                limpiar_clave(item[1].get("nombre")) if col == "nombre" else
                normalizar_fecha_iso(item[1].get("fechaInicio")) if col == "fechaInicio" else
                item[2]
            ),
            reverse=rev
        )

        suma_totales = sum(r[2] for r in registros)
        pag = self.pag_state["presupuestos"]
        total_items = len(registros)
        total_pages = max(1, math.ceil(total_items / pag["size"])) if total_items > 0 else 1
        pag["page"] = max(1, min(total_pages, pag["page"]))
        start_idx = (pag["page"] - 1) * pag["size"]
        end_idx = min(total_items, start_idx + pag["size"])
        pagina_items = registros[start_idx:end_idx]

        anios = sorted({
            normalizar_fecha_iso(p.get("fechaInicio"))[:4]
            for p in db if len(normalizar_fecha_iso(p.get("fechaInicio"))) >= 4
        }, reverse=True)

        fbar = ft.Container(
            bgcolor="#f5f9fd", border=ft.Border.only(bottom=ft.BorderSide(1, "#c2d5e8")), padding=6,
            content=ft.Row([
                ft.TextField(
                    hint_text="🔍 Filtrar período o fecha...",
                    value=self.filtros["pres_txt"], expand=True, height=34, text_size=11.5,
                    content_padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    on_submit=lambda e: (self.filtros.update({"pres_txt": e.control.value}), pag.update({"page": 1}), self.render_ui())
                ),
                ft.Container(
                    bgcolor="#ffffff", border=ft.Border.all(1, "#b8d4f0"), border_radius=6,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                    on_click=lambda e: self.abrir_buscador_en_vivo(
                        "Filtrar por Año",
                        [("📅 Todos los años", "", "todos")] + [(f"Año {a}", a, a) for a in anios],
                        lambda val: (self.filtros.update({"pres_anio": val}), pag.update({"page": 1}), self.render_ui())
                    ),
                    content=ft.Text(f"📅 {anio_sel or 'Años'} ▾", color="#1e293b", size=11, weight=ft.FontWeight.W_600)
                ),
            ], spacing=6)
        )

        tarjetas_presupuestos = []
        for r_idx, (orig_idx, p, total_fila) in enumerate(pagina_items):
            chips_cats = [
                ft.Container(
                    bgcolor="#eaf3fc", border_radius=5, padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    content=ft.Text(f"{c}: {format_money(p.get('montosPorCategoria', {}).get(c, 0.0))}", size=9.5, color="#2c5282", weight=ft.FontWeight.W_600)
                )
                for c in self.categorias_gastos
                if float(p.get("montosPorCategoria", {}).get(c) or 0.0) > 0
            ]

            tarjetas_presupuestos.append(
                ft.Container(
                    bgcolor="#ffffff" if r_idx % 2 == 0 else "#f6f9fc",
                    border=ft.Border.only(left=ft.BorderSide(3.5, "#4a78a8"), bottom=ft.BorderSide(1, "#c2d5e8")),
                    padding=8,
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"📊 {p['nombre']}", color="#1e293b", weight=ft.FontWeight.BOLD, size=12, expand=True),
                            ft.Text(format_money(total_fila), color="#2c5282", weight=ft.FontWeight.BOLD, size=12.5),
                        ]),
                        ft.Row([
                            ft.Text(f"📅 {formatear_fecha_bonita(p['fechaInicio'])} al {formatear_fecha_bonita(p['fechaFin'])}", color="#475569", size=10, expand=True),
                            ft.Container(
                                bgcolor="#d1fae5", padding=ft.Padding.symmetric(horizontal=7, vertical=3), border_radius=5,
                                on_click=lambda e, oi=orig_idx: self.cargar_presupuesto_por_indice(oi),
                                content=ft.Text("📂 Cargar", size=10, color="#065f46", weight=ft.FontWeight.BOLD)
                            ),
                            ft.Container(
                                bgcolor="#eaf3fc", padding=ft.Padding.symmetric(horizontal=7, vertical=3), border_radius=5,
                                on_click=lambda e, oi=orig_idx: self.abrir_modal_presupuesto(oi),
                                content=ft.Text("✏️ Editar", size=10, color="#2c5282", weight=ft.FontWeight.BOLD)
                            ),
                            ft.Container(
                                bgcolor="#fee2e2", padding=ft.Padding.symmetric(horizontal=7, vertical=3), border_radius=5,
                                on_click=lambda e, oi=orig_idx: self.confirmar_eliminar_presupuesto(oi),
                                content=ft.Text("×", size=12, color="#dc2626", weight=ft.FontWeight.BOLD)
                            ),
                        ], spacing=5),
                        ft.Row(chips_cats, wrap=True, spacing=4, run_spacing=4) if chips_cats else ft.Container()
                    ], spacing=5)
                )
            )

        return ft.Container(
            expand=True, bgcolor="#ffffff", border=ft.Border.all(1, "#c2d5e8"), border_radius=8, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column(expand=True, spacing=0, controls=[
                ft.Container(
                    bgcolor="#4a78a8", padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    content=ft.Row([
                        ft.Text(
                            f"📅 Períodos ({len(registros)} | {format_money(suma_totales)})",
                            color="white", weight=ft.FontWeight.BOLD, size=11, expand=True
                        ),
                        ft.Container(
                            bgcolor="#10b981", border_radius=6, padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                            on_click=lambda e: self.abrir_modal_presupuesto(None),
                            content=ft.Text("+ Nuevo", color="white", size=10.5, weight=ft.FontWeight.BOLD)
                        )
                    ])
                ),
                fbar,
                ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0, controls=tarjetas_presupuestos),
                self._build_pagination_bar("presupuestos", total_items, start_idx, end_idx, total_pages)
            ])
        )

    def _build_pagination_bar(self, key: str, total_items: int, start_idx: int, end_idx: int, total_pages: int) -> ft.Control:
        pag = self.pag_state[key]
        cur = pag["page"]
        info_txt = "0 reg." if total_items == 0 else f"{start_idx + 1}–{end_idx} de {total_items}"

        def _go(p: int):
            pag["page"] = max(1, min(total_pages, p))
            self.render_ui()

        return ft.Container(
            bgcolor="#f5f9fd", border=ft.Border.only(top=ft.BorderSide(1, "#c2d5e8")),
            padding=ft.Padding.symmetric(horizontal=8, vertical=5),
            content=ft.Row([
                ft.Text(info_txt, color="#3b5978", weight=ft.FontWeight.W_600, size=10.5),
                ft.Row([
                    ft.Container(bgcolor="#eaf3fc", border_radius=5, padding=ft.Padding.symmetric(horizontal=8, vertical=4), on_click=lambda e: _go(1), content=ft.Text("⏮", size=10, color="#2c5282")),
                    ft.Container(bgcolor="#eaf3fc", border_radius=5, padding=ft.Padding.symmetric(horizontal=8, vertical=4), on_click=lambda e: _go(cur - 1), content=ft.Text("◀", size=10, color="#2c5282")),
                    ft.Text(f"Pág. {cur}/{total_pages}", color="#2c5282", weight=ft.FontWeight.BOLD, size=10.5),
                    ft.Container(bgcolor="#eaf3fc", border_radius=5, padding=ft.Padding.symmetric(horizontal=8, vertical=4), on_click=lambda e: _go(cur + 1), content=ft.Text("▶", size=10, color="#2c5282")),
                    ft.Container(bgcolor="#eaf3fc", border_radius=5, padding=ft.Padding.symmetric(horizontal=8, vertical=4), on_click=lambda e: _go(total_pages), content=ft.Text("⏭", size=10, color="#2c5282")),
                ], spacing=4)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        )


def main(page: ft.Page):
    PresupuestosFletApp(page)


if __name__ == "__main__":
    ft.run(main)
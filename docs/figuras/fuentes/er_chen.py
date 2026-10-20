"""Entity-relationship diagrams in Chen notation (Pillow), one per service.

Usage: python er_chen.py <out_dir> [name ...]
Rules drawn: entity = rectangle (weak = double rectangle); attribute = oval
(key = solid underline, partial key = dashed underline, composite = oval with
child ovals); relationship = diamond (identifying = double diamond);
cardinality 1 / N / M next to each line; total participation = double line.
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = "C:/Windows/Fonts/"


def font(size, bold=False):
    return ImageFont.truetype(FONT_DIR + ("arialbd.ttf" if bold else "arial.ttf"), size)


F_ENT = font(32, True)
F_ATTR = font(26)
F_REL = font(26, True)
F_CARD = font(30, True)
F_LEG = font(24)
F_TITLE = font(34, True)
F_NOTE = font(24)

PALETTE = {
    "core":    {"fill": "#E1F5EE", "stroke": "#1D9E75", "text": "#0F6E56"},
    "supply":  {"fill": "#EEEDFE", "stroke": "#7F77DD", "text": "#3C3489"},
    "support": {"fill": "#FAECE7", "stroke": "#D85A30", "text": "#993C1D"},
    "gateway": {"fill": "#F1EFE8", "stroke": "#888780", "text": "#333333"},
}
INK = "#333333"
LINE = "#555555"
_MEASURE = ImageDraw.Draw(Image.new("RGB", (1, 1)))


def tw(text, f):
    return _MEASURE.textlength(text, font=f)


class Chen:
    def __init__(self, W, H, fam, title):
        self.W, self.H, self.c, self.title = W, H, PALETTE[fam], title
        self.items, self.lines, self.cards, self.notes = [], [], [], []
        self.used = set()

    # ---- elements --------------------------------------------------------------
    def entity(self, name, x, y, weak=False):
        e = dict(kind="entity", name=name, x=x, y=y, w=max(tw(name, F_ENT) + 56, 230), h=78, weak=weak)
        self.items.append(e)
        self.used.add("weak" if weak else "entity")
        return e

    def attr(self, owner, name, x, y, key=False, partial=False):
        a = dict(kind="attr", name=name, x=x, y=y, w=tw(name, F_ATTR) + 50, h=58, key=key, partial=partial)
        self.items.append(a)
        self.lines.append(("seg", [(owner["x"], owner["y"]), (x, y)], False))
        self.used.add("attr")
        if key:
            self.used.add("key")
        if partial:
            self.used.add("partial")
        return a

    def attrs_arc(self, owner, specs, a0, a1, rx, ry):
        """Place attributes on an elliptical arc; angles in degrees (0 = right, 90 = down)."""
        out = []
        n = len(specs)
        for i, spec in enumerate(specs):
            name, opts = (spec, {}) if isinstance(spec, str) else spec
            ang = a0 if n == 1 else a0 + (a1 - a0) * i / (n - 1)
            r = math.radians(ang)
            out.append(self.attr(owner, name, owner["x"] + rx * math.cos(r), owner["y"] + ry * math.sin(r), **opts))
        return out

    def rel(self, name, x, y, identifying=False):
        r = dict(kind="rel", name=name, x=x, y=y, w=max(tw(name, F_REL) + 110, 200), h=112, ident=identifying)
        self.items.append(r)
        self.used.add("ident" if identifying else "rel")
        return r

    def link(self, rel, ent, card, double=False, side=1, extra=34):
        self.lines.append(("seg", [(rel["x"], rel["y"]), (ent["x"], ent["y"])], double))
        if double:
            self.used.add("total")
        dx, dy = ent["x"] - rel["x"], ent["y"] - rel["y"]
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        a, b = rel["w"] / 2, rel["h"] / 2
        t = 1 / (abs(ux) / a + abs(uy) / b)
        dist = t + extra
        px, py = -uy, ux
        self.cards.append((card, rel["x"] + ux * dist + px * 26 * side, rel["y"] + uy * dist + py * 26 * side))

    def poly(self, points, double=False):
        self.lines.append(("seg", points, double))

    def card(self, text, x, y):
        self.cards.append((text, x, y))

    def note(self, text, x, y):
        self.notes.append((text, x, y))

    # ---- rendering ---------------------------------------------------------------
    def _line(self, d, pts, double):
        if not double:
            d.line(pts, fill=LINE, width=3)
            return
        for off in (-5, 5):
            shifted = []
            for i in range(len(pts) - 1):
                (x0, y0), (x1, y1) = pts[i], pts[i + 1]
                L = math.hypot(x1 - x0, y1 - y0) or 1
                px, py = -(y1 - y0) / L * off, (x1 - x0) / L * off
                shifted.append(((x0 + px, y0 + py), (x1 + px, y1 + py)))
            for p0, p1 in shifted:
                d.line([p0, p1], fill=LINE, width=3)

    def _dashed(self, d, x0, y, x1, color):
        x = x0
        while x < x1:
            d.line((x, y, min(x + 9, x1), y), fill=color, width=2)
            x += 15

    def _entity(self, d, e):
        x0, y0 = e["x"] - e["w"] / 2, e["y"] - e["h"] / 2
        x1, y1 = e["x"] + e["w"] / 2, e["y"] + e["h"] / 2
        d.rectangle((x0, y0, x1, y1), fill=self.c["fill"], outline=self.c["stroke"], width=4)
        if e["weak"]:
            d.rectangle((x0 + 8, y0 + 8, x1 - 8, y1 - 8), outline=self.c["stroke"], width=3)
        d.text((e["x"] - tw(e["name"], F_ENT) / 2, e["y"] - 19), e["name"], font=F_ENT, fill=self.c["text"])

    def _attr(self, d, a):
        x0, y0 = a["x"] - a["w"] / 2, a["y"] - a["h"] / 2
        d.ellipse((x0, y0, x0 + a["w"], y0 + a["h"]), fill="#FFFFFF", outline=self.c["stroke"], width=3)
        w = tw(a["name"], F_ATTR)
        tx, ty = a["x"] - w / 2, a["y"] - 16
        d.text((tx, ty), a["name"], font=F_ATTR, fill=INK)
        if a["key"]:
            d.line((tx, ty + 31, tx + w, ty + 31), fill=INK, width=2)
        if a["partial"]:
            self._dashed(d, tx, ty + 31, tx + w, INK)

    def _rel(self, d, r):
        a, b = r["w"] / 2, r["h"] / 2
        pts = [(r["x"], r["y"] - b), (r["x"] + a, r["y"]), (r["x"], r["y"] + b), (r["x"] - a, r["y"])]
        d.polygon(pts, fill="#FFFFFF", outline=self.c["stroke"], width=4)
        if r["ident"]:
            k = 12
            inner = [(r["x"], r["y"] - b + k), (r["x"] + a - k * 1.8, r["y"]), (r["x"], r["y"] + b - k),
                     (r["x"] - a + k * 1.8, r["y"])]
            d.polygon(inner, outline=self.c["stroke"], width=3)
        d.text((r["x"] - tw(r["name"], F_REL) / 2, r["y"] - 16), r["name"], font=F_REL, fill=self.c["text"])

    def _legend_items(self):
        """(symbol width, draw(d, x, y), label) for each symbol this diagram uses."""
        c = self.c
        items = []

        def rect(d, x, y):
            d.rectangle((x, y - 20, x + 60, y + 20), fill=c["fill"], outline=c["stroke"], width=3)

        def weak(d, x, y):
            rect(d, x, y)
            d.rectangle((x + 6, y - 14, x + 54, y + 14), outline=c["stroke"], width=2)

        def oval(d, x, y):
            d.ellipse((x, y - 18, x + 70, y + 18), fill="#FFFFFF", outline=c["stroke"], width=3)

        def key(d, x, y):
            oval(d, x, y)
            d.line((x + 18, y + 6, x + 52, y + 6), fill=INK, width=2)

        def partial(d, x, y):
            oval(d, x, y)
            self._dashed(d, x + 16, y + 6, x + 54, INK)

        def diamond(d, x, y):
            d.polygon([(x + 40, y - 22), (x + 80, y), (x + 40, y + 22), (x, y)], fill="#FFFFFF",
                      outline=c["stroke"], width=3)

        def ident(d, x, y):
            diamond(d, x, y)
            d.polygon([(x + 40, y - 14), (x + 66, y), (x + 40, y + 14), (x + 14, y)], outline=c["stroke"], width=2)

        def total(d, x, y):
            d.line((x, y - 5, x + 60, y - 5), fill=LINE, width=3)
            d.line((x, y + 5, x + 60, y + 5), fill=LINE, width=3)

        def card(d, x, y):
            d.text((x, y - 16), "1 · N · M", font=F_CARD, fill=INK)

        if "entity" in self.used:
            items.append((60, rect, "Entidad"))
        if "weak" in self.used:
            items.append((60, weak, "Entidad débil"))
        items.append((70, oval, "Atributo"))
        items.append((70, key, "Clave"))
        if "partial" in self.used:
            items.append((70, partial, "Clave parcial"))
        if "rel" in self.used or "ident" in self.used:
            items.append((80, diamond, "Relación"))
        if "ident" in self.used:
            items.append((80, ident, "Relación identificadora"))
        if "total" in self.used:
            items.append((60, total, "Participación total"))
        if "rel" in self.used or "ident" in self.used:
            items.append((tw("1 · N · M", F_CARD), card, "Cardinalidad"))
        return items

    def _legend(self, d, y_bottom):
        """Draw the legend, wrapping to as many rows as needed; rows end at y_bottom."""
        items = self._legend_items()
        rows, row, x = [], [], 40
        for wsym, fn, text in items:
            wtot = wsym + 12 + tw(text, F_LEG) + 44
            if row and x + wtot > self.W - 40:
                rows.append(row)
                row, x = [], 40
            row.append((wsym, fn, text))
            x += wtot
        rows.append(row)
        y = y_bottom - (len(rows) - 1) * 56
        widest = 0
        for row in rows:
            x = 40
            for wsym, fn, text in row:
                fn(d, x, y)
                x += wsym + 12
                d.text((x, y - 13), text, font=F_LEG, fill=INK)
                x += tw(text, F_LEG) + 44
            widest = max(widest, x)
            y += 56
        return widest

    def render(self, out):
        img = Image.new("RGB", (self.W, self.H), "white")
        d = ImageDraw.Draw(img)
        d.text((40, 24), self.title, font=F_TITLE, fill=self.c["text"])
        for _, pts, double in self.lines:
            self._line(d, pts, double)
        for it in self.items:
            {"entity": self._entity, "attr": self._attr, "rel": self._rel}[it["kind"]](d, it)
        for text, x, y in self.cards:
            d.text((x - tw(text, F_CARD) / 2, y - 18), text, font=F_CARD, fill=INK)
        for text, x, y in self.notes:
            d.text((x, y), text, font=F_NOTE, fill="#555555")
        end = self._legend(d, self.H - 50)
        assert end < self.W, (self.title, end)
        img.save(out, dpi=(300, 300))
        return out


# ===================================================================================
def gateway():
    g = Chen(1800, 1620, "gateway", "API Gateway · Laravel · MySQL")
    usuario = g.entity("Usuario", 520, 480)
    g.attrs_arc(usuario, [("id_usuario", {"key": True}), "nombre", "email", "password_hash", "estado",
                          "creado_en"], 190, 322, 400, 270)
    rol = g.entity("Rol", 1350, 480)
    g.attrs_arc(rol, [("id_rol", {"key": True}), "nombre"], 235, 305, 240, 230)
    tiene = g.rel("tiene", 935, 480)
    g.link(tiene, usuario, "N")
    g.link(tiene, rol, "1")
    permiso = g.entity("Permiso", 1350, 1060)
    g.attrs_arc(permiso, [("id_permiso", {"key": True}), "codigo", "descripcion"], 30, 150, 290, 220)
    agrupa = g.rel("agrupa", 1350, 770)
    g.link(agrupa, rol, "N")
    g.link(agrupa, permiso, "M")
    token = g.entity("TokenAcceso", 450, 1060)
    g.attrs_arc(token, [("id_token", {"key": True}), "token_hash", "nombre", "habilidades", "ultimo_uso",
                        "expira_en"], 10, 170, 330, 250)
    posee = g.rel("posee", 485, 770)
    g.link(posee, usuario, "1")
    g.link(posee, token, "N")
    rec = g.entity("RecuperacionContrasena", 1040, 1270)
    g.attrs_arc(rec, [("email", {"key": True}), "token_hash", "creado_en"], 40, 140, 230, 170)
    solicita = g.rel("solicita", 760, 880)
    g.link(solicita, usuario, "1")
    g.link(solicita, rec, "N")
    return g


def productos():
    g = Chen(1800, 1100, "core", "ms-productos · Flask · MySQL")
    cat = g.entity("Categoria", 420, 480)
    g.attrs_arc(cat, [("id_categoria", {"key": True}), "nombre", "descripcion", "estado"], 200, 340, 300, 240)
    cont = g.rel("contiene", 420, 820)
    g.poly([(cat["x"] - 90, cat["y"] + 39), (cont["x"] - cont["w"] / 2, cont["y"])])
    g.poly([(cat["x"] + 90, cat["y"] + 39), (cont["x"] + cont["w"] / 2, cont["y"])])
    g.card("1", cat["x"] - 150, 680)
    g.card("N", cat["x"] + 150, 680)
    g.note("categoría padre", 70, 720)
    g.note("subcategoría", 595, 720)
    prod = g.entity("Producto", 1310, 480)
    g.attrs_arc(prod, [("id_producto", {"key": True}), "sku", "nombre", "descripcion", "marca"],
                205, 335, 350, 250)
    g.attrs_arc(prod, ["unidad_medida", "precio_venta", "stock_minimo", "estado", "creado_en"],
                25, 155, 350, 250)
    clas = g.rel("clasifica", 870, 480)
    g.link(clas, cat, "1")
    g.link(clas, prod, "N")
    return g


def inventario():
    g = Chen(1900, 1960, "core", "ms-inventario · Flask · MySQL")
    saldo = g.entity("Saldo", 830, 300)
    g.attrs_arc(saldo, [("id_saldo", {"key": True}), "sku", "cantidad", "costo_promedio", "actualizado_en"],
                160, 380, 420, 180)
    bodega = g.entity("Bodega", 830, 760)
    g.attrs_arc(bodega, [("id_bodega", {"key": True}), "codigo", "nombre", "direccion", "estado"],
                235, 125, 400, 210)
    alm = g.rel("almacena", 830, 530)
    g.link(alm, bodega, "1")
    g.link(alm, saldo, "N")
    tras = g.entity("Traslado", 1530, 760)
    g.attrs_arc(tras, [("id_traslado", {"key": True}), "sku", "cantidad", "id_usuario", "fecha"],
                250, 400, 270, 230)
    sale = g.rel("sale de", 1180, 640)
    entra = g.rel("entra a", 1180, 880)
    g.link(sale, bodega, "1", side=-1)
    g.link(sale, tras, "N", side=-1, extra=60)
    g.link(entra, bodega, "1")
    g.link(entra, tras, "N", extra=60)
    mov = g.entity("Movimiento", 830, 1380)
    g.attrs_arc(mov, ["sku", ("id_movimiento", {"key": True}), "tipo", "cantidad", "costo_unitario",
                      "saldo_resultante", "valor_resultante", "motivo", "documento_referencia",
                      "id_usuario", "fecha"], 195, -15, 690, 370)
    reg = g.rel("registra", 830, 1070)
    g.link(reg, bodega, "1")
    g.link(reg, mov, "N")
    gen = g.rel("genera", 1410, 1120)
    g.link(gen, tras, "1")
    g.link(gen, mov, "N", extra=55)
    ev = g.entity("EventoProcesado", 1600, 190)
    g.attrs_arc(ev, [("id_evento", {"key": True}), "tipo", "procesado_en"], 25, 155, 240, 175)
    return g


def proveedores():
    g = Chen(1800, 1560, "supply", "ms-proveedores · Express · MySQL")
    prov = g.entity("Proveedor", 900, 470)
    g.attrs_arc(prov, [("id_proveedor", {"key": True}), "nit", "razon_social", "telefono", "email",
                       "direccion", "estado"], 190, 350, 580, 290)
    tiene = g.rel("tiene", 480, 790)
    cont = g.entity("Contacto", 380, 1080)
    g.attrs_arc(cont, [("id_contacto", {"key": True}), "nombre", "cargo", "telefono", "email"],
                250, 80, 290, 230)
    g.link(tiene, prov, "1")
    g.link(tiene, cont, "N")
    sumi = g.rel("suministra", 1260, 790, identifying=True)
    ps = g.entity("ProductoSuministrado", 1300, 1080, weak=True)
    g.attrs_arc(ps, [("sku", {"partial": True}), "precio_compra", "dias_entrega", "estado"],
                -60, 100, 340, 230)
    g.link(sumi, prov, "1")
    g.link(sumi, ps, "N", double=True)
    return g


def compras():
    g = Chen(2060, 1720, "supply", "ms-compras · Flask · MySQL")
    orden = g.entity("OrdenCompra", 1000, 530)
    g.attrs_arc(orden, [("id_orden", {"key": True}), "numero", "id_proveedor", "id_bodega_destino", "estado",
                        "total", "id_usuario_creador", "id_usuario_aprobador", "creada_en", "aprobada_en"],
                185, 355, 760, 330)
    rec = g.entity("Recepcion", 330, 1200)
    det = g.entity("DetalleOrden", 1000, 1200)
    dev = g.entity("DevolucionProveedor", 1720, 1200)
    contiene = g.rel("contiene", 1000, 870)
    tiene = g.rel("tiene", 560, 870)
    registra = g.rel("registra", 1480, 870)
    g.link(contiene, orden, "1")
    g.link(contiene, det, "N")
    g.link(tiene, orden, "1")
    g.link(tiene, rec, "N")
    g.link(registra, orden, "1", side=-1)
    g.link(registra, dev, "N", side=-1)
    recibe = g.rel("recibe", 665, 1200)
    g.link(recibe, rec, "N")
    g.link(recibe, det, "M")
    g.attr(recibe, "cantidad", 665, 1060)
    devuelve = g.rel("devuelve", 1335, 1200)
    g.link(devuelve, dev, "N", side=-1, extra=18)
    g.link(devuelve, det, "M", side=-1)
    g.attr(devuelve, "cantidad", 1335, 1060)
    g.attr(rec, "id_recepcion", 480, 1410, key=True)
    g.attr(rec, "observaciones", 250, 1450)
    g.attr(rec, "id_usuario", 120, 1330)
    g.attr(rec, "fecha", 90, 1220)
    g.attrs_arc(det, [("id_detalle", {"key": True}), "cantidad_pedida", "sku", "cantidad_recibida",
                      "precio_unitario"], 155, 25, 400, 330)
    g.attr(dev, "id_devolucion", 1880, 1380, key=True)
    g.attr(dev, "fecha", 1985, 1270)
    g.attr(dev, "motivo", 1700, 1440)
    g.attr(dev, "id_usuario", 1530, 1440)
    return g


def reportes():
    g = Chen(1800, 1700, "support", "ms-reportes · Flask · MySQL (modelo de lectura)")
    ring = [30, 90, 150, 210, 270, 330]

    def place(ent, specs):
        for ang, spec in zip(ring, specs):
            if spec == "":
                continue  # leave this ring position empty
            name, opts = (spec, {}) if isinstance(spec, str) else spec
            r = math.radians(ang)
            g.attr(ent, name, ent["x"] + 310 * math.cos(r), ent["y"] + 175 * math.sin(r), **opts)

    s = g.entity("SaldoReporte", 450, 340)
    place(s, ["cantidad", "costo_promedio", "valor_total", ("sku", {"key": True}), "actualizado_en",
              ("id_bodega", {"key": True})])
    m = g.entity("MovimientoDiario", 1350, 340)
    place(m, ["entradas", ("fecha", {"key": True}), "salidas", ("sku", {"key": True}), "",
              ("id_bodega", {"key": True})])
    o = g.entity("OrdenPendiente", 450, 840)
    place(o, ["estado", "actualizada_en", "", ("id_orden", {"key": True}), "", "id_proveedor"])
    a = g.entity("AlertaStock", 1350, 840)
    place(a, ["saldo", "stock_minimo", "fecha", ("sku", {"key": True}), "activa", ("id_bodega", {"key": True})])
    e = g.entity("EventoProcesado", 900, 1330)
    place(e, ["procesado_en", "", "", ("id_evento", {"key": True}), "", "tipo"])
    g.note("Modelo de lectura: las tablas no se relacionan entre sí; se actualizan con los eventos de RabbitMQ.",
           40, 1580)
    return g


def notificaciones():
    g = Chen(1800, 1260, "support", "ms-notificaciones · Express · Firebase (Firestore)")
    n = g.entity("Notificacion", 500, 640)
    g.attrs_arc(n, [("id_notificacion", {"key": True}), "tipo", "titulo", "mensaje", "rol_destino", "leida",
                    "creada_en"], 270, 115, 380, 320)
    datos = g.attr(n, "datos", 760, 330)
    for name, x, y in [("sku", 640, 175), ("bodega", 800, 150), ("saldo", 950, 205)]:
        g.attr(datos, name, x, y)
    rel = g.rel("se entrega a", 960, 640)
    dsp = g.entity("Dispositivo", 1400, 640)
    g.attrs_arc(dsp, [("id_dispositivo", {"key": True}), "id_usuario", "rol", "token_fcm", "plataforma",
                      "registrado_en"], -75, 75, 290, 330)
    g.link(rel, n, "N")
    g.link(rel, dsp, "M")
    g.note("Colecciones de Firestore; el atributo datos es compuesto (sku, bodega, saldo).", 40, 1150)
    return g


DIAGRAMS = {
    "gateway": gateway,
    "productos": productos,
    "inventario": inventario,
    "proveedores": proveedores,
    "compras": compras,
    "reportes": reportes,
    "notificaciones": notificaciones,
}

if __name__ == "__main__":
    out_dir = sys.argv[1]
    names = sys.argv[2:] or list(DIAGRAMS)
    for name in names:
        g = DIAGRAMS[name]()
        print(g.render(os.path.join(out_dir, f"e2_er_{name}.png")))

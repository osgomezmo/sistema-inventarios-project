"""Entrega 2 - logical architecture diagram (Pillow).

Gateway (Laravel + MySQL: users, roles, tokens), six microservices with framework and
own database, synchronous REST dependencies and RabbitMQ events.
"""
import sys
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
W, H = 2000, 1450
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)

FONT_DIR = "C:/Windows/Fonts/"
def font(size, bold=False):
    return ImageFont.truetype(FONT_DIR + ("arialbd.ttf" if bold else "arial.ttf"), size)

F_TITLE = font(34, True)
F_SUB = font(25)
F_SMALL = font(22)
F_SMALL_B = font(22, True)
F_LABEL = font(23)
F_LABEL_B = font(24, True)

FAM = {
    "core":    {"fill": "#E1F5EE", "stroke": "#1D9E75", "text": "#0F6E56"},
    "supply":  {"fill": "#EEEDFE", "stroke": "#7F77DD", "text": "#3C3489"},
    "support": {"fill": "#FAECE7", "stroke": "#D85A30", "text": "#993C1D"},
    "gateway": {"fill": "#F1EFE8", "stroke": "#888780", "text": "#333333"},
    "client":  {"fill": "#FFFFFF", "stroke": "#888780", "text": "#333333"},
    "broker":  {"fill": "#FFF4E0", "stroke": "#D99A2B", "text": "#7A4F00"},
}
LINE = "#555555"

def tw(txt, f):
    return d.textlength(txt, font=f)

def text_center(cx, y, txt, f, fill):
    d.text((cx - tw(txt, f) / 2, y), txt, font=f, fill=fill)

def dashed_line(p0, p1, dash=15, gap=10, width=4, fill=LINE):
    (x0, y0), (x1, y1) = p0, p1
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    pos = 0.0
    while pos < length:
        end = min(pos + dash, length)
        d.line((x0 + ux * pos, y0 + uy * pos, x0 + ux * end, y0 + uy * end), fill=fill, width=width)
        pos = end + gap

def arrow(p0, p1, dashed=False, width=4, head=22, fill=LINE):
    (x0, y0), (x1, y1) = p0, p1
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    bx, by = x1 - ux * head, y1 - uy * head
    if dashed:
        dashed_line((x0, y0), (bx, by), width=width, fill=fill)
    else:
        d.line((x0, y0, bx, by), fill=fill, width=width)
    px, py = -uy, ux
    d.polygon([(x1, y1), (bx + px * head * 0.55, by + py * head * 0.55),
               (bx - px * head * 0.55, by - py * head * 0.55)], fill=fill)

def cylinder(x0, y0, x1, y1, fill, stroke, width=3):
    eh = max(10, (y1 - y0) * 0.28)
    d.rectangle((x0, y0 + eh / 2, x1, y1 - eh / 2), fill=fill)
    d.line((x0, y0 + eh / 2, x0, y1 - eh / 2), fill=stroke, width=width)
    d.line((x1, y0 + eh / 2, x1, y1 - eh / 2), fill=stroke, width=width)
    d.chord((x0, y1 - eh, x1, y1), 0, 180, fill=fill, outline=stroke, width=width)
    d.ellipse((x0, y0, x1, y0 + eh), fill=fill, outline=stroke, width=width)

def service(x0, y0, x1, y1, name, framework, role, db, fam):
    c = FAM[fam]
    d.rounded_rectangle((x0, y0, x1, y1), radius=18, fill=c["fill"], outline=c["stroke"], width=4)
    cx = (x0 + x1) / 2
    text_center(cx, y0 + 18, name, F_TITLE, c["text"])
    text_center(cx, y0 + 66, f"{framework} · {role}", F_SUB, c["text"])
    # database line: mini cylinder + label, centered
    label = f"BD propia: {db}"
    wtot = 28 + 10 + tw(label, F_SMALL)
    sx = cx - wtot / 2
    cylinder(sx, y0 + 108, sx + 28, y0 + 140, "#FFFFFF", c["stroke"])
    d.text((sx + 38, y0 + 111), label, font=F_SMALL, fill=c["text"])

def lines_text(x, y, lines, f, fill, align="left", step=28):
    for i, ln in enumerate(lines):
        if align == "right":
            d.text((x - tw(ln, f), y + i * step), ln, font=f, fill=fill)
        else:
            d.text((x, y + i * step), ln, font=f, fill=fill)

# --- Client -----------------------------------------------------------------------
c = FAM["client"]
d.rounded_rectangle((760, 20, 1240, 100), radius=18, fill=c["fill"], outline=c["stroke"], width=4)
text_center(1000, 40, "Cliente web (navegador)", font(31, True), c["text"])
arrow((1000, 100), (1000, 150))
d.text((1014, 108), "HTTPS + token de Sanctum", font=F_SMALL, fill=LINE)

# --- API Gateway ---------------------------------------------------------------------
g = FAM["gateway"]
GX0, GY0, GX1, GY1 = 480, 150, 1460, 335
d.rounded_rectangle((GX0, GY0, GX1, GY1), radius=18, fill=g["fill"], outline=g["stroke"], width=4)
text_center(970, GY0 + 16, "API Gateway propio · Laravel", F_TITLE, g["text"])
text_center(970, GY0 + 66, "Único punto de entrada · enrutamiento · token de servicio", F_SUB, g["text"])
text_center(970, GY0 + 102, "Usuarios, roles y permisos · autenticación con Sanctum", F_SUB, g["text"])
text_center(970, GY0 + 138, "Control de acceso por roles (401 / 403)", F_SUB, g["text"])
d.line((GX1, 242, 1560, 242), fill=g["stroke"], width=4)
cylinder(1560, 190, 1690, 295, g["fill"], g["stroke"], width=4)
d.text((1708, 192), "BD del gateway", font=F_SMALL_B, fill="#333333")
lines_text(1708, 220, ["MySQL: usuarios,", "roles y tokens"], F_SMALL, "#333333")

arrow((970, GY1), (970, 418))
lines_text(986, 340, ["REST + token de servicio + identidad del usuario",
                      "(X-User-Id, X-User-Role, X-Correlation-Id)"], F_SMALL, LINE, step=27)

# --- Cluster container ------------------------------------------------------------------
cx0, cy0, cx1, cy1 = 30, 418, 1970, 1290
gray = "#9A9A9A"
for (a, b) in [((cx0 + 20, cy0), (cx1 - 20, cy0)), ((cx0 + 20, cy1), (cx1 - 20, cy1)),
               ((cx0, cy0 + 20), (cx0, cy1 - 20)), ((cx1, cy0 + 20), (cx1, cy1 - 20))]:
    dashed_line(a, b, dash=12, gap=10, width=3, fill=gray)
for (bbox, start) in [((cx0, cy0, cx0 + 40, cy0 + 40), 180), ((cx1 - 40, cy0, cx1, cy0 + 40), 270),
                      ((cx0, cy1 - 40, cx0 + 40, cy1), 90), ((cx1 - 40, cy1 - 40, cx1, cy1), 0)]:
    d.arc(bbox, start, start + 90, fill=gray, width=3)
d.text((cx0 + 28, cy0 + 14),
       "Red interna de microservicios · solo se accede a ellos a través del API Gateway",
       font=F_SMALL, fill="#666666")

# --- Row 1 -----------------------------------------------------------------------------
R1Y0, R1Y1 = 480, 640
xs = [(65, 455), (560, 950), (1050, 1440), (1545, 1935)]
service(xs[0][0], R1Y0, xs[0][1], R1Y1, "ms-productos", "Flask", "Catálogo", "MySQL", "core")
service(xs[1][0], R1Y0, xs[1][1], R1Y1, "ms-inventario", "Flask", "Stock y kardex", "MySQL", "core")
service(xs[2][0], R1Y0, xs[2][1], R1Y1, "ms-proveedores", "Express", "Proveedores", "MySQL", "supply")
service(xs[3][0], R1Y0, xs[3][1], R1Y1, "ms-compras", "Flask", "Órdenes de compra", "MySQL", "supply")

ym = R1Y0 + 60
arrow((xs[1][0], ym), (xs[0][1], ym))
text_center((xs[0][1] + xs[1][0]) / 2, ym - 36, "REST", F_LABEL_B, LINE)
arrow((xs[3][0], ym), (xs[2][1], ym))
text_center((xs[2][1] + xs[3][0]) / 2, ym - 36, "REST", F_LABEL_B, LINE)

# --- Broker ------------------------------------------------------------------------------
BY0, BY1 = 820, 905
b = FAM["broker"]
d.rounded_rectangle((65, BY0, 1935, BY1), radius=14, fill=b["fill"], outline=b["stroke"], width=4)
text_center(1000, BY0 + 14, "RabbitMQ · broker de eventos", font(27, True), b["text"])
text_center(1000, BY0 + 50, "una cola por servicio consumidor · mensajes en JSON", F_SMALL, b["text"])

# compras publishes
arrow((1700, R1Y1), (1700, BY0), dashed=True)
lines_text(1688, 668, ["publica:", "MercanciaRecibida", "DevolucionProveedorRegistrada", "OrdenCompraActualizada"],
           F_SMALL, LINE, align="right", step=27)
# inventario consumes
arrow((650, BY0), (650, R1Y1), dashed=True)
lines_text(638, 682, ["consume:", "MercanciaRecibida", "DevolucionProveedorRegistrada"],
           F_SMALL, LINE, align="right", step=27)
# inventario publishes
arrow((860, R1Y1), (860, BY0), dashed=True)
lines_text(874, 682, ["publica:", "MovimientoRegistrado", "StockBajoUmbral"], F_SMALL, LINE, step=27)

# --- Row 2: reactive services -------------------------------------------------------------
R2Y0, R2Y1 = 1060, 1220
xs2 = [(230, 790), (1150, 1710)]
service(xs2[0][0], R2Y0, xs2[0][1], R2Y1, "ms-notificaciones", "Express", "Alertas", "Firebase", "support")
service(xs2[1][0], R2Y0, xs2[1][1], R2Y1, "ms-reportes", "Flask", "Reportes y dashboard", "MySQL", "support")

arrow((510, BY1), (510, R2Y0), dashed=True)
lines_text(524, 935, ["consume:", "StockBajoUmbral"], F_SMALL, LINE, step=27)
arrow((1430, BY1), (1430, R2Y0), dashed=True)
lines_text(1444, 935, ["consume: MovimientoRegistrado,",
                       "StockBajoUmbral, OrdenCompraActualizada"], F_SMALL, LINE, step=27)

# --- Legend -------------------------------------------------------------------------------
LY = 1318
arrow((50, LY + 14), (150, LY + 14))
d.text((165, LY), "Síncrona (REST)", font=F_LABEL, fill="#333333")
arrow((420, LY + 14), (520, LY + 14), dashed=True)
d.text((535, LY), "Asíncrona (evento por RabbitMQ)", font=F_LABEL, fill="#333333")
cylinder(925, LY - 4, 953, LY + 28, "#FFFFFF", "#555555")
d.text((965, LY), "Base de datos propia de cada servicio", font=F_LABEL, fill="#333333")

lx = 50
for fam, name in [("gateway", "Entrada, identidad y acceso"), ("core", "Núcleo de inventario"),
                  ("supply", "Cadena de suministro"), ("support", "Servicios reactivos")]:
    cc = FAM[fam]
    d.rounded_rectangle((lx, LY + 62, lx + 46, LY + 98), radius=8, fill=cc["fill"], outline=cc["stroke"], width=3)
    d.text((lx + 58, LY + 66), name, font=F_LABEL, fill="#333333")
    lx += 58 + tw(name, F_LABEL) + 55
assert lx < W, lx

img.save(OUT, dpi=(300, 300))
print("saved", OUT, img.size)

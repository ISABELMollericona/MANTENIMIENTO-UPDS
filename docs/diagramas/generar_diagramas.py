"""Regenera todos los diagramas: Graphviz (.dot) y secuencias (matplotlib).

Uso (desde esta carpeta):  python generar_diagramas.py [carpeta_copia]
Requiere Graphviz (`dot` en el PATH) y matplotlib.
"""
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent

for fuente in sorted(AQUI.glob("*.dot")):
    subprocess.run(["dot", "-Tpng", "-Gdpi=130", fuente.name, "-o", fuente.with_suffix(".png").name], cwd=AQUI, check=True)
    print("ok", fuente.stem)

subprocess.run([sys.executable, "secuencias.py"], cwd=AQUI, check=True)

if len(sys.argv) > 1:
    destino = Path(sys.argv[1])
    destino.mkdir(parents=True, exist_ok=True)
    for png in sorted(AQUI.glob("[0-9][0-9]_*.png")):
        shutil.copy2(png, destino / png.name)
    print("copiados a", destino)

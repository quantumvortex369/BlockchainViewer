import asyncio
import websockets
import json
import requests
from rich.console import Console
from rich.panel import Panel
from datetime import datetime
import csv
from collections import deque
import os
import signal
import sys

# Consola con Rich
console = Console()

# Para guardar las transacciones
TRANSACCIONES = deque(maxlen=1000)
CSV_FILE = "blockchainviewer_data/transacciones.csv"
os.makedirs("blockchainviewer_data", exist_ok=True)

# Menú para seleccionar qué tipo de transacciones guardar
def seleccionar_tipo_guardado():
    console.print("[bold green]¿Qué tipo de transacciones quieres guardar en el CSV?[/bold green]")
    console.print("1. Todas\n2. Ballenas \n3. Fee bajo \n4. Mixers ")
    opciones = input("Elige una o más opciones (por ejemplo: 2,4): ").strip()
    opciones_seleccionadas = opciones.split(",")
    # Asegurarse de que las opciones sean válidas
    validas = {"1", "2", "3", "4"}
    return [opcion for opcion in opciones_seleccionadas if opcion in validas]

tipo_guardado = seleccionar_tipo_guardado()

#  Exportar historial a CSV
def exportar_csv():
    # Abrimos el archivo en modo "append" para agregar las transacciones sin sobrescribir
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["hash", "hora", "btc", "usd", "outputs", "fee", "categoria"])

        # Si el archivo está vacío, escribe el encabezado
        if f.tell() == 0:
            writer.writeheader()

        # Escribe las transacciones actuales
        for tx in TRANSACCIONES:
            writer.writerow(tx)
    console.print(f"[green]Transacciones exportadas a:[/green] {CSV_FILE}")

#  Análisis y visualización
def mostrar_transaccion(tx):
    hash_tx = tx["x"]["hash"]
    total_satoshis = sum(out["value"] for out in tx["x"]["out"])
    total_btc = total_satoshis / 1e8
    usd_est = total_btc * obtener_precio_btc()
    num_outputs = len(tx["x"]["out"])
    fee = tx["x"].get("fee", 0) / 1e8

    #  Lógica de resaltado
    categoria = []
    if total_btc > 50:
        categoria.append("BALLENA")
    if fee < 0.00005:
        categoria.append("FEE BAJO")
    if num_outputs > 30:
        categoria.append("MIXER")

    timestamp = datetime.fromtimestamp(tx["x"]["time"]).strftime("%Y-%m-%d %H:%M:%S")

    panel = Panel.fit(
        f"[bold]Hash:[/bold] {hash_tx}\n"
        f"[cyan]Hora:[/cyan] {timestamp}\n"
        f"[green]BTC:[/green] {total_btc:.6f} BTC ≈ ${usd_est:,.2f}\n"
        f"[magenta]Outputs:[/magenta] {num_outputs} | [yellow]Fee:[/yellow] {fee:.8f} BTC\n"
        f"[bold red]{' | '.join(categoria) if categoria else 'Normal'}[/bold red]",
        title="[bold blue]Transacción recibida",
        border_style="blue"
    )
    console.print(panel)

    transaccion = {
        "hash": hash_tx,
        "hora": timestamp,
        "btc": total_btc,
        "usd": usd_est,
        "outputs": num_outputs,
        "fee": fee,
        "categoria": ' | '.join(categoria) if categoria else "Normal"
    }

    #  Guardar si coincide con el filtro
    if (
        "1" in tipo_guardado  # Todas
        or ("2" in tipo_guardado and "BALLENA" in categoria)  # Ballenas
        or ("3" in tipo_guardado and "FEE BAJO" in categoria)  # Fee bajo
        or ("4" in tipo_guardado and "MIXER" in categoria)  # Mixers
    ):
        TRANSACCIONES.append(transaccion)

#  Precio BTC actual
def obtener_precio_btc():
    try:
        res = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")
        return res.json()["bitcoin"]["usd"]
    except:
        return 0

#  Conexión al WebSocket de Blockchain
async def escuchar_transacciones():
    url = "wss://ws.blockchain.info/inv"
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"op": "unconfirmed_sub"}))
        console.print("[bold green]Conectado al WebSocket de Blockchain.info[/bold green]")

        try:
            while True:
                mensaje = await ws.recv()
                data = json.loads(mensaje)
                mostrar_transaccion(data)
        except Exception as e:
            console.print(f"[red]Error en WebSocket:[/red] {e}")
        finally:
            exportar_csv()

#  Detención controlada con SIGINT (Ctrl+C)
def detener_programa(signal, frame):
    console.print("\n[bold yellow]Cancelado por el usuario. Exportando datos...[/bold yellow]")
    exportar_csv()
    sys.exit(0)

# Captura la señal SIGINT (Ctrl+C)
signal.signal(signal.SIGINT, detener_programa)

if __name__ == "__main__":
    try:
        asyncio.run(escuchar_transacciones())
    except KeyboardInterrupt:
        pass

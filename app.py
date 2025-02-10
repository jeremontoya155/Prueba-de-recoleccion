from flask import Flask, render_template, request, jsonify, send_file
from instagrapi import Client
import threading
import json
import queue
import os
import time
import random

app = Flask(__name__)

SESSION_FILE = "session.json"
OUTPUT_FILE = "filtered_followers.json"
PROXY = ""
KEYWORDS = ["Marketing", "marke", "digital", "Digital"]
NUM_THREADS = 8  # Aumentamos hilos para procesar más rápido
MAX_FOLLOWERS_TO_CHECK = 50  # Límite de seguidores a revisar

# Variables globales
task_queue = queue.Queue()
file_lock = threading.Lock()
stop_event = threading.Event()
progress = {"status": "Esperando datos...", "progress": 0, "total": 0}


### 📌 FUNCIONES PRINCIPALES

# Función optimizada para iniciar sesión
def iniciar_sesion(username, password):
    cl = Client()
    if PROXY:
        cl.set_proxy(PROXY)

    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(username, password)
            return cl
        except:
            pass  # No imprimimos errores innecesarios

    try:
        cl.login(username, password)
        cl.dump_settings(SESSION_FILE)
        return cl
    except:
        return None


# Obtener seguidores de una cuenta (optimizado)
def obtener_seguidores(cl, username):
    try:
        user_id = cl.user_id_from_username(username)
        return cl.user_followers(user_id, amount=MAX_FOLLOWERS_TO_CHECK)
    except:
        return {}


# Filtrar seguidores en hilos optimizados
def filtrar_seguidores(cl):
    global progress
    while not task_queue.empty() and not stop_event.is_set():
        follower_id = task_queue.get()
        try:
            # Pequeñas pausas para no parecer bot
            time.sleep(random.uniform(1.5, 4))

            user_info = cl.user_info(follower_id)
            bio = user_info.biography.lower() if user_info.biography else ""

            if any(keyword.lower() in bio for keyword in KEYWORDS):
                follower_data = {
                    "id": follower_id,
                    "username": user_info.username,
                    "full_name": user_info.full_name,
                    "bio": bio,
                    "followers": user_info.follower_count
                }

                with file_lock:
                    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                        json.dump(follower_data, f, ensure_ascii=False)
                        f.write("\n")

                progress["progress"] += 1

        except:
            pass  # No imprimimos errores menores
        finally:
            task_queue.task_done()


# Iniciar scraping optimizado
def iniciar_scraping(username, password, target_accounts):
    global progress
    progress = {"status": "Iniciando sesión...", "progress": 0, "total": 0}

    open(OUTPUT_FILE, "w").close()

    cl = iniciar_sesion(username, password)
    if not cl:
        progress["status"] = "Error en el inicio de sesión."
        return

    # Obtener seguidores de las cuentas objetivo
    progress["status"] = "Obteniendo seguidores..."
    for account in target_accounts:
        followers = obtener_seguidores(cl, account)
        if not followers:
            continue

        for follower_id in followers.keys():
            task_queue.put(follower_id)

    progress["total"] = task_queue.qsize()
    progress["status"] = "Filtrando seguidores..."

    # Iniciar hilos de filtrado optimizados
    threads = []
    for _ in range(NUM_THREADS):
        thread = threading.Thread(target=filtrar_seguidores, args=(cl,))
        thread.start()
        threads.append(thread)

    task_queue.join()
    stop_event.set()

    for thread in threads:
        thread.join()

    progress["status"] = "Finalizado."


### 📌 RUTAS FLASK

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        target_accounts = request.form["target_accounts"].split(",")

        threading.Thread(target=iniciar_scraping, args=(username, password, target_accounts)).start()

    return render_template("index.html")


@app.route("/progress")
def get_progress():
    return jsonify(progress)


@app.route("/download")
def download_file():
    return send_file(OUTPUT_FILE, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)

import os
import uuid
import json
import glob
import time
import pandas as pd
from threading import Thread
from flask import Flask, request, jsonify

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def clean_old_files(threshold_seconds=3600):
    current_time = time.time()
    files = glob.glob(os.path.join(UPLOAD_FOLDER, '*.xlsx'))
    for file_path in files:
        try:
            if current_time - os.path.getmtime(file_path) > threshold_seconds:
                os.remove(file_path)
        except Exception as e:
            pass

def run_periodic_cleanup():
    while True:
        clean_old_files(threshold_seconds=3600)
        time.sleep(1800)

@app.route("/api/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "File kosong."}), 400
    
    file = request.files['file']
    if file.filename == '' or not file.filename.lower().endswith('.xlsx'):
        return jsonify({"status": "error", "message": "Format tidak valid."}), 400

    try:
        old_file_id = request.form.get('old_file_id')
        if old_file_id:
            old_path = os.path.join(UPLOAD_FOLDER, f"{old_file_id}.xlsx")
            if os.path.exists(old_path):
                os.remove(old_path)

        new_file_id = str(uuid.uuid4())
        save_path = os.path.join(UPLOAD_FOLDER, f"{new_file_id}.xlsx")
        file.save(save_path)

        return jsonify({"status": "success", "file_id": new_file_id}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/view/<file_id>", methods=["GET"])
def get_dashboard_data(file_id):
    file_path = os.path.join(UPLOAD_FOLDER, f"{file_id}.xlsx")

    if not os.path.exists(file_path):
        return jsonify({"status": "error", "message": "File not found."}), 404

    try:
        df_raw_local = pd.read_excel(file_path, engine='openpyxl')
        
        params = {
            "jenis_lha": request.args.get("jenis_lha", "ALL"),
            "tahun_lha": request.args.get("tahun_lha", "ALL"),
            "direktorat": request.args.get("direktorat", "ALL"),
            "bidang": request.args.get("bidang", "ALL"),
            "pic": request.args.get("pic", "ALL")
        }

        df = df_raw_local.copy()

        if params["jenis_lha"] != "ALL":
            df = df[df["Jenis LHA"] == params["jenis_lha"]]
        if params["tahun_lha"] != "ALL":
            try:
                df = df[df["Tahun LHA"] == int(params["tahun_lha"])]
            except ValueError:
                pass
        if params["direktorat"] != "ALL":
            df = df[df["Direktorat"] == params["direktorat"]]
        if params["bidang"] != "ALL":
            df = df[df["Bidang"] == params["bidang"]]
        if params["pic"] != "ALL":
            df = df[df["PIC"] == params["pic"]]

        if df.empty:
            return jsonify({"status": "warning", "message": "Tidak ada data.", "data": {}})

        temuan_unik = df.drop_duplicates(subset=["Jenis LHA", "Tahun LHA", "Direktorat", "Bidang", "Temuan", "PIC"])
        
        response_payload = {
            "status": "success",
            "metrics": {
                "total_temuan": len(temuan_unik),
                "aoi_closed": int((temuan_unik["Status AOI"] == "Closed").sum()),
                "aoi_open": int((temuan_unik["Status AOI"] == "Open").sum()),
                "rekomendasi_closed": int((df["Status Tindak Lanjut Rekomendasi"] == "Closed").sum()),
                "rekomendasi_open": int((df["Status Tindak Lanjut Rekomendasi"] == "Open").sum())
            },
            "charts": {
                "status_aoi_per_bidang": temuan_unik.groupby(["Bidang", "Status AOI"]).size().unstack(fill_value=0).to_dict(orient="index"),
                "status_rekomendasi_per_direktorat": df.groupby(["Direktorat", "Status Tindak Lanjut Rekomendasi"]).size().unstack(fill_value=0).to_dict(orient="index")
            },
            "filtered_data": json.loads(df.to_json(orient="records", date_format="iso"))
        }

        return jsonify(response_payload)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        daemon = Thread(target=run_periodic_cleanup, daemon=True)
        daemon.start()
    app.run(debug=True, host='0.0.0.0', port=8069)
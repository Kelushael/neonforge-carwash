#!/usr/bin/env python3
from flask import Flask, send_from_directory, request, jsonify
import os, pathlib

ROOT = pathlib.Path("/root")
app  = Flask(__name__)

@app.route("/")
def index():
    return send_from_directory(ROOT, "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(ROOT, filename)

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "no file"}), 400
    dest = ROOT / f.filename
    f.save(dest)
    return jsonify({"ok": True, "filename": f.filename, "path": str(dest)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888, debug=False)

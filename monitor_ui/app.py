from flask import Flask, render_template
import requests

app = Flask(__name__)

MONITOR_API = "http://monitoring:5002/api"

@app.route("/")
def index():
    overview = requests.get(f"{MONITOR_API}/overview").json()
    return render_template("index.html", data=overview["data"])

@app.route("/alerts")
def alerts():
    alerts = requests.get(f"{MONITOR_API}/alerts").json()
    return render_template("alerts.html", alerts=alerts["data"]["alerts"])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)


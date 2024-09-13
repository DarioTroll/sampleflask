
from flask import Flask
import os

app = Flask(__name__)

# Imposta la chiave segreta utilizzando una variabile d'ambiente
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# Verifica se la chiave segreta è impostata, se no, stampa un avviso
if app.secret_key is None:
    print("Attenzione: FLASK_SECRET_KEY non è impostata!")

@app.route('/')
def hello():
    return "Welcome to my sample Flask app!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)



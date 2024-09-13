from flask import Flask
import os
from functools import wraps
from datetime import datetime
from flask import Flask, request, redirect, session, render_template, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error


app = Flask(__name__)

# Imposta la chiave segreta utilizzando una variabile d'ambiente
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# Verifica se la chiave segreta è impostata, se no, stampa un avviso
if app.secret_key is None:
    print("Attenzione: FLASK_SECRET_KEY non è impostata!")

# Funzione per ottenere la connessione al database
def get_db_connection():

    print(f'Host:', os.getenv('MYSQL_HOST'))
    print(f'User:', os.getenv('MYSQL_USER'))
    print(f'Password:', os.getenv('MYSQL_PASSWORD'))
    print(f'Database:', os.getenv('MYSQL_DB'))
    print(f'Port:', os.getenv('MYSQL_PORT'))

    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST'),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DB')
    )

# Decoratore per verificare se l'utente è admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if not user or not user['is_admin']:
            return redirect('/home')
        return f(*args, **kwargs)
    return decorated_function

# Pagina di login
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Modifica qui: usa 'username' invece di 'email'
        username = request.form['username']
        password = request.form['password']

        # Connessione al database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Modifica qui: seleziona l'utente in base allo username
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()

        # Chiusura della connessione
        cursor.close()
        conn.close()

        # Verifica la password e gestisce il login
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            return redirect('/home')
        else:
            return 'Credenziali non valide', 401

    # Se GET, visualizza il form di login
    return render_template('login.html')


# Pagina di registrazione
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nome = request.form['nome']
        cognome = request.form['cognome']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Verifica che le password corrispondano
        if password != confirm_password:
            flash('Le password non corrispondono. Riprova.', 'error')
            return redirect('/register')

        hashed_password = generate_password_hash(password, method='sha256')

        # Controlla se l'email è già registrata
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            flash('L\'email è già registrata. Riprova con un\'altra.', 'error')
            cursor.close()
            conn.close()
            return redirect('/register')

        try:
            # Inserisce il nuovo utente nel database
            cursor.execute('INSERT INTO users (nome, cognome, email, password) VALUES (%s, %s, %s, %s)',
                           (nome, cognome, email, hashed_password))
            conn.commit()
            flash('Registrazione avvenuta con successo. Puoi ora effettuare il login.', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Errore durante la registrazione: {e}', 'error')
        finally:
            cursor.close()
            conn.close()

        return redirect('/')

    return render_template('register.html')

# Pagina home
@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'user_id' not in session:
        return redirect('/')

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
    user = cursor.fetchone()

    if request.method == 'POST':
        now = datetime.now()
        if 'mark_in' in request.form:
            print(f'Provando ad entrare! (:',user_id,')')
            # Verifica se c'è già un'entrata in corso
            cursor.execute('SELECT * FROM presenze WHERE user_id = %s AND ora_uscita IS NULL',
                                        (session['user_id'],))
            current_entry = cursor.fetchone()
            if current_entry:
                flash('Hai già registrato un\'entrata in corso. Devi segnare l\'uscita prima di segnare una nuova entrata.', 'error')
            else:
                cursor.execute('INSERT INTO presenze (user_id, ora_entrata) VALUES (%s, %s)',
                             (session['user_id'], now))
                conn.commit()
                flash('Entrata registrata con successo.', 'success')
        elif 'mark_out' in request.form:
            print(f'Provando ad uscire! (:',user_id,')')
            # Verifica se c'è un'entrata registrata
            cursor.execute('SELECT * FROM presenze WHERE user_id = %s AND ora_uscita IS NULL',
                                        (session['user_id'],))
            current_entry = cursor.fetchone()
            if not current_entry:
                flash('Non hai registrato alcuna entrata. Non puoi segnare l\'uscita.', 'error')
            else:
                cursor.execute('UPDATE presenze SET ora_uscita = %s WHERE id = %s',
                             (now, current_entry['id']))
                conn.commit()
                flash('Uscita registrata con successo.', 'success')

    # Recupera le informazioni dell'utente
    cursor.execute('SELECT nome, cognome, is_admin, coffee_count FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('home.html', user=user)

# Pagina presenze
@app.route('/presenze')
@admin_required  # Questa pagina è accessibile solo agli admin
def presenze():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Query per ottenere tutte le presenze
    query = '''
        SELECT p.id, u.nome, u.cognome, p.ora_entrata, p.ora_uscita, DATE(p.ora_entrata) as data
        FROM presenze p
        JOIN users u ON p.user_id = u.id
        ORDER BY data DESC, p.ora_entrata DESC
    '''
    cursor.execute(query)
    presenze = cursor.fetchall()
    cursor.close()
    conn.close()

    # Verifica i dati recuperati
    print("Dati delle presenze:", presenze)

    # Raggruppa le presenze per giorno
    presenze_per_giorno = {}
    for presenza in presenze:
        data = presenza['data']
        if data not in presenze_per_giorno:
            presenze_per_giorno[data] = []

        # Gestione delle frazioni di secondo
        entrata = presenza['ora_entrata'].strftime('%Y-%m-%d %H:%M:%S') if presenza['ora_entrata'] else 'N/A'
        uscita = presenza['ora_uscita'].strftime('%Y-%m-%d %H:%M:%S') if presenza['ora_uscita'] else 'In corso'

        presenze_per_giorno[data].append({
            'id': presenza['id'],
            'nome': presenza['nome'],
            'cognome': presenza['cognome'],
            'entrata': entrata,
            'uscita': uscita
        })

    # Verifica i dati raggruppati
    print("Presenze per giorno:", presenze_per_giorno)

    return render_template('presenze.html', presenze_per_giorno=presenze_per_giorno)

@app.route('/increment-coffee', methods=['POST'])
def increment_coffee():
    print("Incremento caffè chiamato!")
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Utente non autenticato'}), 401

    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Impossibile connettersi al database'}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        
        # Recupera l'utente
        cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({'error': 'Utente non trovato'}), 404

        # Incrementa il contatore del caffè
        new_coffee_count = user['coffee_count'] + 1
        cursor.execute('UPDATE users SET coffee_count = %s WHERE id = %s', (new_coffee_count, user_id))
        conn.commit()

        return jsonify({'new_count': new_coffee_count})

    except Error as e:
        print(f"Errore nel database: {e}")
        return jsonify({'error': 'Errore durante l\'operazione'}), 500

    finally:
        cursor.close()
        conn.close()

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)